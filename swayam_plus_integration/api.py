import frappe
import requests

TOKEN_SCOPES = "partner.enrollments:read partner.completions:write"
TOKEN_CACHE_KEY = "swayam_plus_m2m_token"


def get_base_url():
	settings = frappe.get_single("SWAYAM Plus Settings")
	return (settings.base_url or "https://swayamplus.education.gov.in").rstrip("/")


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

	response = requests.post(
		f"{get_base_url()}/oidc/token",
		auth=(client_id, client_secret),
		data={"grant_type": "client_credentials", "scope": TOKEN_SCOPES},
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


def report_progress(enrollment_id, percent):
	percent = cint(percent)
	if percent < 0 or percent > 100:
		frappe.throw("Percent must be a whole number from 0 to 100.")
	return partner_request(
		"POST",
		f"/api/v1/partner/enrollments/{enrollment_id}/progress",
		json={"percent": percent},
		expected=(204,),
	)


def confirm_completion(enrollment_id, note=None):
	payload = {}
	if note:
		payload["note"] = note
	return partner_request(
		"POST",
		f"/api/v1/partner/enrollments/{enrollment_id}/completion",
		json=payload,
		expected=(204,),
	)


def partner_request(method, path, params=None, json=None, expected=(200,), retry=True):
	token = get_access_token()
	response = requests.request(
		method,
		f"{get_base_url()}{path}",
		headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
		params=params,
		json=json,
		timeout=30,
	)
	if response.status_code == 401 and retry:
		clear_token_cache()
		return partner_request(method, path, params=params, json=json, expected=expected, retry=False)

	body = _json_or_text(response)
	if response.status_code not in expected:
		frappe.throw(f"SWAYAM Plus {method} {path} failed ({response.status_code}): {body}")

	if response.status_code == 204:
		return {"status_code": 204}
	return body


def cint(value):
	return frappe.utils.cint(value)


def _json_or_text(response):
	try:
		return response.json()
	except ValueError:
		return {"raw": response.text}
