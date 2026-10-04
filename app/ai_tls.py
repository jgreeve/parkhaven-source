"""Endpoint-scoped private CA trust plus exact certificate identity checks."""

import hashlib
import hmac
import http.client
import json
import os
from pathlib import Path
import re
import ssl
from urllib import parse, request

CONFIG_ROOT = Path(__file__).resolve().parents[1] / "config"
DEFAULT_TRUST_CONFIG = (CONFIG_ROOT / "ai-trust.local.json"
                        if (CONFIG_ROOT / "ai-trust.local.json").is_file()
                        else CONFIG_ROOT / "ai-trust.json")


class EndpointTrustError(ValueError):
    pass


def _origin(url):
    parsed = parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise EndpointTrustError("AI-endpoint moet een geldige URL zonder gebruikersnaam of wachtwoord zijn.")
    try:
        return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise EndpointTrustError("AI-endpoint bevat een ongeldige poort.") from exc


class _SameOriginRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # urllib otherwise forwards Authorization to a redirected host, including
        # an HTTP downgrade. Keep the API key inside its original HTTPS origin.
        if _origin(req.full_url) != _origin(newurl):
            raise EndpointTrustError("AI-server verwijst naar een andere host, poort of protocol. Gebruik het directe API-endpoint.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, fingerprint, **kwargs):
        self.fingerprint = fingerprint
        super().__init__(*args, **kwargs)

    def connect(self):
        # This validates the certificate chain/dates before checking exact identity.
        # HTTP headers and body are not sent until connect() returns successfully.
        super().connect()
        actual = hashlib.sha256(self.sock.getpeercert(binary_form=True)).hexdigest()
        if not hmac.compare_digest(actual, self.fingerprint):
            self.close()
            raise ssl.SSLCertVerificationError(
                "Het AI-servercertificaat is gewijzigd: SHA-256 komt niet overeen met de vertrouwde configuratie.")


class _PinnedHTTPSHandler(request.HTTPSHandler):
    def __init__(self, context, origin, fingerprint):
        super().__init__(context=context)
        self.origin = origin
        self.fingerprint = fingerprint

    def https_open(self, req):
        if _origin(req.full_url) != self.origin:
            raise EndpointTrustError("Privécertificaat mag alleen voor het geconfigureerde AI-endpoint worden gebruikt.")

        def connection(host, **kwargs):
            return _PinnedHTTPSConnection(host, fingerprint=self.fingerprint, **kwargs)

        return self.do_open(connection, req, context=self._context)


def build_ai_opener(url, *, config_path=None):
    origin = _origin(url)
    path = Path(config_path or os.environ.get("PARKHAVEN_AI_TRUST_CONFIG", DEFAULT_TRUST_CONFIG))
    try:
        profiles = json.loads(path.read_text(encoding="utf-8"))["endpoints"] if path.is_file() else []
        if not isinstance(profiles, list):
            raise ValueError("endpoints moet een lijst zijn")
        for profile in profiles:
            trusted_origin = _origin(profile["origin"])
            if trusted_origin != origin:
                continue
            if origin[0] != "https":
                raise ValueError("privécertificaten vereisen HTTPS")
            fingerprint = profile["certificate_sha256"].lower()
            if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                raise ValueError("ongeldige SHA-256-certificaatvingerafdruk")
            ca_file = path.parent / profile["ca_file"]
            context = ssl.create_default_context()
            context.load_verify_locations(cafile=str(ca_file))
            # Private deployments may have a CN such as 'openwebui' rather than
            # an IP SAN. Only here does an exact, origin-bound certificate pin
            # replace the hostname check. CERT_REQUIRED remains enabled.
            context.check_hostname = False
            return request.build_opener(_SameOriginRedirects(), _PinnedHTTPSHandler(context, origin, fingerprint))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise EndpointTrustError("AI-certificaatconfiguratie kon niet worden geladen: " + str(exc)) from exc
    # Public/unconfigured endpoints retain normal system CA and hostname checks.
    return request.build_opener(_SameOriginRedirects())


def open_ai_request(http_request, timeout=120):
    return build_ai_opener(http_request.full_url).open(http_request, timeout=timeout)
