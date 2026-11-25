# SWAYAM Plus Integration

Frappe LMS app for the SWAYAM Plus partner API. It stores credentials, receives webhooks, signs learners in with OpenID Connect, and can report progress and completion.

This is separate from the SIDH integration. The two protocols are not interchangeable.

## DocTypes

- **SWAYAM Plus Settings** stores the API credential, the sign-in credential, and the webhook signing secret. The form has buttons for the basic API test: Test Connection, List Enrollments, Send Progress, and Confirm Completion.
- **SWAYAM Plus Entitlement** is one SWAYAM Plus enrollment. The document name is the `enrollmentId`.
- **SWAYAM Plus Webhook Log** stores each signed delivery. The document name is the delivery id, so retries are ignored.

LMS Enrollment gets four read-only fields: Is SWAYAM Plus Enrollment, SWAYAM Plus Enrollment ID, SWAYAM Plus Learner ID, and SWAYAM Plus Access Ended.

## Install

```bash
bench --site <site> install-app swayam_plus_integration
```

Open **SWAYAM Plus Settings**, save once, and copy the three generated URLs into the SWAYAM Plus Integration page:

| SWAYAM Plus field | Settings field |
|---|---|
| API credential | API Client ID and API Client Secret |
| Sign-in redirect URL | Redirect URL |
| Auto sign-in URL | Auto Sign-in URL |
| Webhook receiver URL | Webhook URL |
| Webhook signing secret | Webhook Signing Secret |

The site that receives webhooks must be reachable over public HTTPS.

## Basic API test

1. Paste the API Client ID and secret. Save.
2. Click **Test Connection**. A successful call shows the client id and both scopes.
3. On SWAYAM Plus, create the Test drive course, add a test learner, and enroll them. Set the partner course id to the LMS Course name.
4. Click **List Enrollments** and copy the enrollment id. `sandbox` is true for Test drive.
5. Click **Send Progress** with that id and a percent such as 40.
6. Click **Confirm Completion** only when the learner has finished the course. Completion is final.

## What the LMS does after that

- A verified `enrollment.activated` webhook creates an entitlement. If the learner already has an account, it also creates the LMS Enrollment.
- The first **Go to course** visit hits the Auto Sign-in URL, creates the user from the SWAYAM Plus `sub`, and enrolls them from any stored entitlement.
- When that enrollment's progress changes, the app posts the percent. At 100 it also posts completion.
- `enrollment.revoked` marks the entitlement terminated and sets SWAYAM Plus Access Ended. It does not delete the enrollment.
