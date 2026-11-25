# Phase 2

Phase 1 has SWAYAM Plus Settings (including the API Access credential fields), Social Login sign-in, and LMS enrollment. Webhook Log and Entitlement are not in the app. The partner API client is not wired yet.

## Add later

1. A client that uses API Client ID / Secret from Settings to list enrollments, report progress, and confirm completion.
2. SWAYAM Plus Entitlement and SWAYAM Plus Webhook Log.
3. A signed webhook receiver. On `enrollment.activated`, store the entitlement and enroll the learner when their SWAYAM `sub` is already linked. On `enrollment.revoked`, set SWAYAM Plus Access Ended. On `enrollment.completed`, mark the entitlement completed.
4. After Social Login, link entitlements that arrived before the first sign-in. Match `User Social Login` where provider is `swayam_plus`.
5. An LMS Enrollment `on_change` hook that posts progress, and posts completion once at 100 percent.
6. If SWAYAM rejects the Social Login token call because PKCE or `nonce` is missing, that gap is in Frappe Social Login, not in this enrollment step.
