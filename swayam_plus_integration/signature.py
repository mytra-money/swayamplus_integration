"""SWAYAM Plus webhook signature checks. This module does not import Frappe."""

import hashlib
import hmac
import time

SIGNATURE_TOLERANCE_SECONDS = 300


def verify_signature(header, raw_body, secrets, now=None):
	"""Return True when one v1 signature matches a secret and the timestamp is fresh.

	Header format: t=<unix seconds>,v1=<hex hmac>[,v1=<hex hmac>]
	Signed payload: "{timestamp}.{raw body}"
	HMAC-SHA256, hex encoded. Comparison is constant-time per candidate.
	"""
	if not header or not secrets:
		return False

	timestamp, candidates = _parse_header(header)
	if timestamp is None or not candidates:
		return False

	current = time.time() if now is None else now
	if abs(current - timestamp) > SIGNATURE_TOLERANCE_SECONDS:
		return False

	if isinstance(raw_body, str):
		raw_body = raw_body.encode()

	signed = f"{int(timestamp)}.".encode() + (raw_body or b"")
	for secret in secrets:
		if not secret:
			continue
		expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
		for candidate in candidates:
			if hmac.compare_digest(expected, candidate):
				return True
	return False


def _parse_header(header):
	timestamp = None
	candidates = []
	for part in header.split(","):
		part = part.strip()
		if part.startswith("t="):
			try:
				timestamp = int(part[2:])
			except ValueError:
				return None, []
		elif part.startswith("v1="):
			value = part[3:].strip().lower()
			if len(value) == 64:
				candidates.append(value)
	return timestamp, candidates
