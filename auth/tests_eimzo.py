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
