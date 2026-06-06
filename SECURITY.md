# Security

## Trust model

ocular runs on a LAN-only camera node (raspo) and is reached two ways:

- **`https://ocular.<domain>`** — through raspi's Traefik, behind **oauth2-proxy
  forward-auth** (Kanidm SSO). ocular trusts `X-Auth-Request-User` /
  `X-Auth-Request-Email` *when present*, never logs them (PII), and has **no
  login/session of its own** and no Kanidm OIDC client.
- **`http://<raspo-ip>:8099`** — direct on the LAN, for tuning. No TLS/auth; the
  node is LAN-only and egress-restricted.

`GET /status` is an unauthenticated liveness probe (for gatus); it exposes no
data beyond `{status, synthetic}`.

## Boundaries

- **Egress**: `ocular` is in the `raspi` repo's `network_restrict.py` RESTRICTED
  list — it can reach the LAN (and raspi's hub/ntfy) but not the internet.
- **Filesystem**: the systemd unit runs `ProtectSystem=strict` with a single
  writable path (`/var/lib/ocular`) plus camera devices.
- **No secrets**: ocular holds none in v1 (edge auth). If a webhook token is
  added later it comes from `/etc/secrets/ocular.env` (written by the raspi
  deploy), never committed.
- **Camera**: the feed and stored frames stay on-device / on the LAN; nothing is
  sent off-host.

## Reporting

Personal project — open an issue.
