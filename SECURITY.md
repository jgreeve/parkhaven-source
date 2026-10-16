# Security policy

Report suspected vulnerabilities privately to a repository administrator; do not open
a public issue or disclose project files, models, credentials, endpoints, logs, or
screenshots.

Never commit API keys, session tokens, private keys, user project workspaces,
generated model evidence, deployment-specific endpoints, or local trust profiles.
Use `config/ai-trust.local.json` or `PARKHAVEN_AI_TRUST_CONFIG` for private AI trust
configuration. User API keys remain request-only and must not be stored.

Before every release, scan the exact staged tree and release artifacts for secrets,
personal paths, debug symbols, copied Rhino assemblies, project models and logs.
