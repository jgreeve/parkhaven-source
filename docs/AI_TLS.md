# Private HTTPS certificates for AI endpoints

Deployment-specific AI endpoints and certificate identities must not be committed.
The tracked `config/ai-trust.json` is intentionally empty. Copy
`config/ai-trust.example.json` to the ignored `config/ai-trust.local.json`, then
enter the values supplied by the server administrator.

```json
{
  "endpoints": [
    {
      "origin": "https://ai.internal.example",
      "ca_file": "certificates/ai.internal.example.pem",
      "certificate_sha256": "replace-with-64-lowercase-hex-characters"
    }
  ]
}
```

The certificate file must contain only the approved public CA/server certificate,
never a private key. Files under `config/certificates/*.pem` are ignored. An
alternative trust file can be selected with `PARKHAVEN_AI_TRUST_CONFIG`; relative
`ca_file` paths resolve beside that JSON file.

## Verification model

- A profile maps one exact HTTPS origin (scheme, hostname/IP and port) to a public
  certificate/CA file and expected leaf-certificate SHA-256 fingerprint.
- Certificate-chain and validity-date checks remain required.
- For an explicitly configured private profile, the exact fingerprint is checked
  during TLS setup before HTTP headers, API keys or project data are sent.
- A changed certificate fails closed, even when signed by a trusted issuer.
- Other origins retain system-CA and hostname verification.
- Redirects to another host, port or protocol are rejected.

## Credential-free check

Provide the deployment endpoint without storing it in source control:

```powershell
$env:PARKHAVEN_AI_ENDPOINT = "https://ai.internal.example/v1"
.\.venv\Scripts\python.exe .\scripts\verify_ai_tls.py
```

An HTTP 401/403 after successful TLS proves only connectivity and authentication
enforcement. It does not prove API-key permissions, vision input, JSON output or
model inference. Never paste credentials into shell history, documentation, issues,
logs or repository files.

When a certificate is renewed, obtain the new public certificate and fingerprint
through an authenticated administrative channel. Update only the local/deployment
profile; the client never automatically accepts changed certificate identity.
