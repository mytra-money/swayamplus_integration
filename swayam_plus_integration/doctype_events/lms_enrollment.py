import frappe

from swayam_plus_integration.api import SwayamAPIError, confirm_completion, report_progress


def on_change(doc, method=None):
	if not doc.get("swayam_enrollment_id"):
		return
	if not doc.has_value_changed("progress"):
		return
	if not frappe.db.get_single_value("SWAYAM Plus Settings", "enabled"):
		return

	percent = max(0, min(int(round(doc.progress or 0)), 100))
	frappe.enqueue(
		"swayam_plus_integration.doctype_events.lms_enrollment.sync_progress",
		queue="short",
		enrollment_id=doc.swayam_enrollment_id,
		percent=percent,
		lms_enrollment_name=doc.name,
		enqueue_after_commit=True,
	)


def sync_progress(enrollment_id, percent, lms_enrollment_name=None):
	"""Background worker to report progress (and completion at 100%) to SWAYAM Plus."""
	percent = max(0, min(int(percent or 0), 100))
	try:
		report_progress(enrollment_id, percent, reference_docname=lms_enrollment_name)
		if percent == 100:
			confirm_completion(enrollment_id, reference_docname=lms_enrollment_name)
	except SwayamAPIError as exc:
		if exc.status_code == 409 or exc.error_code == "INVALID_HANDOFF_TRANSITION":
			return
		frappe.log_error(frappe.get_traceback(), "SWAYAM Plus Progress")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "SWAYAM Plus Progress")
