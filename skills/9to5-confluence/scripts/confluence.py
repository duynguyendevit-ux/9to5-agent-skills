#!/usr/bin/env python3
"""General Confluence page operations for the 9to5 skills.

Reads and writes Confluence through the REST API, using the same credentials the
zjira CLI already stores. Every write is a dry run until `--apply --approved`.

    confluence.py search  --cql 'space = X and title ~ "y"'
    confluence.py get     --page <id|url> [--body]
    confluence.py children|ancestors|labels --page <id|url>
    confluence.py create  --space KEY --title T --body-file F [--parent <id|url>]
    confluence.py update  --page <id|url> --body-file F [--title T]
    confluence.py comment --page <id|url> --text '...'
    confluence.py set-labels --page <id|url> [--add a,b] [--remove c]
    confluence.py attach  --page <id|url> --file PATH [--comment '...']

Never prints the token. Internal hostnames come from config/endpoints.json (gitignored)
or the zjira config; there is no hardcoded fallback.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ENDPOINTS_PATH = SKILL_DIR / "config" / "endpoints.json"
AUTH_PATH = SKILL_DIR.parent / "9to5-confluence-auth" / "scripts" / "auth.py"
if not AUTH_PATH.is_file():
    sys.exit("Missing sibling skill 9to5-confluence-auth; install it alongside 9to5-confluence")
_auth_spec = importlib.util.spec_from_file_location("confluence_auth", AUTH_PATH)
AUTH = importlib.util.module_from_spec(_auth_spec)
_auth_spec.loader.exec_module(AUTH)
ZJIRA_CONFIG, SECRETS_PATH = AUTH.default_paths()
ENDPOINT_KEYS = ("confluence_url", "confluence_space")
EXPAND = "body.storage,version,space,ancestors,metadata.labels"


# ---------------------------------------------------------------- configuration

def load_endpoints() -> dict:
    try:
        return {k: v for k, v in AUTH.read_mapping(ENDPOINTS_PATH, "json").items()
                if not k.startswith("_")}
    except AUTH.ConfigError as exc:
        sys.exit(str(exc))


def save_endpoint(key: str, value: str) -> Path:
    if key not in ENDPOINT_KEYS:
        sys.exit(f"unknown endpoint '{key}'; expected one of: {', '.join(ENDPOINT_KEYS)}")
    data = load_endpoints()
    data[key] = value.rstrip("/")
    ENDPOINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENDPOINTS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(ENDPOINTS_PATH, 0o600)
    return ENDPOINTS_PATH


def zjira_config() -> dict:
    try:
        return AUTH.read_dotfiles(ZJIRA_CONFIG, SECRETS_PATH)[0]
    except AUTH.ConfigError as exc:
        sys.exit(str(exc))


def resolve_url(cli_value: str | None) -> str:
    try:
        url, _, _ = AUTH.resolve(ZJIRA_CONFIG, SECRETS_PATH, ENDPOINTS_PATH, cli_value)
    except AUTH.ConfigError as exc:
        sys.exit(str(exc))
    if url:
        return url
    sys.exit("missing confluence_url: ask the user for the internal URL, then persist it with\n"
             f"  {Path(__file__).name} --set-endpoint confluence_url=<url>")


def resolve_space(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    if os.environ.get("CONFLUENCE_SPACE"):
        return os.environ["CONFLUENCE_SPACE"].strip()
    if load_endpoints().get("confluence_space"):
        return load_endpoints()["confluence_space"]
    if zjira_config().get("confluence_space"):
        return zjira_config()["confluence_space"]
    sys.exit("missing space: pass --space <KEY> or persist it with "
             f"{Path(__file__).name} --set-endpoint confluence_space=<KEY>")


def resolve_token(cli_value: str | None = None) -> str:
    try:
        _, token, _ = AUTH.resolve(ZJIRA_CONFIG, SECRETS_PATH, ENDPOINTS_PATH, cli_value)
    except AUTH.ConfigError as exc:
        sys.exit(str(exc))
    if not token:
        sys.exit("missing Confluence PAT; use 9to5-confluence-auth to check config "
                 "and run authorized interactive zjira init if needed")
    return token


# ------------------------------------------------------------------- transport

def api(base: str, token: str, method: str, path: str, payload=None,
        headers: dict | None = None, raw: bytes | None = None) -> dict:
    request_headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    data = raw
    if payload is not None:
        data = json.dumps(payload).encode()
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(base + path, method=method, data=data,
                                     headers=request_headers)
    try:
        with AUTH.opener().open(request, timeout=120) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        exc.close()
        sys.exit(f"{method} failed: HTTP {exc.code}; response withheld. "
                 "Check 9to5-confluence-auth for missing/401 credentials; "
                 "redirects are blocked.")
    except Exception as exc:
        sys.exit(f"{method} failed: {type(exc).__name__}; details withheld")


def page_url(page: dict, base: str) -> str:
    links = page.get("_links", {})
    if links.get("webui"):
        return (links.get("base") or base).rstrip("/") + links["webui"]
    return f"{base}/pages/viewpage.action?pageId={page['id']}"


def resolve_page(base: str, token: str, ref: str, expand: str = EXPAND) -> dict:
    ref = str(ref).strip()
    if ref.isdigit():
        return api(base, token, "GET", f"/rest/api/content/{ref}?expand={expand}")
    match = re.search(r"[?&]pageId=(\d+)", ref)
    if match:
        return resolve_page(base, token, match.group(1), expand)
    match = re.search(r"/display/([^/?#]+)/([^?#]+)", ref)
    if match:
        query = urllib.parse.urlencode({
            "spaceKey": urllib.parse.unquote_plus(match.group(1)),
            "title": urllib.parse.unquote_plus(match.group(2)),
            "expand": expand,
        })
        results = api(base, token, "GET", "/rest/api/content?" + query).get("results", [])
        if results:
            return results[0]
    sys.exit(f"cannot resolve page reference: {ref}")


def cql(base: str, token: str, query: str, limit: int = 50) -> list:
    results, start = [], 0
    while len(results) < limit:
        batch = min(100, limit - len(results))
        params = urllib.parse.urlencode({
            "cql": query, "limit": batch, "start": start, "expand": "version,space",
        })
        page = api(base, token, "GET", "/rest/api/content/search?" + params)
        results.extend(page.get("results", []))
        if not page.get("_links", {}).get("next") or not page.get("results"):
            break
        start += len(page["results"])
    return results[:limit]


def read_body_file(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8")


def body_payload(text: str, fmt: str) -> dict:
    representation = "wiki" if fmt == "wiki" else "storage"
    return {representation: {"value": text, "representation": representation}}


# ----------------------------------------------------------------- write gate

def gate(args, method: str, path: str, summary: list[str], payload=None,
         headers: dict | None = None, raw: bytes | None = None):
    """Print the exact request, then send it only with --apply --approved."""
    print(f"{method} {args.base}{path}")
    for line in summary:
        print(f"  {line}")
    if payload is not None:
        print("  payload: " + json.dumps(payload, ensure_ascii=False, indent=2))
    if raw is not None:
        print(f"  body: {len(raw)} bytes (multipart)")
    if not args.apply:
        print("\ndry run: nothing sent. Show this to the user, then re-run with --apply --approved.")
        return None
    if not args.approved:
        sys.exit("refusing --apply without --approved: show the plan to the user and get "
                 "explicit approval for it first")
    return api(args.base, args.token, method, path, payload=payload, headers=headers, raw=raw)


# ------------------------------------------------------------------- commands

def cmd_search(args):
    rows = cql(args.base, args.token, args.cql, args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("no results")
        return
    print(f"{len(rows)} result(s)")
    for page in rows:
        version = page.get("version", {}).get("number")
        when = (page.get("version", {}).get("when") or "")[:10]
        print(f"  {page['id']:>10}  v{version:<4} {when}  {page.get('title', '')}")
        print(f"              {page_url(page, args.base)}")


def cmd_get(args):
    page = resolve_page(args.base, args.token, args.page)
    if args.json:
        print(json.dumps(page, ensure_ascii=False, indent=2))
        return
    space = page.get("space", {}).get("key")
    print(f"title:   {page.get('title')}")
    print(f"id:      {page['id']}")
    print(f"space:   {space}")
    print(f"version: {page.get('version', {}).get('number')} "
          f"({(page.get('version', {}).get('when') or '')[:19]})")
    print(f"url:     {page_url(page, args.base)}")
    ancestors = [a.get("title") for a in page.get("ancestors", [])]
    if ancestors:
        print(f"path:    {' / '.join(ancestors)}")
    labels = [l.get("name") for l in page.get("metadata", {}).get("labels", {}).get("results", [])]
    if labels:
        print(f"labels:  {', '.join(labels)}")
    if args.body:
        body = page.get("body", {}).get("storage", {}).get("value", "")
        print(f"--- body ({len(body)} chars, storage format) ---")
        print(body)


def cmd_children(args):
    parent = resolve_page(args.base, args.token, args.page, "version")
    rows = cql(args.base, args.token, f"parent = {parent['id']} and type = page", args.limit)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print(f"children of {parent.get('title')} ({parent['id']}): {len(rows)}")
    for page in sorted(rows, key=lambda p: p.get("title", "")):
        print(f"  {page['id']:>10}  {page.get('title', '')}")


def cmd_ancestors(args):
    page = resolve_page(args.base, args.token, args.page, "version,ancestors")
    chain = [(a.get("id"), a.get("title")) for a in page.get("ancestors", [])]
    chain.append((page["id"], page.get("title")))
    if args.json:
        print(json.dumps(chain, ensure_ascii=False, indent=2))
        return
    for index, (pid, title) in enumerate(chain):
        print(f"  {'  ' * index}{pid:>10}  {title}")


def cmd_labels(args):
    page = resolve_page(args.base, args.token, args.page, "version,metadata.labels")
    current = [l.get("name") for l in page.get("metadata", {}).get("labels", {}).get("results", [])]
    if args.json:
        print(json.dumps(current, ensure_ascii=False, indent=2))
        return
    print(f"labels on {page['id']}: {', '.join(current) if current else '(none)'}")


def cmd_create(args):
    space = resolve_space(args.space)
    text = read_body_file(args.body_file)
    payload = {
        "type": "page",
        "title": args.title,
        "space": {"key": space},
        "body": body_payload(text, args.format),
    }
    if args.parent:
        parent = resolve_page(args.base, args.token, args.parent, "version")
        payload["ancestors"] = [{"id": parent["id"]}]
    summary = [f"space: {space}", f"title: {args.title}",
               f"body: {len(text)} chars ({args.format})"]
    if args.parent:
        summary.append(f"parent: {payload['ancestors'][0]['id']}")
    result = gate(args, "POST", "/rest/api/content", summary, payload=payload)
    if result:
        print(f"created page {result['id']}: {page_url(result, args.base)}")


def cmd_update(args):
    page = resolve_page(args.base, args.token, args.page, "version")
    if page["version"]["number"] != args.expected_version:
        sys.exit(f"page changed: expected version {args.expected_version}, found "
                 f"{page['version']['number']}; re-read, rebase and review the body before retrying")
    text = read_body_file(args.body_file)
    title = args.title or page.get("title")
    payload = {
        "id": page["id"],
        "type": "page",
        "title": title,
        "version": {"number": args.expected_version + 1},
        "body": body_payload(text, args.format),
    }
    summary = [f"title: {title} (was {page.get('title')})",
               f"version: {page['version']['number']} -> {payload['version']['number']}",
               f"body: {len(text)} chars ({args.format})"]
    result = gate(args, "PUT", f"/rest/api/content/{page['id']}", summary, payload=payload)
    if result:
        print(f"updated page {result['id']} to version {result['version']['number']}")
        print(f"re-read it to confirm the render: {page_url(result, args.base)}")


def cmd_comment(args):
    page = resolve_page(args.base, args.token, args.page, "version")
    text = args.text if args.text else read_body_file(args.body_file)
    payload = {
        "type": "comment",
        "container": {"id": page["id"], "type": "page"},
        "body": body_payload(text, args.format),
    }
    summary = [f"page: {page['id']} ({page.get('title')})",
               f"comment: {len(text)} chars ({args.format})"]
    result = gate(args, "POST", "/rest/api/content", summary, payload=payload)
    if result:
        print(f"comment {result['id']} added to page {page['id']}")


def cmd_set_labels(args):
    page = resolve_page(args.base, args.token, args.page, "version,metadata.labels")
    add = [l.strip() for l in (args.add or "").split(",") if l.strip()]
    remove = [l.strip() for l in (args.remove or "").split(",") if l.strip()]
    if not add and not remove:
        sys.exit("nothing to do: pass --add and/or --remove")
    current = [l.get("name") for l in page.get("metadata", {}).get("labels", {}).get("results", [])]
    summary = [f"page: {page['id']} ({page.get('title')})",
               f"current: {', '.join(current) if current else '(none)'}",
               f"add: {', '.join(add) if add else '(none)'}",
               f"remove: {', '.join(remove) if remove else '(none)'}"]
    if add:
        payload = [{"prefix": "global", "name": name} for name in add]
        gate(args, "POST", f"/rest/api/content/{page['id']}/label", summary, payload=payload)
    if remove:
        # Confluence Server/DC exposes removeLabel at this path; verify once against
        # your instance before relying on it in a batch.
        for name in remove:
            gate(args, "DELETE",
                 f"/rest/api/content/{page['id']}/label/{urllib.parse.quote(name)}",
                 [f"remove label: {name}"])


def cmd_attach(args):
    page = resolve_page(args.base, args.token, args.page, "version")
    for path in args.file:
        source = Path(path).expanduser()
        if not source.is_file():
            sys.exit(f"not a file: {source}")
        content = source.read_bytes()
        content_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        existing = api(args.base, args.token, "GET",
                       f"/rest/api/content/{page['id']}/child/attachment?"
                       + urllib.parse.urlencode({"filename": source.name})).get("results", [])
        boundary = "----opencode" + uuid.uuid4().hex
        parts = []
        if args.comment:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"comment\"\r\n\r\n"
                         f"{args.comment}\r\n".encode())
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{source.name}\"\r\nContent-Type: {content_type}\r\n\r\n".encode()
            + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        raw = b"".join(parts)
        if existing:
            path_url = (f"/rest/api/content/{page['id']}/child/attachment/"
                        f"{existing[0]['id']}/data")
            action = "replace existing attachment"
        else:
            path_url = f"/rest/api/content/{page['id']}/child/attachment"
            action = "add new attachment"
        summary = [f"page: {page['id']} ({page.get('title')})",
                   f"file: {source.name} ({len(content)} bytes, {content_type})",
                   action]
        gate(args, "POST", path_url, summary, raw=raw,
             headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                      "X-Atlassian-Token": "no-check"})


# ----------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Confluence page operations (dry run by default)")
    parser.add_argument("--confluence-url")
    parser.add_argument("--set-endpoint", metavar="KEY=VALUE")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command")

    def add(name, help_text):
        command = sub.add_parser(name, help=help_text)
        return command

    def add_write_flags(command):
        command.add_argument("--apply", action="store_true", help="send the request")
        command.add_argument("--approved", action="store_true",
                             help="confirms the user approved the dry-run plan")

    p = add("search", "search with CQL")
    p.add_argument("--cql", required=True)
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(func=cmd_search)

    p = add("get", "page metadata, optionally the body")
    p.add_argument("--page", required=True)
    p.add_argument("--body", action="store_true")
    p.set_defaults(func=cmd_get)

    for name, func in (("children", cmd_children), ("ancestors", cmd_ancestors),
                       ("labels", cmd_labels)):
        p = add(name, f"{name} of a page")
        p.add_argument("--page", required=True)
        p.add_argument("--limit", type=int, default=100)
        p.set_defaults(func=func)

    p = add("create", "create a page (dry run by default)")
    p.add_argument("--space")
    p.add_argument("--parent")
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True, help="storage XHTML, or '-' for stdin")
    p.add_argument("--format", choices=("storage", "wiki"), default="storage")
    add_write_flags(p)
    p.set_defaults(func=cmd_create)

    p = add("update", "replace a page body (dry run by default)")
    p.add_argument("--page", required=True)
    p.add_argument("--expected-version", type=int, required=True,
                   help="version of the page body used to prepare the reviewed replacement")
    p.add_argument("--title")
    p.add_argument("--body-file", required=True)
    p.add_argument("--format", choices=("storage", "wiki"), default="storage")
    add_write_flags(p)
    p.set_defaults(func=cmd_update)

    p = add("comment", "add a comment (dry run by default)")
    p.add_argument("--page", required=True)
    p.add_argument("--text")
    p.add_argument("--body-file")
    p.add_argument("--format", choices=("storage", "wiki"), default="storage")
    add_write_flags(p)
    p.set_defaults(func=cmd_comment)

    p = add("set-labels", "add or remove page labels (dry run by default)")
    p.add_argument("--page", required=True)
    p.add_argument("--add")
    p.add_argument("--remove")
    add_write_flags(p)
    p.set_defaults(func=cmd_set_labels)

    p = add("attach", "attach files to a page (dry run by default)")
    p.add_argument("--page", required=True)
    p.add_argument("--file", action="append", required=True)
    p.add_argument("--comment")
    add_write_flags(p)
    p.set_defaults(func=cmd_attach)

    args = parser.parse_args()

    if args.set_endpoint:
        if "=" not in args.set_endpoint:
            sys.exit("--set-endpoint requires KEY=VALUE")
        key, value = args.set_endpoint.split("=", 1)
        print(f"saved {key} to {save_endpoint(key, value)}")
        return
    if not args.command:
        parser.error("a command is required; see --help")

    args.base = resolve_url(args.confluence_url)
    args.token = resolve_token(args.confluence_url)
    args.func(args)


if __name__ == "__main__":
    main()
