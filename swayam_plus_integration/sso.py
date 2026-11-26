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
		_link_pending_entitlements(frappe.session.user)
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

	_link_pending_entitlements(frappe.session.user)

	if course:
		_enroll_if_needed(frappe.session.user, course, enrollment_id)

	_redirect(next_url or get_url("/lms"))


def _learner_sub(user: str) -> str | None:
	return frappe.db.get_value(
		"User Social Login",
		{"parent": user, "provider": PROVIDER},
		"userid",
	)


def _link_pending_entitlements(user: str):
	learner_sub = _learner_sub(user)
	if not learner_sub or not frappe.db.get_single_value("SWAYAM Plus Settings", "api_client_id"):
		return
	try:
		from swayam_plus_integration.api import get_student_enrollments

		data = get_student_enrollments(learner_sub)
	except Exception:
		return

	for row in data.get("enrollments") or []:
		if row.get("status") == "TERMINATED":
			continue
		course = row.get("partnerCourseId")
		if course:
			_enroll_if_needed(user, course, row.get("enrollmentId"))


def _enroll_if_needed(user: str, course_id: str, enrollment_id: str | None = None):
	"""Create LMS Enrollment for a SWAYAM launch.

	SkillDzire does not use LMS paid-course or published eligibility for partner
	launches. ``managed_by_caller`` skips those LMS Enrollment gates.
	"""
	if not frappe.db.exists("LMS Course", course_id):
		frappe.log_error(
			title="SWAYAM enroll: course not found",
			message=f"course={course_id} user={user}",
		)
		return

	meta = frappe.get_meta("LMS Enrollment")
	has_enrollment_id = meta.has_field("swayam_enrollment_id")

	existing = frappe.db.get_value(
		"LMS Enrollment",
		{"course": course_id, "member": user},
		["name", "swayam_enrollment_id"] if has_enrollment_id else "name",
		as_dict=True,
	)
	if existing:
		if enrollment_id and has_enrollment_id and not existing.swayam_enrollment_id:
			frappe.db.set_value("LMS Enrollment", existing.name, "swayam_enrollment_id", enrollment_id)
			frappe.db.commit()
		return

	doc = frappe.get_doc(
		{
			"doctype": "LMS Enrollment",
			"course": course_id,
			"member": user,
			"member_type": "Student",
		}
	)
	if enrollment_id and has_enrollment_id:
		doc.swayam_enrollment_id = enrollment_id

	# Skip LMS paid / unpublished / self-learning checks for SWAYAM partner enrolls.
	doc.flags.managed_by_caller = True

	try:
		doc.insert(ignore_permissions=True)
	except frappe.ValidationError:
		frappe.log_error(
			title="SWAYAM enroll failed",
			message=f"course={course_id} user={user} swayam_enrollment_id={enrollment_id}",
		)
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
