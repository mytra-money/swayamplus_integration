import frappe
import requests
from frappe.integrations.utils import create_request_log

TOKEN_SCOPES = "partner.enrollments:read partner.completions:write"
TOKEN_CACHE_KEY = "swayam_plus_m2m_token"


class SwayamAPIError(frappe.ValidationError):
	"""HTTP error from SWAYAM Plus Partner API with status and error code."""

	def __init__(self, message, status_code=None, error_code=None, body=None):
		super().__init__(message)
		self.status_code = status_code
		self.error_code = error_code
		self.body = body or {}


def get_api_host():
	"""Host for partner REST and OIDC token. Settings base_url ends with /oidc for SSO iss."""
	settings = frappe.get_single("SWAYAM Plus Settings")
	base = (settings.base_url or "https://swayamplus.education.gov.in/oidc").rstrip("/")
	if base.endswith("/oidc"):
		base = base[: -len("/oidc")]
	return base.rstrip("/") or "https://swayamplus.education.gov.in"


def get_access_token(force=False):
	if not force:
		cached = frappe.cache.get_value(TOKEN_CACHE_KEY)
		if cached:
			return cached

	settings = frappe.get_single("SWAYAM Plus Settings")
	client_id = (settings.api_client_id or "").strip()
	client_secret = settings.get_password("api_client_secret", raise_exception=False)
	if not client_id or not client_secret:
		frappe.throw("Set the API Client ID and API Client Secret in SWAYAM Plus Settings.")

	scopes = TOKEN_SCOPES
	response = requests.post(
		f"{get_api_host()}/oidc/token",
		auth=(client_id, client_secret),
		data={"grant_type": "client_credentials", "scope": scopes},
		timeout=30,
	)
	body = _json_or_text(response)
	if response.status_code != 200:
		frappe.throw(f"SWAYAM Plus token request failed ({response.status_code}): {body}")

	token = body.get("access_token")
	if not token:
		frappe.throw("SWAYAM Plus token response did not include an access token.")

	expires_in = int(body.get("expires_in") or 600)
	frappe.cache.set_value(TOKEN_CACHE_KEY, token, expires_in_sec=max(expires_in - 60, 30))
	return token


def clear_token_cache():
	frappe.cache.delete_value(TOKEN_CACHE_KEY)


def ping():
	return partner_request("GET", "/api/v1/partner/ping")


def list_enrollments(page=1, limit=20, course_id=None, status=None):
	params = {"page": cint(page) or 1, "limit": min(cint(limit) or 20, 100)}
	if course_id:
		params["courseId"] = course_id
	if status:
		params["status"] = status
	return partner_request("GET", "/api/v1/partner/enrollments", params=params)


def list_all_enrollments(course_id=None, status=None):
	"""Fetch all enrollment pages until meta.hasNext is False."""
	page = 1
	rows = []
	while True:
		data = list_enrollments(page=page, limit=100, course_id=course_id, status=status)
		rows.extend(data.get("enrollments") or [])
		meta = data.get("meta") or {}
		if not meta.get("hasNext"):
			break
		page += 1
	return rows


def get_student_enrollments(sub, page=1, limit=100):
	params = {"page": cint(page) or 1, "limit": min(cint(limit) or 100, 100)}
	return partner_request("GET", f"/api/v1/partner/students/{sub}/enrollments", params=params)


def report_progress(enrollment_id, percent, reference_docname=None):
	percent = cint(percent)
	if percent < 0 or percent > 100:
		frappe.throw("Percent must be a whole number from 0 to 100.")
	ref_name = reference_docname or frappe.db.get_value(
		"LMS Enrollment", {"swayam_enrollment_id": enrollment_id}, "name"
	)
	return partner_request(
		"POST",
		f"/api/v1/partner/enrollments/{enrollment_id}/progress",
		json={"percent": percent},
		expected=(204,),
		reference_doctype="LMS Enrollment" if ref_name else None,
		reference_docname=ref_name,
	)


def confirm_completion(enrollment_id, note=None, reference_docname=None):
	payload = {}
	if note:
		payload["note"] = note
	ref_name = reference_docname or frappe.db.get_value(
		"LMS Enrollment", {"swayam_enrollment_id": enrollment_id}, "name"
	)
	return partner_request(
		"POST",
		f"/api/v1/partner/enrollments/{enrollment_id}/completion",
		json=payload,
		expected=(204,),
		reference_doctype="LMS Enrollment" if ref_name else None,
		reference_docname=ref_name,
	)


def partner_request(
	method,
	path,
	params=None,
	json=None,
	expected=(200,),
	retry=True,
	integration_request=None,
	reference_doctype=None,
	reference_docname=None,
):
	url = f"{get_api_host()}{path}"
	safe_headers = {"Authorization": "Bearer ***", "Accept": "application/json"}
	request_data = json or params or ""
	if integration_request is None:
		integration_request = create_request_log(
			data=request_data,
			service_name="SWAYAM Plus",
			is_remote_request=1,
			request_description=f"{method} {path}",
			url=url,
			request_headers=safe_headers,
			reference_doctype=reference_doctype or "SWAYAM Plus Settings",
			reference_docname=reference_docname or "SWAYAM Plus Settings",
		)

	token = get_access_token()
	response = requests.request(
		method,
		url,
		headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
		params=params,
		json=json,
		timeout=30,
	)
	if response.status_code == 401 and retry:
		clear_token_cache()
		return partner_request(
			method,
			path,
			params=params,
			json=json,
			expected=expected,
			retry=False,
			integration_request=integration_request,
			reference_doctype=reference_doctype,
			reference_docname=reference_docname,
		)

	body = _json_or_text(response)
	if response.status_code not in expected:
		error_code = body.get("error") if isinstance(body, dict) else None
		integration_request.db_set(
			{
				"status": "Failed",
				"error": frappe.as_json({"status_code": response.status_code, "body": body}),
			},
			update_modified=False,
		)
		raise SwayamAPIError(
			f"SWAYAM Plus {method} {path} failed ({response.status_code}): {body}",
			status_code=response.status_code,
			error_code=error_code,
			body=body,
		)

	result = {"status_code": 204} if response.status_code == 204 else body
	integration_request.db_set(
		{
			"status": "Completed",
			"output": frappe.as_json(result),
		},
		update_modified=False,
	)
	return result


def cint(value):
	return frappe.utils.cint(value)


def _json_or_text(response):
	try:
		return response.json()
	except ValueError:
		return {"raw": response.text}
