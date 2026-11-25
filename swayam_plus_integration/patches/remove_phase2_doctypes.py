import frappe


def execute():
	for name in ("SWAYAM Plus Webhook Log", "SWAYAM Plus Entitlement"):
		if frappe.db.exists("DocType", name):
			frappe.delete_doc("DocType", name, force=True, ignore_permissions=True)
