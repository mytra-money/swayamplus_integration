app_name = "swayam_plus_integration"
app_title = "SWAYAM Plus Integration"
app_publisher = "Mytra"
app_description = "SWAYAM Plus sign-in and course enrollment for Frappe LMS"
app_email = "hello@mytra.money"
app_license = "mit"

required_apps = ["lms"]

fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					"LMS Enrollment-swayam_enrollment_id",
				],
			]
		],
	}
]
