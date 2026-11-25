import frappe

KEEP = "LMS Enrollment-swayam_enrollment_id"
OBSOLETE = (
	"LMS Enrollment-is_swayam_enrollment",
	"LMS Enrollment-swayam_learner_sub",
	"LMS Enrollment-swayam_access_ended",
)


def execute():
	for name in OBSOLETE:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)

	if not frappe.db.exists("Custom Field", KEEP):
		frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "LMS Enrollment",
				"fieldname": "swayam_enrollment_id",
				"fieldtype": "Data",
				"insert_after": "member_type",
				"label": "SWAYAM Plus Enrollment ID",
				"module": "SWAYAM Plus",
				"name": KEEP,
				"read_only": 1,
				"search_index": 1,
			}
		).insert(ignore_permissions=True)
