import frappe

from swayam_plus_integration.api import confirm_completion, report_progress


def on_change(doc, method=None):
	if not doc.get("swayam_enrollment_id") or doc.get("swayam_access_ended"):
		return
	if not doc.has_value_changed("progress"):
		return

	entitlement = frappe.db.get_value(
		"SWAYAM Plus Entitlement",
		doc.swayam_enrollment_id,
		["completion_sent", "status"],
		as_dict=True,
	)
	if entitlement and (entitlement.completion_sent or entitlement.status == "COMPLETED"):
		return

	percent = int(round(doc.progress or 0))
	percent = max(0, min(percent, 100))
	try:
		report_progress(doc.swayam_enrollment_id, percent)
		if entitlement:
			frappe.db.set_value(
				"SWAYAM Plus Entitlement",
				doc.swayam_enrollment_id,
				{"status": "IN_PROGRESS" if percent < 100 else "COMPLETED", "last_progress_percent": percent},
				update_modified=False,
			)
		if percent == 100:
			confirm_completion(doc.swayam_enrollment_id)
			frappe.db.set_value(
				"SWAYAM Plus Entitlement",
				doc.swayam_enrollment_id,
				"completion_sent",
				1,
				update_modified=False,
			)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "SWAYAM Plus Progress")
