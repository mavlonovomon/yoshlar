import base64
import datetime

from django.test import TestCase

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID


def make_test_pfx(password="test1234", pinfl="12345678901234", expired=False):
    """Self-signed test sertifikat va PFX yasaydi."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "TESTOV TEST TEST"),
        x509.NameAttribute(NameOID.SERIAL_NUMBER, pinfl),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    not_before = now - datetime.timedelta(days=365) if expired else now - datetime.timedelta(days=1)
    not_after = now - datetime.timedelta(days=1) if expired else now + datetime.timedelta(days=365)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .sign(key, hashes.SHA256())
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"test",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
    )
    return key, cert, base64.b64encode(pfx_bytes).decode()


class LoadPfxTests(TestCase):
    def test_loads_valid_pfx(self):
        from auth.eimzo.pkcs12 import load_pfx

        key, cert, pfx_b64 = make_test_pfx()
        loaded_key, loaded_cert, error = load_pfx(pfx_b64, "test1234")
        self.assertIsNone(error)
        self.assertIsNotNone(loaded_key)
        self.assertIsNotNone(loaded_cert)
        self.assertEqual(loaded_cert.serial_number, cert.serial_number)

    def test_wrong_password_rejected(self):
        from auth.eimzo.pkcs12 import load_pfx

        _key, _cert, pfx_b64 = make_test_pfx(password="right-pass")
        loaded_key, loaded_cert, error = load_pfx(pfx_b64, "wrong-pass")
        self.assertIsNone(loaded_key)
        self.assertIsNone(loaded_cert)
        self.assertIn("Parol xato", error)

    def test_garbage_input_rejected(self):
        from auth.eimzo.pkcs12 import load_pfx

        bad_b64 = base64.b64encode(b"not a pfx file at all").decode()
        loaded_key, loaded_cert, error = load_pfx(bad_b64, "test1234")
        self.assertIsNone(loaded_key)
        self.assertIsNone(loaded_cert)
        self.assertIsNotNone(error)

    def test_invalid_base64_rejected(self):
        from auth.eimzo.pkcs12 import load_pfx

        loaded_key, loaded_cert, error = load_pfx("!!!not-base64!!!", "test1234")
        self.assertIsNone(loaded_key)
        self.assertIsNone(loaded_cert)
        self.assertIsNotNone(error)


class SignNonceTests(TestCase):
    def test_produces_parseable_signed_data(self):
        from asn1crypto import cms as asn1_cms

        from auth.eimzo.cms_signer import sign_nonce

        key, cert, _pfx = make_test_pfx()
        nonce = b"abc123nonce"
        cms_der = sign_nonce(nonce, key, cert)

        content_info = asn1_cms.ContentInfo.load(cms_der)
        self.assertEqual(content_info["content_type"].native, "signed_data")
        signed_data = content_info["content"]
        encap = signed_data["encap_content_info"]
        self.assertEqual(encap["content_type"].native, "data")
        self.assertEqual(bytes(encap["content"].native), nonce)
        self.assertEqual(len(signed_data["signer_infos"]), 1)

    def test_signature_verifies_with_public_key(self):
        from asn1crypto import cms as asn1_cms
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.serialization import Encoding

        from auth.eimzo.cms_signer import sign_nonce

        key, cert, _pfx = make_test_pfx()
        nonce = b"another-nonce-42"
        cms_der = sign_nonce(nonce, key, cert)

        content_info = asn1_cms.ContentInfo.load(cms_der)
        signed_data = content_info["content"]
        signer_info = signed_data["signer_infos"][0]
        signed_attrs = signer_info["signed_attrs"]
        signature = signer_info["signature"].native

        cert.public_key().verify(
            signature,
            signed_attrs.dump(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )

        md_attr = [
            a["values"][0].native
            for a in signed_attrs
            if a["type"].native == "message_digest"
        ][0]
        import hashlib
        self.assertEqual(md_attr, hashlib.sha256(nonce).digest())

    def test_wrong_key_type_raises_clear_error(self):
        from auth.eimzo.cms_signer import sign_nonce

        class FakeKey:
            def sign(self, *args, **kwargs):
                raise TypeError("unsupported")

        key, cert, _pfx = make_test_pfx()
        with self.assertRaises(TypeError):
            sign_nonce(b"x", FakeKey(), cert)


class VerifyCmsSignatureTests(TestCase):
    def test_roundtrip_ok(self):
        import base64 as b64mod

        from auth.eimzo.cms_signer import sign_nonce
        from auth.eimzo.verifier import verify_cms_signature

        key, cert, _pfx = make_test_pfx(pinfl="12345678901234")
        nonce = "nonce-value-777"
        cms_b64 = b64mod.b64encode(sign_nonce(nonce.encode(), key, cert)).decode()

        is_valid, cert_info, error = verify_cms_signature(cms_b64, nonce)
        self.assertTrue(is_valid, error)
        self.assertEqual(cert_info.get("pinfl"), "12345678901234")
        self.assertIn("TESTOV", cert_info.get("cn", "") + cert_info.get("subject", ""))

    def test_nonce_mismatch_rejected(self):
        import base64 as b64mod

        from auth.eimzo.cms_signer import sign_nonce
        from auth.eimzo.verifier import verify_cms_signature

        key, cert, _pfx = make_test_pfx()
        cms_b64 = b64mod.b64encode(sign_nonce(b"real-nonce", key, cert)).decode()

        is_valid, _info, error = verify_cms_signature(cms_b64, "tampered-nonce")
        self.assertFalse(is_valid)
        self.assertIn("mos emas", error)

    def test_tampered_signature_rejected(self):
        import base64
        from asn1crypto import cms as asn1_cms

        from auth.eimzo.cms_signer import sign_nonce
        from auth.eimzo.verifier import verify_cms_signature

        key, cert, _pfx = make_test_pfx()
        cms_der = bytearray(sign_nonce(b"some-nonce", key, cert))
        # oxirgi baytlar signature joyida — bitta baytni buzamiz (DER oxiri signature octets)
        cms_der[-1] ^= 0xFF
        try:
            tampered_b64 = base64.b64encode(bytes(cms_der)).decode()
            is_valid, _info, error = verify_cms_signature(tampered_b64, "some-nonce")
        except Exception:
            is_valid, error = False, "parse error"
        self.assertFalse(is_valid)

    def test_garbage_rejected(self):
        import base64

        from auth.eimzo.verifier import verify_cms_signature

        garbage_b64 = base64.b64encode(b"garbage-data-here").decode()
        is_valid, _info, error = verify_cms_signature(garbage_b64, "n")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
