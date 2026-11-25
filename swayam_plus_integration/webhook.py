import json

import frappe

from swayam_plus_integration.signature import verify_signature


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive():
	"""Receive a SWAYAM Plus webhook. Signature is checked before any enrollment change."""
	raw = frappe.request.get_data(cache=True) or b""
	header = frappe.get_request_header("X-Swayam-Signature") or ""
	secrets = _webhook_secrets()

	if not verify_signature(header, raw, secrets):
		frappe.local.response["http_status_code"] = 401
		return {"ok": False, "error": "invalid signature"}

	try:
		event = json.loads(raw.decode() or "{}")
	except ValueError:
		frappe.local.response["http_status_code"] = 400
		return {"ok": False, "error": "invalid json"}

	delivery_id = frappe.get_request_header("X-Swayam-Delivery") or event.get("id")
	if not delivery_id:
		frappe.local.response["http_status_code"] = 400
		return {"ok": False, "error": "missing delivery id"}

	if frappe.db.exists("SWAYAM Plus Webhook Log", delivery_id):
		return {"ok": True, "duplicate": True}

	event_type = event.get("type") or frappe.get_request_header("X-Swayam-Event")
	data = event.get("data") or {}
	log = frappe.get_doc(
		{
			"doctype": "SWAYAM Plus Webhook Log",
			"delivery_id": delivery_id,
			"event_type": event_type,
			"enrollment_id": data.get("enrollmentId"),
			"learner_sub": data.get("sub"),
			"sequence": event.get("sequence") or 0,
			"sandbox": 1 if event.get("sandbox") else 0,
			"signature_valid": 1,
			"processing_status": "Received",
			"payload": raw.decode(errors="replace"),
		}
	)
	log.insert(ignore_permissions=True)

	try:
		status = _apply_event(event, log)
		log.db_set("processing_status", status, update_modified=False)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "SWAYAM Plus Webhook")
		log.db_set("processing_status", "Failed", update_modified=False)
		log.db_set("error", frappe.get_traceback()[-1400:], update_modified=False)

	return {"ok": True}


def _webhook_secrets():
	if not frappe.db.exists("DocType", "SWAYAM Plus Settings"):
		return []
	settings = frappe.get_single("SWAYAM Plus Settings")
	secrets = []
	for field in ("webhook_secret", "webhook_previous_secret"):
		secret = settings.get_password(field, raise_exception=False)
		if secret:
			secrets.append(secret)
	return secrets


def _apply_event(event, log):
	event_type = event.get("type")
	if event_type == "ping":
		return "Ignored"

	data = event.get("data") or {}
	enrollment_id = data.get("enrollmentId")
	sequence = int(event.get("sequence") or 0)
	if not enrollment_id:
		return "Ignored"

	current_sequence = frappe.db.get_value("SWAYAM Plus Entitlement", enrollment_id, "sequence") or 0
	if sequence and sequence <= int(current_sequence):
		return "Ignored"

	if event_type == "enrollment.activated":
		_upsert_entitlement(event, "ACCESS_PROVISIONED")
		_enroll_if_possible(enrollment_id)
		return "Processed"

	if event_type == "enrollment.revoked":
		_upsert_entitlement(event, "TERMINATED")
		_mark_access_ended(enrollment_id)
		return "Processed"

	if event_type == "enrollment.completed":
		_upsert_entitlement(event, "COMPLETED")
		frappe.db.set_value("SWAYAM Plus Entitlement", enrollment_id, "completion_sent", 1, update_modified=False)
		return "Processed"

	return "Ignored"


def _upsert_entitlement(event, status):
	data = event.get("data") or {}
	enrollment_id = data.get("enrollmentId")
	values = {
		"learner_sub": data.get("sub"),
		"swayam_course_id": data.get("courseId"),
		"partner_course_id": data.get("partnerCourseId"),
		"status": data.get("status") or status,
		"sandbox": 1 if event.get("sandbox") else 0,
		"sequence": int(event.get("sequence") or 0),
		"last_event": event.get("type"),
		"payload": frappe.as_json(event),
	}
	course = resolve_course(data.get("partnerCourseId"))
	if course:
		values["partner_course"] = course

	if frappe.db.exists("SWAYAM Plus Entitlement", enrollment_id):
		frappe.db.set_value("SWAYAM Plus Entitlement", enrollment_id, values, update_modified=True)
		return enrollment_id

	doc = frappe.get_doc({"doctype": "SWAYAM Plus Entitlement", "enrollment_id": enrollment_id, **values})
	doc.insert(ignore_permissions=True)
	return doc.name


def _enroll_if_possible(enrollment_id):
	entitlement = frappe.get_doc("SWAYAM Plus Entitlement", enrollment_id)
	if not entitlement.learner_sub or not entitlement.partner_course:
		return
	user = frappe.db.get_value(
		"User Social Login",
		{"provider": "swayam_plus", "userid": entitlement.learner_sub},
		"parent",
	)
	if not user:
		return
	enrollment = ensure_lms_enrollment(user, entitlement.partner_course, entitlement.enrollment_id, entitlement.learner_sub)
	entitlement.db_set("lms_user", user, update_modified=False)
	entitlement.db_set("lms_enrollment", enrollment, update_modified=False)


def _mark_access_ended(enrollment_id):
	lms_enrollment = frappe.db.get_value("SWAYAM Plus Entitlement", enrollment_id, "lms_enrollment")
	if lms_enrollment and frappe.db.exists("LMS Enrollment", lms_enrollment):
		frappe.db.set_value("LMS Enrollment", lms_enrollment, "swayam_access_ended", 1, update_modified=False)


def resolve_course(partner_course_id):
	if not partner_course_id:
		return None
	if frappe.db.exists("LMS Course", partner_course_id):
		return partner_course_id
	return frappe.db.get_value("LMS Course", {"name": partner_course_id.lower()}, "name")


def ensure_lms_enrollment(user, course, enrollment_id, learner_sub):
	existing = frappe.db.get_value("LMS Enrollment", {"course": course, "member": user}, "name")
	if existing:
		frappe.db.set_value(
			"LMS Enrollment",
			existing,
			{
				"is_swayam_enrollment": 1,
				"swayam_enrollment_id": enrollment_id,
				"swayam_learner_sub": learner_sub,
				"swayam_access_ended": 0,
			},
			update_modified=False,
		)
		return existing

	enrollment = frappe.get_doc(
		{
			"doctype": "LMS Enrollment",
			"course": course,
			"member": user,
			"member_type": "Student",
			"is_swayam_enrollment": 1,
			"swayam_enrollment_id": enrollment_id,
			"swayam_learner_sub": learner_sub,
		}
	)
	enrollment.insert(ignore_permissions=True)
	return enrollment.name


def link_entitlements_for_user(user, learner_sub):
	"""Enroll a learner in courses whose webhook arrived before the first sign-in."""
	names = frappe.get_all(
		"SWAYAM Plus Entitlement",
		filters={"learner_sub": learner_sub, "status": ["!=", "TERMINATED"]},
		pluck="name",
	)
	for name in names:
		entitlement = frappe.get_doc("SWAYAM Plus Entitlement", name)
		if entitlement.partner_course:
			enrollment = ensure_lms_enrollment(user, entitlement.partner_course, entitlement.enrollment_id, learner_sub)
			entitlement.db_set("lms_user", user, update_modified=False)
			entitlement.db_set("lms_enrollment", enrollment, update_modified=False)
