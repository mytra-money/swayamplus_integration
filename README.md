# SWAYAM Plus Integration for Frappe LMS

Minimal, standards-first integration connecting **Frappe LMS** with **SWAYAM Plus** using Frappe's built-in **Social Login Key**, **Integration Request**, background jobs, and `LMS Enrollment` hooks.

## Features

- **Learner Sign-in (OIDC + Auto Sign-in):** Uses Frappe's built-in `Social Login Key` (`swayam_plus`) with a lightweight launch endpoint (`start_swayam_login`) that validates `iss`, forwards `login_hint`, and auto-enrolls the learner on arrival.
- **Minimal Schema:** Adds only **1 custom field** (`swayam_enrollment_id`) on `LMS Enrollment` and **1 Single DocType** (`SWAYAM Plus Settings`).
- **Partner API Client (`api.py`):** OAuth 2.0 `client_credentials` token flow cached in `frappe.cache` (with automatic `401` refresh) for:
  - Connection check (`ping`)
  - Reading enrollments (`list_enrollments`, `list_all_enrollments`, `get_student_enrollments`)
  - Reporting progress & completion (`report_progress`, `confirm_completion`)
- **Automated Progress & Completion Sync:** Subscribes to `LMS Enrollment` `on_change` and enqueues background jobs (`enqueue_after_commit=True`) to push `progress` (`0–100`) and confirm completion at `100%`.
- **Standard Logging:** Every Partner API request is logged in Frappe's built-in **Integration Request** (`Service = SWAYAM Plus`) with URL, masked headers, request data, and response output/errors.

---

## Installation

```bash
bench get-app https://github.com/mytra-money/swayamplus_integration.git
bench --site <your-site> install-app swayam_plus_integration
bench --site <your-site> migrate
```

Ensure `bench worker` is running so background progress/completion sync jobs execute.

---

## Setup Guide

### 1. Configure Frappe Social Login Key (Learner Sign-in)

1. In the **SWAYAM Plus Partner Portal → Integration → Learner sign-in (SSO)**, create a sign-in credential.
2. In Frappe Desk, create a **Social Login Key** with:
   - **Provider Name / ID**: `swayam_plus`
   - **Enable Social Login**: Checked
   - **Base URL**: `https://swayamplus.education.gov.in/oidc`
   - **Authorize URL**: `/auth`
   - **Access Token URL**: `/token`
   - **API Endpoint**: `/me`
   - **Client ID / Client Secret**: From SWAYAM Plus sign-in credential
   - **User ID Property**: `sub`
   - **Scope**: `openid email profile`
   - **Email Verification**: Disabled (SWAYAM Plus verifies learner emails)
3. Register the **Redirect URL** (`/api/method/frappe.integrations.oauth2_logins.login_via_swayam_plus`) and **Auto sign-in URL** (`/api/method/swayam_plus_integration.sso.start_swayam_login`) on your SWAYAM Plus sign-in credential.

### 2. Configure SWAYAM Plus Settings

1. In the **SWAYAM Plus Partner Portal → Integration → API access**, create an API credential with `partner.enrollments:read` and `partner.completions:write`.
2. In Frappe Desk, open **SWAYAM Plus Settings**:
   - **Enabled**: Checked
   - **Base URL**: `https://swayamplus.education.gov.in/oidc`
   - **API Client ID** & **API Client Secret**: Paste from your SWAYAM Plus API credential.
   - Save.

### 3. Course Mapping

Set each SWAYAM Plus course's **Partner Course ID** to match the `LMS Course` document `name` (URL slug) in Frappe LMS.

---

## APIs & Hooks Reference

| Component | Purpose |
| :--- | :--- |
| `swayam_plus_integration.sso.start_swayam_login` | Guest Auto sign-in URL (`iss`, `login_hint`, `target_link_uri`, `lti_message_hint`). |
| `swayam_plus_integration.sso.ensure_swayam_enrollment` | Post-login callback that links `LMS Enrollment` with `swayam_enrollment_id`. |
| `swayam_plus_integration.api.ping()` | Calls `GET /api/v1/partner/ping` to verify API credentials. |
| `swayam_plus_integration.api.list_enrollments(page, limit)` | Calls `GET /api/v1/partner/enrollments`. |
| `swayam_plus_integration.api.list_all_enrollments()` | Paginates through all enrollment pages until `meta.hasNext` is `False`. |
| `swayam_plus_integration.api.get_student_enrollments(sub)` | Calls `GET /api/v1/partner/students/{sub}/enrollments`. |
| `swayam_plus_integration.api.report_progress(enrollment_id, percent)` | Calls `POST /api/v1/partner/enrollments/{enrollmentId}/progress`. |
| `swayam_plus_integration.api.confirm_completion(enrollment_id)` | Calls `POST /api/v1/partner/enrollments/{enrollmentId}/completion`. |
| `LMS Enrollment` `on_change` | Enqueues `sync_progress` in the background whenever `progress` changes on a SWAYAM enrollment. |

### CLI Examples

```bash
# Test API connection
bench --site <your-site> execute swayam_plus_integration.api.ping

# Fetch all enrollments
bench --site <your-site> execute swayam_plus_integration.api.list_all_enrollments
```
