# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.data import get_url


class SWAYAMPlusSettings(Document):
	def validate(self):
		self.base_url = (self.base_url or "https://swayamplus.education.gov.in").rstrip("/")
		self.redirect_url = get_url("/api/method/swayam_plus_integration.sso.callback")
		self.sso_start_url = get_url("/api/method/swayam_plus_integration.sso.start")
		self.webhook_url = get_url("/api/method/swayam_plus_integration.webhook.receive")

	@frappe.whitelist()
	def test_connection(self):
		from swayam_plus_integration.api import ping

		result = ping()
		scopes = ", ".join(result.get("scopes") or [])
		return {"message": f"Connected as {result.get('clientId')}. Scopes: {scopes}", "result": result}

	@frappe.whitelist()
	def fetch_enrollments(self):
		from swayam_plus_integration.api import list_enrollments

		data = list_enrollments(page=1, limit=20)
		enrollments = data.get("enrollments") or []
		meta = data.get("meta") or {}
		lines = []
		for row in enrollments:
			lines.append(
				"{name} | {status} | {percent}% | sandbox={sandbox} | {enrollment_id}".format(
					name=row.get("studentName") or "Learner",
					status=row.get("status"),
					percent=row.get("progressPercent"),
					sandbox=row.get("sandbox"),
					enrollment_id=row.get("enrollmentId"),
				)
			)
		message = "Page {page} of {pages} ({total} enrollments).".format(
			page=meta.get("page"),
			pages=meta.get("totalPages"),
			total=meta.get("total"),
		)
		if lines:
			message = message + "\n" + "\n".join(lines)
		else:
			message = message + "\nNo enrollments yet. Enroll a test learner in SWAYAM Plus Test drive."
		return {"message": message, "data": data}

	@frappe.whitelist()
	def send_progress(self, enrollment_id, percent):
		from swayam_plus_integration.api import report_progress

		report_progress(enrollment_id, percent)
		return {"message": f"Progress {int(percent)} accepted for {enrollment_id}."}

	@frappe.whitelist()
	def send_completion(self, enrollment_id):
		from swayam_plus_integration.api import confirm_completion

		confirm_completion(enrollment_id)
		return {"message": f"Completion accepted for {enrollment_id}. This cannot be undone."}
