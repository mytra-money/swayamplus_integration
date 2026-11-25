// Copyright (c) 2026, Mytra and contributors
// For license information, please see license.txt

frappe.ui.form.on("SWAYAM Plus Settings", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Test Connection"), () => {
			frm.call("test_connection").then((r) => {
				frappe.msgprint(r.message.message || __("Connected"));
			});
		});
		frm.add_custom_button(__("List Enrollments"), () => {
			frm.call("fetch_enrollments").then((r) => {
				frappe.msgprint({
					title: __("Enrollments"),
					message: frappe.utils.escape_html(r.message.message || "").replaceAll("\n", "<br>"),
					indicator: "blue",
				});
			});
		});
		frm.add_custom_button(__("Send Progress"), () => {
			frappe.prompt(
				[
					{
						fieldname: "enrollment_id",
						fieldtype: "Data",
						label: __("Enrollment ID"),
						reqd: 1,
					},
					{
						fieldname: "percent",
						fieldtype: "Int",
						label: __("Percent"),
						reqd: 1,
						default: 40,
					},
				],
				(values) => {
					frm.call("send_progress", values).then((r) => {
						frappe.msgprint(r.message.message);
					});
				},
				__("Send Progress"),
				__("Send")
			);
		});
		frm.add_custom_button(__("Confirm Completion"), () => {
			frappe.prompt(
				[
					{
						fieldname: "enrollment_id",
						fieldtype: "Data",
						label: __("Enrollment ID"),
						reqd: 1,
					},
				],
				(values) => {
					frappe.confirm(
						__(
							"Completion is final. SWAYAM Plus will unlock the assessment and certificate for this enrollment."
						),
						() => {
							frm.call("send_completion", values).then((r) => {
								frappe.msgprint(r.message.message);
							});
						}
					);
				},
				__("Confirm Completion"),
				__("Continue")
			);
		});
	},
});
