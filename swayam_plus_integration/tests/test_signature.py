import unittest

from swayam_plus_integration.signature import verify_signature

# Official test vector from the SWAYAM Plus webhook guide.
SECRET = "whsec_test"
TIMESTAMP = 1759276800
BODY = b'{"id":"d1","type":"ping"}'
SIGNATURE = "69abe2ce3897ce74def9ec7fa0349ae6e00af8f8c7745b03d9e0e545358e3734"


class TestWebhookSignature(unittest.TestCase):
	def test_official_vector(self):
		header = f"t={TIMESTAMP},v1={SIGNATURE}"
		self.assertTrue(verify_signature(header, BODY, [SECRET], now=TIMESTAMP))

	def test_rejects_bad_signature(self):
		header = f"t={TIMESTAMP},v1={'ab' * 32}"
		self.assertFalse(verify_signature(header, BODY, [SECRET], now=TIMESTAMP))

	def test_rejects_stale_timestamp(self):
		header = f"t={TIMESTAMP},v1={SIGNATURE}"
		self.assertFalse(verify_signature(header, BODY, [SECRET], now=TIMESTAMP + 301))

	def test_accepts_either_secret_during_rotation(self):
		header = f"t={TIMESTAMP},v1={SIGNATURE}"
		self.assertTrue(verify_signature(header, BODY, ["old-secret", SECRET], now=TIMESTAMP))


if __name__ == "__main__":
	unittest.main()
