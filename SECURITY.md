# Security Policy — E2ScreenRecorder

## Supported Versions

| Version | Supported |
|---|---|
| 1.0.1 | ✅ Active |
| 1.0.0 | ⚠️ Upgrade recommended (pre-audit; known vulnerabilities) |

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Report privately to: **samo.hossam@gmail.com**  
Subject line: `[E2ScreenRecorder] Security: <brief description>`

Expected response time: 48 hours.  
For confirmed vulnerabilities a patched release will be issued within 7 days.

## Known Fixed Vulnerabilities (v1.0.0 → v1.0.1)

### VULN-001 — Shell Injection in install.sh (Fixed in v1.0.1)

**Severity:** Medium  
**Vector:** Local — requires attacker-controlled `/dev/fb*` path in config  
**Description:** `install.sh` passed the `FB_DEVICE` config value directly to
`sed -i` without sanitization. A path containing shell metacharacters could
trigger arbitrary command execution during install or reinstall.  
**Fix:** `sed` replaced with a Python one-liner that performs only string
substitution with no shell expansion of the substitution value.

## Scope

This plugin runs as root on a set-top box on a private home LAN.
The WebIF binds to `0.0.0.0` on the configured port (default 8765).
There is no authentication on the WebIF — by design, it is intended for
trusted LAN use only. **Do not expose the WebIF port to the internet.**

If you need authentication, configure your router/firewall to block the
WebIF port from the WAN, or change the port to something non-standard.
