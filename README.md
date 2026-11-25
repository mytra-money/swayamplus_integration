# SWAYAM Plus Integration

Phase 1 signs a SWAYAM Plus learner into Frappe LMS with a Social Login Key and enrolls them in the course from the launch URL.

The only DocType is SWAYAM Plus Settings. Social Login Key holds the authorize URL, token URL, userinfo URL, redirect URL, and sign-in client credentials. Settings enables sign-in, stores the issuer host, shows the Auto sign-in URL, and holds the separate **API Access** credential (client id and secret) for enrollments and progress reporting. The partner API client, webhooks, and entitlement records are deferred. See [PHASE_2.md](PHASE_2.md).

## Install

```bash
bench --site <site> install-app swayam_plus_integration
bench --site <site> migrate
```

## Social Login Key

Create **Social Login Key** with provider name `SWAYAM Plus`. The document name must be `swayam_plus`.

| Field | Value |
|---|---|
| Enable Social Login | Checked |
| Sign Ups | Allow |
| Custom Base URL | Checked |
| Base URL | `https://swayamplus.education.gov.in/oidc` |
| Authorize URL | `/auth` |
| Access Token URL | `/token` |
| API Endpoint | `/me` |
| Redirect URL | `/api/method/frappe.integrations.oauth2_logins.custom/swayam_plus` |
| User ID Property | `sub` |
| Auth URL Data | `{"response_type": "code", "scope": "openid email profile"}` |
| Client ID and Client Secret | The SWAYAM sign-in credential |

Open **SWAYAM Plus Settings**, enable it, and save once. Register **Auto Sign-in URL** on the SWAYAM sign-in credential. Register the Social Login Key redirect URL as the SWAYAM sign-in redirect URL.

Use the same Base URL that SWAYAM sends as `iss`, including `/oidc`.

## API Access

On the SWAYAM Plus partner portal, open **API access** → **Create API credential**, then paste the values into **SWAYAM Plus Settings**:

| Settings field | Value |
|---|---|
| API Client ID | Client ID from the API credential |
| API Client Secret | Client secret (shown once) |
| API Scopes | Read-only: `partner.enrollments:read partner.completions:write partner.reconciliation:read` |

This credential is not the Social Login sign-in client. Token calls and progress reporting will use these fields later.

## What a launch does

1. SWAYAM opens the Auto Sign-in URL with `iss`, `target_link_uri`, and optional `login_hint` and `lti_message_hint`.
2. A guest is sent through the Social Login Key. Frappe creates or matches the user and logs them in.
3. The browser returns to `ensure_swayam_enrollment`, which creates an LMS Enrollment for `/lms/courses/<course-id>` when that course exists and the learner is not already enrolled.
4. The learner lands on the course URL. A URL on another site is replaced with `/lms`.
