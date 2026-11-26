app_name = "swayam_plus_integration"
app_title = "SWAYAM Plus Integration"
app_publisher = "Mytra"
app_description = "SWAYAM Plus partner API, sign-in, and webhooks for Frappe LMS"
app_email = "hello@mytra.money"
app_license = "mit"

required_apps = ["lms"]

doc_events = {
	"LMS Enrollment": {
		"on_change": "swayam_plus_integration.doctype_events.lms_enrollment.on_change",
	}
}

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["name", "in", ["LMS Enrollment-swayam_enrollment_id"]]],
	}
]
