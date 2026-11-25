import re
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlparse

import frappe
from frappe import _
from frappe.utils import get_url
from frappe.utils.oauth import get_oauth2_authorize_url

PROVIDER = "swayam_plus"
DEFAULT_BASE_URL = "https://swayamplus.education.gov.in/oidc"


@frappe.whitelist(allow_guest=True)
def start_swayam_login(
	iss: str | None = None,
	login_hint: str | None = None,
	target_link_uri: str | None = None,
	lti_message_hint: str | None = None,
):
	"""Auto sign-in URL registered on the SWAYAM Plus sign-in credential."""
	iss = iss or frappe.form_dict.get("iss")
	target_link_uri = target_link_uri or frappe.form_dict.get("target_link_uri")
	login_hint = login_hint or frappe.form_dict.get("login_hint")
	lti_message_hint = lti_message_hint or frappe.form_dict.get("lti_message_hint")

	if iss != _issuer():
		frappe.throw(_("Invalid request"), frappe.ValidationError)

	if not frappe.db.get_single_value("SWAYAM Plus Settings", "enabled"):
		frappe.throw(_("SWAYAM Plus sign-in is disabled"))

	course_url = _safe_target(target_link_uri)
	course_id = _course_id_from_url(course_url)
	enrollment_id = lti_message_hint or _query_param(course_url, "swayamEnrollmentId")

	if frappe.session.user != "Guest":
		if course_id:
			_enroll_if_needed(frappe.session.user, course_id, enrollment_id)
		_redirect(course_url)
		return

	if not frappe.db.get_value("Social Login Key", PROVIDER, "enable_social_login"):
		frappe.throw(_("SWAYAM Plus social login is not enabled"))

	auth_url = get_oauth2_authorize_url(PROVIDER, _ensure_enrollment_url(course_id, course_url, enrollment_id))
	if login_hint:
		separator = "&" if "?" in auth_url else "?"
		auth_url = f"{auth_url}{separator}login_hint={quote_plus(str(login_hint))}"

	_redirect(auth_url)


@frappe.whitelist()
def ensure_swayam_enrollment(
	course: str | None = None,
	next: str | None = None,
	enrollment_id: str | None = None,
):
	"""Post-login landing. Social Login redirects here after the learner is signed in."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login"), frappe.PermissionError)

	course = course or frappe.form_dict.get("course")
	next_url = _safe_target(next or frappe.form_dict.get("next"))
	enrollment_id = enrollment_id or frappe.form_dict.get("enrollment_id")

	if not course:
		course = _course_id_from_url(next_url)

	if course:
		_enroll_if_needed(frappe.session.user, course, enrollment_id)

	_redirect(next_url or get_url("/lms"))


def _enroll_if_needed(user: str, course_id: str, enrollment_id: str | None = None):
	if not frappe.db.exists("LMS Course", course_id):
		frappe.log_error(
			title="SWAYAM enroll: course not found",
			message=f"course={course_id} user={user}",
		)
		return

	if frappe.db.exists("LMS Enrollment", {"course": course_id, "member": user}):
		return

	doc = frappe.get_doc(
		{
			"doctype": "LMS Enrollment",
			"course": course_id,
			"member": user,
			"member_type": "Student",
		}
	)
	if enrollment_id and doc.meta.has_field("swayam_enrollment_id"):
		doc.swayam_enrollment_id = enrollment_id
		if doc.meta.has_field("is_swayam_enrollment"):
			doc.is_swayam_enrollment = 1

	try:
		doc.insert(ignore_permissions=True)
	except frappe.ValidationError:
		frappe.log_error(title="SWAYAM enroll failed")
		return

	frappe.db.commit()


def _ensure_enrollment_url(course_id: str | None, course_url: str, enrollment_id: str | None) -> str:
	params = [f"next={quote(course_url)}"]
	if course_id:
		params.insert(0, f"course={quote(course_id)}")
	if enrollment_id:
		params.append(f"enrollment_id={quote(enrollment_id)}")
	return f"/api/method/swayam_plus_integration.sso.ensure_swayam_enrollment?{'&'.join(params)}"


def _course_id_from_url(url: str | None) -> str | None:
	if not url:
		return None
	match = re.search(r"/lms/courses/([^/]+)", urlparse(url).path)
	return unquote(match.group(1)) if match else None


def _query_param(url: str, key: str) -> str | None:
	values = parse_qs(urlparse(url).query).get(key) or []
	return values[0] if values else None


def _safe_target(target_link_uri: str | None) -> str:
	fallback = get_url("/lms")
	if not target_link_uri:
		return fallback

	site = urlparse(get_url())
	target = urlparse(target_link_uri)
	if not target.scheme and not target.netloc:
		return get_url(target_link_uri)
	if target.scheme in ("http", "https") and target.netloc == site.netloc:
		return target_link_uri
	return fallback


def _issuer() -> str:
	base = frappe.db.get_single_value("SWAYAM Plus Settings", "base_url") or DEFAULT_BASE_URL
	return base.rstrip("/")


def _redirect(location: str):
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = location
