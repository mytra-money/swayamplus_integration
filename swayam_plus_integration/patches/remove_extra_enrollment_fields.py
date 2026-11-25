import frappe

OBSOLETE = (
	"LMS Enrollment-is_swayam_enrollment",
	"LMS Enrollment-swayam_learner_sub",
	"LMS Enrollment-swayam_access_ended",
)


def execute():
	for name in OBSOLETE:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
