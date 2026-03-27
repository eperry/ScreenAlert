"""
TLS certificate management for the ScreenAlert MCP server.

Auto-generates a self-signed EC 256 certificate for localhost / 127.0.0.1.
Regenerates automatically if the cert file is missing or expired.
"""

import datetime
import logging
import os

logger = logging.getLogger(__name__)


def ensure_cert(cert_path: str, key_path: str) -> None:
    """
    Ensure a valid self-signed TLS cert and key exist at the given paths.
    Generates new ones if either file is missing or the cert is expired.
    """
    if _cert_is_valid(cert_path):
        logger.debug("TLS cert is valid: %s", cert_path)
        return

    logger.info("Generating new self-signed TLS certificate: %s", cert_path)
    _generate_cert(cert_path, key_path)


def cert_fingerprint(cert_path: str) -> str:
    """
    Return the SHA-256 fingerprint of the certificate at cert_path.
    Returns empty string if the file does not exist or cannot be read.
    """
    if not os.path.exists(cert_path):
        return ""
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        import binascii

        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        raw = cert.fingerprint(hashes.SHA256())
        return "sha256:" + binascii.hexlify(raw).decode()
    except Exception as exc:
        logger.error("Failed to read cert fingerprint: %s", exc)
        return ""


def cert_expiry(cert_path: str) -> str:
    """Return the ISO 8601 expiry date of the cert, or empty string on error."""
    if not os.path.exists(cert_path):
        return ""
    try:
        from cryptography import x509

        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return cert.not_valid_after_utc.date().isoformat()
    except Exception as exc:
        logger.error("Failed to read cert expiry: %s", exc)
        return ""


# ── Internal ──────────────────────────────────────────────────────────────────

def _cert_is_valid(cert_path: str) -> bool:
    """Return True if the cert file exists and is not expired."""
    if not os.path.exists(cert_path):
        return False
    try:
        from cryptography import x509

        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        now = datetime.datetime.now(datetime.timezone.utc)
        return cert.not_valid_after_utc > now
    except Exception:
        return False


def _generate_cert(cert_path: str, key_path: str) -> None:
    """Generate a self-signed EC 256 cert valid for 10 years."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    import ipaddress

    # Generate EC private key
    key = ec.generate_private_key(ec.SECP256R1())

    now = datetime.datetime.now(datetime.timezone.utc)
    expires = now + datetime.timedelta(days=365 * 10)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "ScreenAlert MCP"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ScreenAlert"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(expires)
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
            ]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )

    os.makedirs(os.path.dirname(cert_path), exist_ok=True)

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.info(
        "TLS cert generated: expires=%s fingerprint=%s",
        expires.date().isoformat(),
        cert_fingerprint(cert_path),
    )
