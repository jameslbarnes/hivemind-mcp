#!/usr/bin/env python3
"""Generate self-signed SSL certificate for local HTTPS testing."""

from OpenSSL import crypto
from pathlib import Path

def generate_self_signed_cert():
    """Generate a self-signed certificate and key."""

    # Generate key
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)

    # Generate certificate
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "State"
    cert.get_subject().L = "City"
    cert.get_subject().O = "Hivemind"
    cert.get_subject().OU = "MCP"
    cert.get_subject().CN = "localhost"
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365*24*60*60)  # Valid for 1 year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')

    # Save files
    cert_dir = Path(__file__).parent / "certs"
    cert_dir.mkdir(exist_ok=True)

    with open(cert_dir / "cert.pem", "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))

    with open(cert_dir / "key.pem", "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

    print(f"✓ Certificate generated in {cert_dir}")
    print("  - cert.pem")
    print("  - key.pem")
    print("\nTo use, run the server with:")
    print("  python src/remote_mcp_server.py --ssl")

if __name__ == "__main__":
    try:
        generate_self_signed_cert()
    except ImportError:
        print("Error: pyOpenSSL not installed")
        print("Install with: pip install pyOpenSSL")
