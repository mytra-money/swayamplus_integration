# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class SWAYAMPlusSettings(Document):
	def validate(self):
		base = (self.base_url or "https://swayamplus.education.gov.in/oidc").rstrip("/")
		if not base.endswith("/oidc"):
			base = f"{base}/oidc"
		self.base_url = base
