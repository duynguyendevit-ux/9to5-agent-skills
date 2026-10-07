#!/usr/bin/env python3
"""Resolve Confluence PAT configuration and check it without printing secrets."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


class ConfigError(ValueError):
    """Safe error whose message contains no config values or parser excerpts."""


def default_paths():
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "zjira/config.yaml", root / "opencode/release-sync.json"


def read_mapping(path: Path, kind: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
        if kind == "yaml":
            try:
                import yaml
            except ImportError:
                raise ConfigError("PyYAML is required to read the zjira config") from None
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
    except FileNotFoundError:
        return {}
    except ConfigError:
        raise
    except Exception:
        raise ConfigError(f"Cannot read or parse {kind} configuration; values withheld") from None
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a mapping in {kind} configuration; values withheld")
    return {k: v.strip() for k, v in data.items()
            if isinstance(k, str) and isinstance(v, str) and v.strip()}


def read_dotfiles(config_path=None, overlay_path=None):
    default_config, default_overlay = default_paths()
    config = read_mapping(Path(config_path or default_config), "yaml")
    sources = {k: "zjira-config" for k in config}
    overlay = read_mapping(Path(overlay_path or default_overlay), "json")
    config.update(overlay)
    sources.update({k: "release-sync-overlay" for k in overlay})
    return config, sources


def validate_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or any(c.isspace() for c in value)):
            raise ValueError
        parsed.port
    except ValueError:
        raise ConfigError("Invalid Confluence base URL; value withheld") from None
    return value.rstrip("/")


def resolve(config_path=None, overlay_path=None, endpoints_path=None,
            cli_url=None, env=None):
    env = os.environ if env is None else env
    config, sources = read_dotfiles(config_path, overlay_path)
    endpoints = read_mapping(Path(endpoints_path), "json") if endpoints_path else {}
    url, url_source = None, None
    for candidate, source in ((cli_url, "cli"), (env.get("CONFLUENCE_URL"), "environment"),
                              (endpoints.get("confluence_url"), "local-endpoints"),
                              (config.get("confluence_url"), sources.get("confluence_url"))):
        if isinstance(candidate, str) and candidate.strip():
            url, url_source = validate_url(candidate.strip()), source
            break
    token, token_source = None, None
    # Preserve the existing REST helper policy: dotfile PATs before env fallback.
    for key in ("confluence_token", "token"):
        if config.get(key):
            token, token_source = config[key], sources[key] + ":" + key
            break
    if not token and isinstance(env.get("CONFLUENCE_TOKEN"), str):
        token = env["CONFLUENCE_TOKEN"].strip() or None
        token_source = "environment:CONFLUENCE_TOKEN" if token else None
    if token and ("\r" in token or "\n" in token):
        raise ConfigError("Invalid PAT header value; value withheld")
    return url, token, {"url_present": bool(url), "token_present": bool(token),
                        "url_source": url_source, "token_source": token_source}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a PAT to a login page or a different origin.
        return None


def opener():
    return urllib.request.build_opener(NoRedirect())


def check(url, token, transport=None):
    if not url or not token:
        return {"status": "missing-config", "verified": False, "login_needed": True}
    request = urllib.request.Request(url + "/rest/api/user/current", headers={
        "Authorization": "Bearer " + token, "Accept": "application/json"})
    try:
        with (transport or opener()).open(request, timeout=20) as response:
            if response.status != 200:
                return {"status": "unverified", "verified": False,
                        "login_needed": False, "http_status": response.status}
            body = response.read(65537)
            if len(body) > 65536:
                return {"status": "invalid-response", "verified": False, "login_needed": False}
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError
            if data.get("type") == "anonymous":
                return {"status": "unauthenticated", "verified": False,
                        "login_needed": True, "http_status": 200}
            known = data.get("type") == "known" or bool(data.get("userKey") or data.get("username"))
            return {"status": "authenticated" if known else "unverified",
                    "verified": bool(known), "login_needed": False, "http_status": 200}
    except urllib.error.HTTPError as exc:
        exc.close()
        label = {401: "unauthenticated", 403: "forbidden"}.get(exc.code, "unverified")
        if 300 <= exc.code < 400:
            label = "redirect-blocked"
        return {"status": label, "verified": False,
                "login_needed": exc.code == 401, "http_status": exc.code}
    except (ValueError, UnicodeError):
        return {"status": "invalid-response", "verified": False, "login_needed": False}
    except Exception:
        return {"status": "network-error", "verified": False, "login_needed": False}


def run(args, *, interactive=None, login_runner=None):
    def inspect():
        try:
            url, token, report = resolve(args.config, args.overlay, args.endpoints,
                                         args.confluence_url)
        except ConfigError as exc:
            return {"status": "config-error", "verified": False,
                    "login_needed": False, "reason": str(exc)}
        if not url or not token or args.check or args.login_if_needed:
            report.update(check(url, token))
        else:
            report.update(status="configured", verified=False, login_needed=False)
        return report

    report = inspect()
    if report.get("login_needed"):
        report["login_command"] = "zjira init"
    if not args.login_if_needed or not report.get("login_needed"):
        return report
    default_config, _ = default_paths()
    if args.config and Path(args.config).expanduser().resolve() != default_config.resolve():
        report.update(status="custom-config-login-required", login_attempted=False)
        return report
    interactive = (sys.stdin.isatty() and sys.stdout.isatty()) if interactive is None else interactive
    if not interactive:
        report.update(status="needs-interactive-login", login_attempted=False)
        return report
    binary = shutil.which("zjira")
    if not binary:
        report.update(status="cli-missing", login_attempted=False)
        return report
    try:
        result = (login_runner or subprocess.run)([binary, "init"], check=False)
    except OSError:
        report.update(status="login-failed", login_attempted=True)
        return report
    if result.returncode:
        report.update(status="login-failed", login_attempted=True)
        return report
    report = inspect()  # Reload dotfiles; verify, never assume the TUI succeeded.
    report["login_attempted"] = True
    if report.get("login_needed"):
        report["login_command"] = "zjira init"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="explicit zjira YAML path")
    parser.add_argument("--overlay", type=Path, help="optional release-sync JSON path")
    parser.add_argument("--endpoints", type=Path, help="optional local endpoints JSON path")
    parser.add_argument("--confluence-url", help="explicit base URL (never inferred from history)")
    parser.add_argument("--check", action="store_true", help="read-only Confluence auth check")
    parser.add_argument("--login-if-needed", action="store_true",
                        help="run zjira init only for missing/401 auth in an interactive terminal")
    args = parser.parse_args()
    report = run(args)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] in ("configured", "authenticated") else 2


if __name__ == "__main__":
    raise SystemExit(main())
