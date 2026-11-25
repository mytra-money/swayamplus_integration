# Copyright (c) 2026, Mytra and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils.data import get_url

REDIRECT_PATH = "/api/method/frappe.integrations.oauth2_logins.custom/swayam_plus"
START_PATH = "/api/method/swayam_plus_integration.sso.start_swayam_login"


class SWAYAMPlusSettings(Document):
	def validate(self):
		self.base_url = (self.base_url or "https://swayamplus.education.gov.in").rstrip("/")
		issuer = f"{self.base_url}/oidc"
		self.issuer = issuer
		self.authorize_url = f"{issuer}/auth"
		self.access_token_url = f"{issuer}/token"
		self.userinfo_url = f"{issuer}/me"
		self.scope = "openid email profile"
		self.social_login_key = "swayam_plus"
		self.redirect_url = get_url(REDIRECT_PATH)
		self.sso_start_url = get_url(START_PATH)
