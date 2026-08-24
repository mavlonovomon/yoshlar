"""Nonce ustiga server tomonda CMS (PKCS#7) SignedData yasash."""
from __future__ import annotations

import datetime
import hashlib

from asn1crypto import algos, cms, core
from asn1crypto import x509 as asn1_x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import Encoding


def sign_nonce(data: bytes, private_key, certificate) -> bytes:
    """
    data (masalan nonce utf-8 baytlari) ustiga attached CMS SignedData yasaydi.
    Qaytaradi: DER formatidagi ContentInfo baytlari.
    """
    message_digest = hashlib.sha256(data).digest()

    signed_attrs = cms.CMSAttributes([
        cms.CMSAttribute({
            "type": cms.CMSAttributeType("content_type"),
            "values": [cms.ContentType("data")],
        }),
        cms.CMSAttribute({
            "type": cms.CMSAttributeType("signing_time"),
            "values": [core.UTCTime(datetime.datetime.now(datetime.timezone.utc))],
        }),
        cms.CMSAttribute({
            "type": cms.CMSAttributeType("message_digest"),
            "values": [core.OctetString(message_digest)],
        }),
    ])

    issuer_and_serial = cms.IssuerAndSerialNumber({
        "issuer": asn1_x509.Name.load(certificate.subject.public_bytes()),
        "serial_number": certificate.serial_number,
    })

    signer_info = cms.SignerInfo({
        "version": "v1",
        "sid": cms.SignerIdentifier({"issuer_and_serial_number": issuer_and_serial}),
        "digest_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
        "signed_attrs": signed_attrs,
        "signature_algorithm": algos.SignedDigestAlgorithm({
            "algorithm": "rsassa_pkcs1v15",
        }),
        "signature": b"",
    })

    # RFC 5652 §11.2: imzo implicit [0] tegli signed_attrs DER baytlari ustida
    # qo'yiladi (ContentInfo DER ichidagi encoding bilan aynan bir xil bo'lishi kerak).
    to_sign = signer_info["signed_attrs"].dump()
    signature = private_key.sign(
        to_sign,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    signer_info["signature"] = signature

    der_cert = certificate.public_bytes(Encoding.DER)
    signed_data = cms.SignedData({
        "version": "v1",
        "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
        "encap_content_info": {
            "content_type": cms.ContentType("data"),
            "content": core.OctetString(data),
        },
        "certificates": [
            cms.CertificateChoices(("certificate", asn1_x509.Certificate.load(der_cert)))
        ],
        "signer_infos": [signer_info],
    })

    content_info = cms.ContentInfo({
        "content_type": cms.ContentType("signed_data"),
        "content": signed_data,
    })
    return content_info.dump()
