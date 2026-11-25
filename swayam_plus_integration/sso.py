import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlparse

import frappe
import requests

from swayam_plus_integration.api import get_base_url
from swayam_plus_integration.webhook import link_entitlements_for_user

ISSUER_PATH = "/oidc"
OIDC_CACHE_PREFIX = "swayam_plus_oidc:"


class SignInError(Exception):
	def __init__(self, title, message):
		self.title = title
		self.message = message


@frappe.whitelist(allow_guest=True)
def start():
	"""Login initiation URL. Register this as the SWAYAM Plus Auto sign-in URL."""
	iss = frappe.form_dict.get("iss") or ""
	expected_iss = f"{get_base_url()}{ISSUER_PATH}"
	if iss != expected_iss:
		return _error("Invalid sign-in request", "The issuer is not SWAYAM Plus.")

	target = frappe.form_dict.get("target_link_uri") or ""
	if not _same_site(target):
		return _error("Invalid sign-in request", "The course address is not on this site.")

	settings = frappe.get_single("SWAYAM Plus Settings")
	client_id = (settings.signin_client_id or "").strip()
	if not client_id:
		return _error("Sign-in is not configured", "Set the sign-in Client ID in SWAYAM Plus Settings.")

	state = secrets.token_urlsafe(24)
	nonce = secrets.token_urlsafe(24)
	verifier = secrets.token_urlsafe(64)
	frappe.cache.set_value(
		OIDC_CACHE_PREFIX + state,
		{
			"nonce": nonce,
			"verifier": verifier,
			"target": target,
			"enrollment_id": frappe.form_dict.get("lti_message_hint") or _enrollment_id_from_target(target),
		},
		expires_in_sec=600,
	)

	query = urlencode(
		{
			"client_id": client_id,
			"response_type": "code",
			"scope": "openid email profile",
			"redirect_uri": settings.redirect_url,
			"state": state,
			"nonce": nonce,
			"code_challenge": _code_challenge(verifier),
			"code_challenge_method": "S256",
			"login_hint": frappe.form_dict.get("login_hint") or "",
		}
	)
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = f"{expected_iss}/auth?{query}"


@frappe.whitelist(allow_guest=True)
def callback():
	"""OIDC redirect URL. Register this exact address on the sign-in credential."""
	error = frappe.form_dict.get("error")
	if error:
		return _error("Sign-in failed", frappe.form_dict.get("error_description") or error)

	state = frappe.form_dict.get("state")
	code = frappe.form_dict.get("code")
	if not state or not code:
		return _error("Sign-in failed", "SWAYAM Plus did not return a code.")

	cached = frappe.cache.get_value(OIDC_CACHE_PREFIX + state)
	frappe.cache.delete_value(OIDC_CACHE_PREFIX + state)
	if not cached:
		return _error("Sign-in failed", "This sign-in attempt expired. Open the course from SWAYAM Plus again.")

	settings = frappe.get_single("SWAYAM Plus Settings")
	client_id = (settings.signin_client_id or "").strip()
	client_secret = settings.get_password("signin_client_secret", raise_exception=False)
	if not client_id or not client_secret:
		return _error("Sign-in is not configured", "Set the sign-in Client ID and secret in SWAYAM Plus Settings.")

	token_response = requests.post(
		f"{get_base_url()}{ISSUER_PATH}/token",
		auth=(client_id, client_secret),
		data={
			"grant_type": "authorization_code",
			"code": code,
			"redirect_uri": settings.redirect_url,
			"code_verifier": cached["verifier"],
		},
		timeout=30,
	)
	if token_response.status_code != 200:
		frappe.log_error(token_response.text[:1500], "SWAYAM Plus Token Exchange")
		return _error("Sign-in failed", "SWAYAM Plus rejected the authorization code.")

	token_body = token_response.json()
	profile = _userinfo(token_body.get("access_token"))
	if not profile or not profile.get("sub"):
		return _error("Sign-in failed", "SWAYAM Plus did not return a learner profile.")

	try:
		user = _upsert_user(profile)
	except SignInError as exc:
		return _error(exc.title, exc.message)
	except frappe.PermissionError:
		return _error("Signup is disabled", "This site is not accepting new learner accounts.")

	link_entitlements_for_user(user, profile["sub"])
	if cached.get("enrollment_id"):
		_attach_launch_enrollment(user, cached["enrollment_id"], profile["sub"])

	frappe.local.login_manager.login_as(user)
	frappe.db.commit()
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = cached["target"]


