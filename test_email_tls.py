"""streamlit_app_monitor.py send_email_report TLS: the client must verify smtp.gmail.com's certificate before it sends the app password.

A local fake SMTP server offers TLS (STARTTLS) with a certificate minted per test by the openssl CLI. The
client's connection to smtp.gmail.com is redirected to it, so hostname checks still run against the real name.
Run: uv run python -m unittest -q test_email_tls"""

import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import contextlib
import io
from datetime import datetime, timezone

import streamlit_app_monitor

HOST, PORT = "smtp.gmail.com", 587


def _openssl(*args: str) -> None:
    subprocess.run(["openssl", *args], check=True, capture_output=True)


def _ca(d: Path, name: str) -> tuple[Path, Path]:
    key, cert = d / f"{name}.key", d / f"{name}.pem"
    _openssl(
        "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", f"/CN={name}",
        "-keyout", str(key), "-out", str(cert),
        "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign",
    )  # fmt: skip
    return cert, key


def _leaf(d: Path, ca: tuple[Path, Path], host: str) -> tuple[Path, Path]:
    key, csr, cert, ext = d / f"{host}.key", d / f"{host}.csr", d / f"{host}.pem", d / f"{host}.ext"
    ext.write_text(
        f"subjectAltName=DNS:{host}\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,"
        "keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n"
    )
    _openssl("req", "-newkey", "rsa:2048", "-nodes", "-subj", f"/CN={host}", "-keyout", str(key), "-out", str(csr))
    _openssl(
        "x509", "-req", "-in", str(csr), "-CA", str(ca[0]), "-CAkey", str(ca[1]), "-CAcreateserial",
        "-days", "2", "-extfile", str(ext), "-out", str(cert),
    )  # fmt: skip
    return cert, key


class FakeSMTP(threading.Thread):
    """One-connection SMTP server: TLS with the given certificate (implicit on 465, else after STARTTLS), then
    accepts any AUTH and message. Records each command, and "TLS" when the handshake starts."""

    def __init__(self, cert: tuple[Path, Path]) -> None:
        super().__init__(daemon=True)
        self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.tls.load_cert_chain(*cert)
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.listener.settimeout(10)
        self.port = self.listener.getsockname()[1]
        self.commands: list[str] = []

    def run(self) -> None:
        conn, _ = self.listener.accept()
        conn.settimeout(10)
        buf, secure = b"", False
        try:
            if PORT == 465:
                self.commands.append("TLS")
                conn, secure = self.tls.wrap_socket(conn, server_side=True), True
            conn.sendall(b"220 fake ESMTP\r\n")
            while True:
                while b"\r\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buf += chunk
                line, buf = buf.split(b"\r\n", 1)
                verb = line.split(b" ", 1)[0].upper().decode()
                self.commands.append(verb)
                if verb == "EHLO":
                    conn.sendall(b"250-fake\r\n250 AUTH PLAIN LOGIN\r\n" if secure else b"250-fake\r\n250 STARTTLS\r\n")
                elif verb == "STARTTLS":
                    conn.sendall(b"220 go ahead\r\n")
                    self.commands.append("TLS")
                    conn, secure = self.tls.wrap_socket(conn, server_side=True), True
                elif verb == "AUTH":
                    conn.sendall(b"235 accepted\r\n")
                elif verb == "DATA":
                    conn.sendall(b"354 end with .\r\n")
                    while b"\r\n.\r\n" not in buf:
                        buf += conn.recv(4096)
                    buf = buf.split(b"\r\n.\r\n", 1)[1]
                    conn.sendall(b"250 queued\r\n")
                elif verb == "QUIT":
                    conn.sendall(b"221 bye\r\n")
                    return
                else:
                    conn.sendall(b"250 ok\r\n")
        except (ssl.SSLError, OSError):
            return
        finally:
            conn.close()
            self.listener.close()


def send() -> str | None:
    """Send one report without reading .env; return the printed failure if the certificate check refused the server."""
    out = io.StringIO()
    result = {"status": "awake", "url": "https://app.example.test", "timestamp": "2026-01-01T12:00:00+00:00"}
    with mock.patch.object(streamlit_app_monitor, "load_dotenv"), contextlib.redirect_stdout(out):
        streamlit_app_monitor.send_email_report([result], datetime.now(timezone.utc))
    refused = [line for line in out.getvalue().splitlines() if "CERTIFICATE_VERIFY_FAILED" in line]
    return refused[0] if refused else None


class CertificateVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not shutil.which("openssl"):
            raise AssertionError("these tests need the openssl CLI on PATH")
        cls.tmp = tempfile.TemporaryDirectory()
        d = Path(cls.tmp.name)
        trusted, rogue = _ca(d, "trusted-ca"), _ca(d, "rogue-ca")
        (d / "rogue").mkdir()
        cls.trusted_ca = trusted[0]
        cls.leaves = {
            "right_host": _leaf(d, trusted, HOST),
            "wrong_host": _leaf(d, trusted, "wrong-host.example.test"),
            "untrusted": _leaf(d / "rogue", rogue, HOST),
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def send_through(self, leaf: str) -> tuple[object, list[str]]:
        """Run send() against a fake server presenting `leaf`, trusting only the test CA."""
        server = FakeSMTP(self.leaves[leaf])
        server.start()
        real_connect = socket.create_connection

        def to_fake(address, *args, **kwargs):
            assert address == (HOST, PORT), address
            return real_connect(("127.0.0.1", server.port), *args, **kwargs)

        env = {
            "SSL_CERT_FILE": str(self.trusted_ca),
            "SSL_CERT_DIR": str(self.trusted_ca.parent / "no-system-certs"),
            "GMAIL_USER": "alerts@example.test",
            "GMAIL_APP_PASSWORD": "test-app-password",
        }
        with mock.patch.object(socket, "create_connection", to_fake), mock.patch.dict(os.environ, env):
            error = send()
        server.join(timeout=15)
        self.assertFalse(server.is_alive(), "fake SMTP server did not finish")
        return error, server.commands

    def test_refuses_untrusted_certificate(self) -> None:
        error, commands = self.send_through("untrusted")
        self.assertIn("TLS", commands)  # the TLS step was reached, so the refusal is the certificate check
        self.assertIsNotNone(error)
        self.assertNotIn("AUTH", commands)

    def test_refuses_wrong_host_certificate(self) -> None:
        error, commands = self.send_through("wrong_host")
        self.assertIn("TLS", commands)
        self.assertIsNotNone(error)
        self.assertNotIn("AUTH", commands)

    def test_sends_with_trusted_certificate_for_the_right_host(self) -> None:
        error, commands = self.send_through("right_host")
        self.assertIsNone(error)
        self.assertEqual([c for c in commands if c in ("TLS", "AUTH", "DATA")], ["TLS", "AUTH", "DATA"])


if __name__ == "__main__":
    unittest.main()
