#!/usr/bin/env python3
"""Read-only Confluence release-record snapshots and comparisons."""
import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ENDPOINTS = SKILL_DIR / "config" / "endpoints.json"
ZJIRA_CONFIG = Path.home() / ".config" / "zjira" / "config.yaml"
SECRETS = Path.home() / ".config" / "opencode" / "release-sync.json"
ENDPOINT_KEYS = ("confluence_url",)


def load_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"invalid JSON {path}: {exc}")
    if not isinstance(value, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return value


def endpoints():
    return load_json(ENDPOINTS) if ENDPOINTS.exists() else {}


def set_endpoint(key, value):
    if key not in ENDPOINT_KEYS:
        raise SystemExit(f"unknown endpoint '{key}'; expected: {', '.join(ENDPOINT_KEYS)}")
    data = endpoints()
    data[key] = value.rstrip("/")
    ENDPOINTS.parent.mkdir(parents=True, exist_ok=True)
    ENDPOINTS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(ENDPOINTS, 0o600)


def resolve_url(cli):
    if cli:
        return cli.rstrip("/")
    if os.environ.get("CONFLUENCE_URL"):
        return os.environ["CONFLUENCE_URL"].strip().rstrip("/")
    if endpoints().get("confluence_url"):
        return endpoints()["confluence_url"].rstrip("/")
    raise SystemExit(f"missing confluence_url; run --set-endpoint confluence_url=<url> or set CONFLUENCE_URL")


def yaml_config():
    result = {}
    if ZJIRA_CONFIG.exists():
        for line in ZJIRA_CONFIG.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
            if match and match.group(2).strip():
                result[match.group(1)] = match.group(2).strip().strip('"').strip("'")
    if SECRETS.exists():
        overlay = load_json(SECRETS)
        result.update({k: v for k, v in overlay.items() if isinstance(v, str) and v})
    return result


def api(base, token, path):
    request = urllib.request.Request(
        base + path,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except Exception as exc:
        raise SystemExit(f"Confluence read failed: {exc}")


def resolve_page(base, token, reference):
    ref = reference.strip()
    if ref.isdigit():
        return api(base, token, f"/rest/api/content/{ref}?expand=body.storage,version,space")
    match = re.search(r"[?&]pageId=(\d+)", ref)
    if match:
        return resolve_page(base, token, match.group(1))
    match = re.search(r"/display/([^/?#]+)/([^?#]+)", ref)
    if match:
        query = urllib.parse.urlencode({
            "spaceKey": urllib.parse.unquote_plus(match.group(1)),
            "title": urllib.parse.unquote_plus(match.group(2)),
            "expand": "body.storage,version,space",
        })
        result = api(base, token, "/rest/api/content?" + query).get("results", [])
        if result:
            return result[0]
    raise SystemExit(f"cannot resolve Confluence page: {reference}")


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
        self.link = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            self.table = []
        elif tag == "tr" and self.table is not None:
            self.row = []
        elif tag in ("th", "td") and self.row is not None:
            self.cell = {"text": [], "links": []}
        elif tag == "a" and self.cell is not None:
            self.link = attrs.get("href")

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "a":
            self.link = None
        elif tag in ("th", "td") and self.cell is not None:
            if self.link:
                self.cell["links"].append(self.link)
            self.cell["text"] = " ".join("".join(self.cell["text"]).split())
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if self.table is not None and self.row:
                self.table.append(self.row)
            self.row = None
        elif tag == "table" and self.table is not None:
            if self.table:
                self.tables.append(self.table)
            self.table = None


def normal(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip().lower()


def extract_services(body):
    parser = TableParser()
    parser.feed(body)
    rows = []
    for table in parser.tables:
        if not table:
            continue
        headers = [normal(cell["text"]) for cell in table[0]]
        indexes = {}
        for index, header in enumerate(headers):
            if header in ("service", "service name", "project"):
                indexes.setdefault("service", index)
            elif header in ("version", "current version", "release tag", "docker image"):
                indexes.setdefault(header, index)
        if "service" not in indexes:
            continue
        for row in table[1:]:
            if len(row) <= indexes["service"]:
                continue
            service = row[indexes["service"]]["text"].strip()
            if not service or normal(service) in ("service", "total"):
                continue
            item = {"service": service}
            for key, index in indexes.items():
                if key != "service":
                    item[key] = row[index]["text"].strip() if index < len(row) else ""
            rows.append(item)
    if not rows:
        raise SystemExit("no service table found; expected a Service column in the page")
    result = {}
    for item in rows:
        result[item.pop("service")] = item
    return result


def page_url(page, base):
    links = page.get("_links", {})
    if links.get("webui"):
        return (links.get("base") or base).rstrip("/") + links["webui"]
    return f"{base}/pages/viewpage.action?pageId={page['id']}"


def snapshot(base, token, page_ref, project):
    page = resolve_page(base, token, page_ref)
    return {
        "schema": 1,
        "captured_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": {
            "type": "confluence",
            "page_id": str(page["id"]),
            "page_title": page.get("title", ""),
            "page_version": page.get("version", {}).get("number"),
            "page_url": page_url(page, base),
            "space": page.get("space", {}).get("key"),
            "project": project,
        },
        "services": extract_services(page.get("body", {}).get("storage", {}).get("value", "")),
    }


def print_snapshot(data):
    source = data["source"]
    print(f"page: {source['page_title']} (id {source['page_id']}, Confluence v{source['page_version']})")
    print(f"captured: {data['captured_at']}")
    print("| Service | Current version | Release Tag | Docker image |")
    print("|---|---|---|---|")
    for service, values in data["services"].items():
        print(f"| {service} | {values.get('current version', '')} | {values.get('release tag', '')} | {values.get('docker image', '')} |")


def compare(before, current):
    old = before["services"]
    new = current["services"]
    changed = 0
    for service in sorted(set(old) | set(new)):
        if service not in old:
            print(f"NEW_SERVICE | {service}")
            changed += 1
            continue
        if service not in new:
            print(f"MISSING_SERVICE | {service}")
            changed += 1
            continue
        fields = sorted(set(old[service]) | set(new[service]))
        diffs = [f"{field}: '{old[service].get(field, '')}' -> '{new[service].get(field, '')}'" for field in fields if old[service].get(field, '') != new[service].get(field, '')]
        if diffs:
            print(f"RECORDED_CHANGE | {service} | " + "; ".join(diffs))
            changed += 1
        else:
            print(f"UNCHANGED_RECORD | {service}")
    print(f"\nConfluence record comparison: {'CHANGED' if changed else 'UNCHANGED'}")
    print("This result describes the release page record; it does not verify a running deployment.")


def main():
    parser = argparse.ArgumentParser(description="Read-only Confluence release-record audit")
    parser.add_argument("--set-endpoint", metavar="KEY=VALUE")
    parser.add_argument("--confluence-url")
    sub = parser.add_subparsers(dest="command")
    for name in ("snapshot", "compare"):
        command = sub.add_parser(name)
        command.add_argument("--page", required=True)
        command.add_argument("--project")
    sub.choices["snapshot"].add_argument("--output", required=True)
    sub.choices["compare"].add_argument("--before", required=True)
    args = parser.parse_args()
    if args.set_endpoint:
        if "=" not in args.set_endpoint:
            raise SystemExit("--set-endpoint requires KEY=VALUE")
        key, value = args.set_endpoint.split("=", 1)
        set_endpoint(key, value)
        print(f"saved {key} to {ENDPOINTS}")
        return
    if not args.command:
        parser.error("a command is required: snapshot or compare")
    cfg = yaml_config()
    token = cfg.get("confluence_token") or cfg.get("token")
    if not token:
        raise SystemExit("missing Confluence token in ~/.config/zjira/config.yaml or release-sync.json")
    base = resolve_url(args.confluence_url)
    current = snapshot(base, token, args.page, args.project)
    if args.command == "snapshot":
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.chmod(output, 0o600)
        print_snapshot(current)
        print(f"snapshot: {output}")
    else:
        before = load_json(Path(args.before).expanduser())
        print_snapshot(current)
        print()
        compare(before, current)


if __name__ == "__main__":
    main()