def _userinfo(access_token):
	if not access_token:
		return None
	response = requests.get(
		f"{get_base_url()}{ISSUER_PATH}/me",
		headers={"Authorization": f"Bearer {access_token}"},
		timeout=30,
	)
	if response.status_code != 200:
		frappe.log_error(response.text[:1500], "SWAYAM Plus Userinfo")
		return None
	return response.json()


def _upsert_user(profile):
	from frappe.website.utils import is_signup_disabled

	sub = profile["sub"]
	email = (profile.get("email") or "").strip()
	user_name = frappe.db.get_value("User Social Login", {"provider": "swayam_plus", "userid": sub}, "parent")
	if not user_name and email:
		user_name = frappe.db.get_value("User", {"email": email}, "name")

	if user_name:
		user = frappe.get_doc("User", user_name)
	else:
		if is_signup_disabled():
			raise frappe.PermissionError
		if not email:
			raise SignInError("Sign-in failed", "SWAYAM Plus did not share an email address for a new learner.")
		user = frappe.new_doc("User")
		user.update(
			{
				"email": email,
				"first_name": (profile.get("given_name") or profile.get("name") or email).strip(),
				"last_name": (profile.get("family_name") or "").strip(),
				"enabled": 1,
				"user_type": "Website User",
				"new_password": frappe.generate_hash(),
			}
		)

	if not user.enabled:
		raise SignInError("Not allowed", f"User {user.email} is disabled.")

	existing_sub = user.get_social_login_userid("swayam_plus")
	if existing_sub and existing_sub != sub:
		raise SignInError(
			"Sign-in failed",
			"This email is already linked to a different SWAYAM Plus learner.",
		)

	if not existing_sub:
		user.set_social_login_userid("swayam_plus", userid=sub)
		user.flags.ignore_permissions = True
		user.flags.no_welcome_mail = True
		if default_role := frappe.db.get_single_value("Portal Settings", "default_role"):
			user.add_roles(default_role)
		user.save(ignore_permissions=True)
	return user.name


def _attach_launch_enrollment(user, enrollment_id, learner_sub):
	if not frappe.db.exists("SWAYAM Plus Entitlement", enrollment_id):
		return
	entitlement = frappe.get_doc("SWAYAM Plus Entitlement", enrollment_id)
	if entitlement.learner_sub and entitlement.learner_sub != learner_sub:
		return
	if not entitlement.partner_course:
		return
	from swayam_plus_integration.webhook import ensure_lms_enrollment

	enrollment = ensure_lms_enrollment(user, entitlement.partner_course, enrollment_id, learner_sub)
	entitlement.db_set("lms_user", user, update_modified=False)
	entitlement.db_set("lms_enrollment", enrollment, update_modified=False)


def _code_challenge(verifier):
	digest = hashlib.sha256(verifier.encode()).digest()
	return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _enrollment_id_from_target(target):
	query = urlparse(target).query
	for part in query.split("&"):
		if part.startswith("swayamEnrollmentId="):
			return part.split("=", 1)[1]
	return None


def _same_site(url):
	if not url:
		return False
	target = urlparse(url)
	site = urlparse(frappe.utils.get_url())
	return target.scheme in ("http", "https") and target.netloc == site.netloc


def _error(title, message):
	return frappe.respond_as_web_page(title, message, success=False, http_status_code=403)
