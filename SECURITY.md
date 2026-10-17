# Security

Keep Codex authentication, API credentials, original materials, private books,
runtime logs, databases and notes outside this repository.

For a suspected vulnerability, use GitHub private vulnerability reporting when
available. Otherwise open an Issue requesting a private reporting channel without
including exploit details, credentials or private source material.

Production deployments should bind the application to loopback, require an
authenticated owner at the reverse proxy and application, and keep uploaded code
as material rather than execute it.
