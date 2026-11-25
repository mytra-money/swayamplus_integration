# SWAYAM Plus Integration

Phase 1 signs a SWAYAM Plus learner into Frappe LMS with a Social Login Key and enrolls them in the course from the launch URL.

The only DocType is SWAYAM Plus Settings. It stores the sign-in endpoints. The sign-in Client ID and Client Secret are entered only on the Social Login Key. Webhooks, the partner API, and entitlement records are deferred. See [PHASE_2.md](PHASE_2.md).

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
| Authorize URL | Authorize URL from SWAYAM Plus Settings |
| Access Token URL | Access Token URL from SWAYAM Plus Settings |
| API Endpoint | Userinfo URL from SWAYAM Plus Settings |
| Redirect URL | Redirect URL from SWAYAM Plus Settings |
| User ID Property | `sub` |
| Auth URL Data | `{"response_type": "code", "scope": "openid email profile"}` |
| Client ID and Client Secret | The SWAYAM sign-in credential. Do not store these on SWAYAM Plus Settings. |

Open **SWAYAM Plus Settings**, enable it, save once, and copy the generated values:

| SWAYAM Plus field | Settings field |
|---|---|
| Sign-in redirect URL | Redirect URL |
| Auto sign-in URL | Auto Sign-in URL |

Use the same Base URL host that SWAYAM sends as `iss`. The check is `{Base URL}/oidc`.

## What a launch does

1. SWAYAM opens the Auto Sign-in URL with `iss`, `target_link_uri`, and optional `login_hint` and `lti_message_hint`.
2. A guest is sent through the Social Login Key. Frappe creates or matches the user and logs them in.
3. The browser returns to `ensure_swayam_enrollment`, which creates an LMS Enrollment for `/lms/courses/<course-id>` when that course exists and the learner is not already enrolled.
4. The learner lands on the course URL. A URL on another site is replaced with `/lms`.
