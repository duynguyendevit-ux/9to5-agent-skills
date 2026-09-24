#!/usr/bin/env python3
"""Sync Release Tag and Docker image cells in a C7 Confluence release page.

Targets today's release page (`NNN. DD.MM.YYYY` in space C7GSAFEDA):
- updates it when it exists
- creates it when missing (cloned from the newest daily page, numbered max+1)

Reads Confluence credentials from ~/.config/zjira/config.yaml (never prints them).
Dry-run by default; pass --apply to create/update the page.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CONFIG = Path.home() / ".config" / "zjira" / "config.yaml"
SECRETS_PATH = Path.home() / ".config" / "opencode" / "release-sync.json"
SKILL_DIR = Path(__file__).resolve().parent.parent
ENDPOINTS_PATH = SKILL_DIR / "config" / "endpoints.json"
ENDPOINT_KEYS = ("confluence_url", "git_ssh_base", "confluence_space", "jira_url")
CACHE_PATH = SKILL_DIR / "cache.json"
PROJECTS_PATH = SKILL_DIR / "projects.json"
CACHE_TTL = 120
SSH_OPTIONS = "-o BatchMode=yes -o ConnectTimeout=15"
TAG_RE = re.compile(r"^(.*?)(\d+(?:\.\d+)*)$")
DAILY_RE = re.compile(r"^(\d+)\.\s+(\d{2})\.(\d{2})\.(\d{4})$")
HL_COLOR = "#998dd9"  # purple row highlight for services that need a release


def load_endpoints():
    """Non-secret internal endpoints for this skill.

    Version control holds only `config/endpoints.example.json`. Real values live
    in `config/endpoints.json`, which is gitignored so internal hostnames never
    enter the repository. Never invent a value — ask the user first.
    """
    if not ENDPOINTS_PATH.exists():
        return {}
    try:
        data = json.loads(ENDPOINTS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        sys.exit(f"{ENDPOINTS_PATH} is not valid JSON: {exc}")
    if not isinstance(data, dict):
        sys.exit(f"{ENDPOINTS_PATH} must contain a JSON object")
    return {k: v.strip() for k, v in data.items()
            if isinstance(v, str) and v.strip() and not k.startswith("_")}


def save_endpoint(key, value):
    if key not in ENDPOINT_KEYS:
        sys.exit(f"unknown endpoint '{key}'; expected one of: {', '.join(ENDPOINT_KEYS)}")
    data = {}
    if ENDPOINTS_PATH.exists():
        data = json.loads(ENDPOINTS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            sys.exit(f"{ENDPOINTS_PATH} must contain a JSON object; fix or delete it before writing")
    data[key] = value.rstrip("/")
    ENDPOINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENDPOINTS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.chmod(ENDPOINTS_PATH, 0o600)
    return ENDPOINTS_PATH


def resolve_endpoint(key, cli_value, env_vars):
    """CLI flag -> env var -> config/endpoints.json -> ask the user."""
    if cli_value:
        return cli_value.rstrip("/")
    for var in env_vars:
        if os.environ.get(var):
            return os.environ[var].strip().rstrip("/")
    value = load_endpoints().get(key)
    if value:
        return value.rstrip("/")
    sys.exit(
        f"missing {key}: ask the user for the internal value, then persist it with\n"
        f"  {Path(__file__).name} --set-endpoint {key}=<value>\n"
        f"or write it into {ENDPOINTS_PATH}\n"
        f"(version control only ships config/endpoints.example.json; do not commit the real value)"
    )


def load_config():
    cfg = {}
    for line in CONFIG.read_text().splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
        if m and m.group(2).strip():
            cfg[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return cfg


def load_secrets():
    """zjira config, overlaid by the secrets file, then the skill endpoints config.

    `config/endpoints.json` is authoritative for non-secret keys so that
    `--set-endpoint` always takes effect. A differing `confluence_url` in the
    secrets overlay is reported rather than silently ignored.
    """
    cfg = load_config()
    overlay = {}
    if SECRETS_PATH.exists():
        try:
            overlay = json.loads(SECRETS_PATH.read_text())
        except Exception:
            overlay = {}
        for key in ("confluence_url", "confluence_token"):
            if overlay.get(key):
                cfg[key] = overlay[key]
    for key, value in load_endpoints().items():
        if key not in ("confluence_url", "confluence_space"):
            continue
        if (key == "confluence_url" and overlay.get(key)
                and overlay[key].rstrip("/") != value.rstrip("/")):
            print(f"warning: confluence_url differs between {SECRETS_PATH} and "
                  f"{ENDPOINTS_PATH}; using {ENDPOINTS_PATH}", file=sys.stderr)
        cfg[key] = value
    return cfg


def api(base, token, method, path, payload=None):
    req = urllib.request.Request(
        base + path,
        method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def page_url(page, base):
    links = page.get("_links", {})
    if links.get("webui"):
        return (links.get("base") or base).rstrip("/") + links["webui"]
    return f"{base}/pages/viewpage.action?pageId={page['id']}"


def resolve_page(base, token, ref, expand="body.storage,version"):
    ref = ref.strip()
    if ref.isdigit():
        return api(base, token, "GET", f"/rest/api/content/{ref}?expand={expand}")
    m = re.search(r"[?&]pageId=(\d+)", ref)
    if m:
        return api(base, token, "GET", f"/rest/api/content/{m.group(1)}?expand={expand}")
    m = re.search(r"/display/([^/?#]+)/([^?#]+)", ref)
    if m:
        space = urllib.parse.unquote_plus(m.group(1))
        title = urllib.parse.unquote_plus(m.group(2))
        q = urllib.parse.urlencode(
            {"spaceKey": space, "title": title, "expand": expand}
        )
        res = api(base, token, "GET", "/rest/api/content?" + q)
        if res.get("results"):
            return res["results"][0]
        sys.exit(f"page not found: {ref}")
    sys.exit(f"cannot resolve page ref: {ref}")


def cql(base, token, query, limit=100):
    q = urllib.parse.urlencode(
        {"cql": query, "limit": limit, "expand": "version", "orderby": "lastmodified desc"}
    )
    return api(base, token, "GET", "/rest/api/content/search?" + q)["results"]


def daily_date(page):
    m = DAILY_RE.match(page["title"])
    return (m.group(2), m.group(3), m.group(4)) if m else None


def find_today_page(base, token, space, day):
    q = f'space={space} and type=page and title ~ "{day.strftime("%d.%m.%Y")}"'
    wanted = (day.strftime("%d"), day.strftime("%m"), str(day.year))
    hits = [p for p in cql(base, token, q) if daily_date(p) == wanted]
    if not hits:
        return None, None
    hits.sort(key=lambda p: p["version"]["when"], reverse=True)
    warn = None
    if len(hits) > 1:
        warn = "multiple pages for this date: " + ", ".join(p["title"] for p in hits)
    return hits[0], warn


def newest_daily_page(base, token, space):
    days = [p for p in cql(base, token, f"space={space} and type=page") if daily_date(p)]
    if not days:
        sys.exit(f"no daily release page found in space {space}")
    days.sort(key=lambda p: p["version"]["when"], reverse=True)
    return days


def plan_create(base, token, space, day, template):
    days = newest_daily_page(base, token, space)
    next_no = max(int(DAILY_RE.match(p["title"]).group(1)) for p in days) + 1
    title = f"{next_no}. {day.strftime('%d.%m.%Y')}"
    tpl_ref = template or days[0]["id"]
    tpl = resolve_page(base, token, str(tpl_ref), "body.storage,version,ancestors")
    parent = tpl.get("ancestors", [{}])[-1].get("id") if tpl.get("ancestors") else None
    return {"title": title, "parent": parent, "template": tpl}


def create_page(base, token, space, plan):
    tpl = plan["template"]
    payload = {
        "type": "page",
        "title": plan["title"],
        "space": {"key": space},
        "body": {
            "storage": {
                "value": prepare_copied_release(tpl["body"]["storage"]["value"]),
                "representation": "storage",
            }
        },
    }
    if plan["parent"]:
        payload["ancestors"] = [{"id": plan["parent"]}]
    created = api(base, token, "POST", "/rest/api/content", payload)
    return api(base, token, "GET", f"/rest/api/content/{created['id']}?expand=body.storage,version")


def resolve_daily_under_root(base, token, root_ref, day, template):
    root = resolve_page(base, token, str(root_ref), "version")
    kids = cql(base, token, f"parent={root['id']}", limit=200)
    periods = []
    for p in kids:
        m = re.match(r"^\d+\.\s*(\d{2})\s*[-–]\s*(\d{4})$", p["title"])
        if m:
            periods.append((m.group(1), m.group(2), p))
    period = next(
        (p for mm, yyyy, p in periods if (mm, yyyy) == (day.strftime("%m"), str(day.year))),
        None,
    )
    if period is None:
        sys.exit(
            f"no monthly page for {day.strftime('%m-%Y')} under root '{root['title']}'; "
            "create it first (or pass --page)"
        )
    siblings = cql(base, token, f"parent={period['id']}", limit=200)
    wanted = (day.strftime("%d"), day.strftime("%m"), str(day.year))
    days = [p for p in siblings if daily_date(p)]
    days.sort(key=lambda p: p["version"]["when"], reverse=True)
    hits = [p for p in days if daily_date(p) == wanted]
    if hits:
        if len(hits) > 1:
            print("warning: multiple pages for this date: " + ", ".join(p["title"] for p in hits))
        return resolve_page(base, token, hits[0]["id"]), None

    # numbering and template come from the newest month that has daily pages
    latest_days = days
    if not latest_days:
        ordered = sorted(periods, key=lambda t: (t[1], t[0]), reverse=True)
        for mm, yyyy, p in ordered:
            if p["id"] == period["id"]:
                continue
            kids = cql(base, token, f"parent={p['id']}", limit=200)
            latest_days = [k for k in kids if daily_date(k)]
            if latest_days:
                latest_days.sort(key=lambda k: k["version"]["when"], reverse=True)
                break
    next_no = max([int(DAILY_RE.match(p["title"]).group(1)) for p in latest_days], default=0) + 1
    tpl_ref = template or (latest_days[0]["id"] if latest_days else period["id"])
    tpl = resolve_page(base, token, str(tpl_ref), "body.storage,version,ancestors")
    plan = {
        "title": f"{next_no}. {day.strftime('%d.%m.%Y')}",
        "parent": period["id"],
        "template": tpl,
    }
    return None, plan


def clear_open_tag(open_tag):
    m = re.search(r'class="([^"]*)"', open_tag)
    if m:
        classes = [c for c in m.group(1).split() if not c.startswith("highlight-")]
        if classes:
            open_tag = open_tag[:m.start()] + f'class="{" ".join(classes)}"' + open_tag[m.end():]
        else:
            start, end = m.start(), m.end()
            if start > 0 and open_tag[start - 1] == " ":
                start -= 1
            open_tag = open_tag[:start] + open_tag[end:]
    return re.sub(r'\s*data-highlight-colour="[^"]*"', "", open_tag)


def reset_copied_highlights(html):
    """A cloned service row is a baseline, not evidence of a new release.

    Preserve header/section formatting and all cell contents, including tag links.
    Only numbered service rows have inherited cell highlights removed.
    """
    def reset(match):
        row = match.group(0)
        cells = re.findall(r"(<t[dh]\b[^>]*>)(.*?)(</t[dh]>)", row, re.S)
        if len(cells) < 2 or not plain(cells[0][1]).isdigit() or not plain(cells[1][1]):
            return row
        return re.sub(r"<td\b[^>]*>", lambda cell: clear_open_tag(cell.group(0)), row)
    return re.sub(r"<tr\b[^>]*>.*?</tr>", reset, html, flags=re.S)


def prepare_copied_release(html):
    """Carry the previous release into current version before discovering new tags."""
    _, current_idx, release_idx, _ = cell_indices(html)

    def rollover(match):
        row = match.group(0)
        cells = list(re.finditer(r"(<t[dh]\b[^>]*>)(.*?)(</t[dh]>)", row, re.S))
        if len(cells) <= max(current_idx, release_idx):
            return row
        if not plain(cells[0].group(2)).isdigit():
            return row
        release = cells[release_idx].group(2)
        current = cells[current_idx]
        release_tag = tag_from_cell(release)
        if release_tag and release_tag != tag_from_cell(current.group(2)):
            # Copy the full source cell body so the label and href stay together.
            row = row[:current.start(2)] + release + row[current.end(2):]
        return row

    return reset_copied_highlights(re.sub(r"<tr\b[^>]*>.*?</tr>", rollover, html, flags=re.S))


def load_cache():
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def load_projects(path):
    if path.exists():
        try:
            return json.loads(path.read_text()).get("projects", {})
        except Exception:
            return {}
    return {}


def save_projects(path, projects):
    payload = {"projects": {k: projects[k] for k in sorted(projects)}}
    path.write_text(json.dumps(payload, indent=2) + "\n")


def save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n")


def git_context():
    """Derive the git SSH base and group from the cwd repo. Returns (None, None) when unavailable."""
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return None, None
    m = re.match(r"ssh://(?:([^@/]+)@)?([^:/]+)(?::(\d+))?/(.+?)(?:\.git)?$", url)
    if m:
        user, host, port, path = m.group(1) or "git", m.group(2), m.group(3), m.group(4)
        base = f"ssh://{user}@{host}:{port}" if port else f"ssh://{user}@{host}"
        return base, path.split("/")[0]
    m = re.match(r"(?:([^@/]+)@)?([^:/]+):(.+?)(?:\.git)?$", url)
    if m:
        user, host, path = m.group(1) or "git", m.group(2), m.group(3)
        return f"ssh://{user}@{host}", path.split("/")[0]
    return None, None


def remote_tags(git_base, repo):
    url = f"{git_base}/{repo}.git"
    env = dict(os.environ)
    env["GIT_SSH_COMMAND"] = (env.get("GIT_SSH_COMMAND", "ssh") + " " + SSH_OPTIONS).strip()
    try:
        out = subprocess.run(
            ["git", "ls-remote", "--tags", "--refs", url],
            capture_output=True, text=True, timeout=90, check=True, env=env,
        ).stdout
    except Exception as exc:
        return None, f"ls-remote failed: {exc}"
    return [line.rsplit("/", 1)[-1] for line in out.splitlines() if line.strip()], None


def newest_for_prefix(tags, prefix):
    best, best_ver = None, ()
    for tag in tags:
        if "hotfix" in tag.lower():
            continue
        if not tag.startswith(prefix):
            continue
        ver = tag[len(prefix):]
        if not re.fullmatch(r"\d+(?:\.\d+)*", ver):
            continue
        key = tuple(int(x) for x in ver.split("."))
        if key > best_ver:
            best, best_ver = tag, key
    return best


def cell_indices(html):
    header = re.search(r"<tr>.*?</tr>", html, re.S)
    version, current, release, docker = 3, 4, 5, 7
    if header:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", header.group(0), re.S)
        for i, c in enumerate(cells):
            text = re.sub(r"<[^>]+>", "", c).strip().lower()
            if text == "version":
                version = i
            elif "current version" in text:
                current = i
            elif "release tag" in text:
                release = i
            elif "docker image" in text:
                docker = i
    return version, current, release, docker


def repo_from_row(row):
    paths = re.findall(r"https?://[^/\"\s]+/([^\"\s?#]+?)(?:/-/(?:tree|tags)/|\.git)", row)
    return max(paths, key=len) if paths else None


def tag_from_cell(cell):
    m = re.search(r"([A-Za-z][\w.\-]*?)(\d+(?:\.\d+)*)(?=<|\s|$)", re.sub(r"<[^>]+>", "\n", cell))
    return m.group(0) if m else None


def plain(cell):
    return re.sub(r"<[^>]+>", "", cell).strip()


def update_release_cell(cell, old, new):
    if old not in cell:
        return cell
    link = re.compile(r'(<a[^>]*href="[^"]*/-/tags/)([^"]*)("[^>]*>)([^<]*)(</a>)')
    m = link.search(cell)
    if m:
        head, _, mid, label, tail = m.groups()
        new_label = label.replace(old, new) if "://" in label else new
        return cell[: m.start()] + head + new + mid + new_label + tail + cell[m.end():]
    return cell.replace(old, new, 1)


def update_docker_cell(cell, prefix, new):
    return re.sub(r":(" + re.escape(prefix) + r"\d+(?:\.\d+)*)", f":{new}", cell, count=1)


def page_rows(html, ver_idx, release_idx, docker_idx):
    rows = []
    for row in re.findall(r"<tr>.*?</tr>", html, re.S):
        cells = re.findall(r"(<t[dh][^>]*>)(.*?)(</t[dh]>)", row, re.S)
        if len(cells) <= max(ver_idx, release_idx, docker_idx):
            continue
        no, service = plain(cells[0][1]), plain(cells[1][1])
        if not service or service.lower() == "service":
            continue
        tag = (
            tag_from_cell(cells[ver_idx][1])
            or tag_from_cell(cells[release_idx][1])
            or tag_from_cell(cells[docker_idx][1])
            or "-"
        )
        highlight = "-"
        for c in cells:
            m = re.search(r'class="[^"]*?highlight-(#[0-9a-fA-F]{3,8})', c[0]) \
                or re.search(r'data-highlight-colour="([^"]+)"', c[0])
            if m:
                highlight = m.group(1)
                break
        rows.append((no, service, tag, highlight))
    return rows


def print_rows(label, rows):
    print(f"\n=== {label} ===")
    print("| No | Service | Tag | Highlight |")
    print("|----|---------|-----|-----------|")
    for no, service, tag, highlight in rows:
        print(f"| {no} | {service} | {tag} | {highlight} |")


def paint_open_tag(open_tag, color=HL_COLOR):
    if "data-highlight-colour" in open_tag:
        open_tag = re.sub(r'data-highlight-colour="[^"]*"', f'data-highlight-colour="{color}"', open_tag, count=1)
    else:
        open_tag = open_tag[:-1] + f' data-highlight-colour="{color}">'
    if re.search(r'class="[^"]*highlight-[^"\s]+', open_tag):
        open_tag = re.sub(r'(class="[^"]*)highlight-[^"\s]+', rf'\1highlight-{color}', open_tag, count=1)
    elif 'class="' in open_tag:
        open_tag = re.sub(r'class="', f'class="highlight-{color} ', open_tag, count=1)
    else:
        open_tag = open_tag[:-1] + f' class="highlight-{color}">'
    return open_tag


def update_page(base, token, page, body):
    """Compare against the version the replacement body was built from."""
    expected = page["version"]["number"]
    path = f"/rest/api/content/{page['id']}"
    fresh = api(base, token, "GET", path + "?expand=version")
    if fresh["version"]["number"] != expected:
        sys.exit(f"page changed since read (expected v{expected}, found "
                 f"v{fresh['version']['number']}); rerun the dry run and review again")
    return api(base, token, "PUT", path, {
        "id": page["id"], "type": "page", "title": page["title"],
        "version": {"number": expected + 1},
        "body": {"storage": {"value": body, "representation": "storage"}},
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", help="explicit page URL or ID (skips today lookup)")
    ap.add_argument("--project", help="project name from projects.json (e.g. dev-c7, dev-c7-ttdvkh)")
    ap.add_argument("--add-project", metavar="NAME",
                    help="register/update a project in the registry using --root/--group/--space/--hl-color/--page-link/--doc-link, then exit")
    ap.add_argument("--page-link", help="reference link to the project's release page (stored by --add-project)")
    ap.add_argument("--doc-link", help="reference link to the release document/space root (stored by --add-project)")
    ap.add_argument("--config", default=None, help=f"project registry path (default {PROJECTS_PATH})")
    ap.add_argument("--space", default=None, help="Confluence space key (default: the project's or config/endpoints.json)")
    ap.add_argument("--root", help="hierarchy root page URL or ID; daily pages are resolved under its monthly children")
    ap.add_argument("--date", help="release date YYYY-MM-DD (default: today)")
    ap.add_argument("--template", help="page URL or ID cloned when creating today's page")
    ap.add_argument("--no-create", action="store_true", help="fail instead of creating a missing page")
    ap.add_argument("--hl-color", default=None,
                    help=f"cell highlight for rows that need release (default {HL_COLOR} or the project's)")
    ap.add_argument("--group", help="git group to sync, e.g. c7/ttch (default: from cwd repo remote or the project's)")
    ap.add_argument("--git-base", default=None, help="ssh base URL; default: cwd repo remote or config/endpoints.json")
    ap.add_argument("--service", help="only rows whose service name contains this string")
    ap.add_argument("--paint", help="comma-separated row numbers to highlight purple, e.g. 1,2,4")
    ap.add_argument("--clear-highlight", nargs="?", const="all",
                    help="remove highlight colors: all highlighted rows, or comma-separated row numbers")
    ap.add_argument("--scan", action="store_true",
                    help="refresh every repo from git, report new services and new tags (ignores the cache)")
    ap.add_argument("--no-cache", action="store_true", help="do not read or write the repo/tag cache")
    ap.add_argument("--cache-ttl", type=int, default=CACHE_TTL,
                    help=f"seconds before a cached repo tag list is refreshed (default {CACHE_TTL})")
    ap.add_argument("--jobs", type=int, default=8,
                    help="parallel git ls-remote fetches (default 8)")
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--approved", action="store_true",
                    help="confirm the user approved the dry-run result (required with --apply)")
    ap.add_argument("--set-endpoint", metavar="KEY=VALUE",
                    help=f"persist an internal endpoint to {ENDPOINTS_PATH} and exit; keys: {', '.join(ENDPOINT_KEYS)}")
    args = ap.parse_args()

    if args.set_endpoint:
        if "=" not in args.set_endpoint:
            ap.error("--set-endpoint expects KEY=VALUE")
        key, value = args.set_endpoint.split("=", 1)
        path = save_endpoint(key.strip(), value.strip())
        print(f"saved {key.strip()} to {path}")
        return

    if args.apply and not args.approved:
        sys.exit("refusing to write: run the dry run, show the table to the user, get explicit approval, "
                 "then re-run with --apply --approved")

    cfg = load_secrets()
    base = cfg.get("confluence_url", "").rstrip("/")
    token = cfg.get("confluence_token") or cfg.get("token")
    if not base or not token:
        sys.exit("missing confluence_url/confluence_token in ~/.config/zjira/config.yaml "
                 f"or {SECRETS_PATH}")

    projects_path = Path(args.config) if args.config else PROJECTS_PATH
    projects = load_projects(projects_path)

    if args.add_project:
        space_value = resolve_endpoint("confluence_space", args.space, ("CONFLUENCE_SPACE",))
        entry = {
            "root": args.root,
            "group": args.group,
            "space": space_value,
            "hl_color": args.hl_color or HL_COLOR,
            "page_link": args.page_link,
            "doc_link": args.doc_link,
        }
        entry = {k: v for k, v in entry.items() if v}
        projects[args.add_project] = {**projects.get(args.add_project, {}), **entry}
        projects_path.parent.mkdir(parents=True, exist_ok=True)
        save_projects(projects_path, projects)
        print(f"registered project '{args.add_project}' in {projects_path}")
        for k, v in projects[args.add_project].items():
            print(f"  {k}: {v}")
        return

    git_base, cwd_group = git_context()

    project_name = args.project
    if not project_name and cwd_group:
        project_name = next((n for n, p in projects.items() if p.get("group") == cwd_group), None)
    if project_name and project_name not in projects:
        known = ", ".join(sorted(projects)) or "none"
        sys.exit(f"unknown project '{project_name}' in {projects_path} (known: {known}). "
                 "Register it with --add-project, or read the skill's Onboarding section to "
                 "collect the release page link, document link, and credentials.")
    project = projects.get(project_name, {}) if project_name else {}

    root = args.root or project.get("root")
    space = resolve_endpoint("confluence_space", args.space or project.get("space"),
                             ("CONFLUENCE_SPACE",))
    group = args.group or project.get("group") or cwd_group
    hl_color = args.hl_color or project.get("hl_color") or HL_COLOR
    if not group:
        sys.exit("no --group given, no matching project, and cannot derive a group from the current repository")

    day = datetime.date.fromisoformat(args.date) if args.date else datetime.date.today()
    cloned_page = False

    if args.page:
        page = resolve_page(base, token, args.page)
    else:
        plan = None
        if root:
            page, plan = resolve_daily_under_root(base, token, root, day, args.template)
        else:
            found, warn = find_today_page(base, token, space, day)
            if warn:
                print(f"warning: {warn}")
            page = resolve_page(base, token, found["id"]) if found else None
        if page is None:
            if args.no_create:
                sys.exit(f"no release page for {day} and --no-create given")
            if plan is None:
                plan = plan_create(base, token, space, day, args.template)
            tpl_title = plan["template"]["title"]
            if not args.apply:
                print(f"dry run: no page for {day}. Would create '{plan['title']}' "
                      f"(parent {plan['parent']}) cloned from '{tpl_title}'. Re-run with --apply.")
                print("Previous Release Tag will roll into Current version when different "
                      "(including its link). Copied service-row highlights will be cleared; only verified updates "
                      "or explicitly requested --paint rows will be highlighted again.")
                print("This is a creation preview, not a completed per-service tag check.")
                return
            page = create_page(base, token, space, plan)
            cloned_page = True
            print(f"created page '{page['title']}' (id {page['id']}) from '{tpl_title}'")
            print(f"link: {page_url(page, base)}")
        else:
            print(f"using existing page '{page['title']}' (id {page['id']})")
            print(f"link: {page_url(page, base)}")

    html = page["body"]["storage"]["value"]
    ver_idx, cur_idx, release_idx, docker_idx = cell_indices(html)

    page_row_list = []
    for row in re.findall(r"<tr>.*?</tr>", html, re.S):
        cells = re.findall(r"(<t[dh][^>]*>)(.*?)(</t[dh]>)", row, re.S)
        if len(cells) <= max(ver_idx, release_idx, docker_idx):
            continue
        no, service = plain(cells[0][1]), plain(cells[1][1])
        if not service or service.lower() == "service":
            continue
        hl = "-"
        for c in cells:
            m = re.search(r'class="[^"]*?highlight-(#[0-9a-fA-F]{3,8})', c[0]) \
                or re.search(r'data-highlight-colour="([^"]+)"', c[0])
            if m:
                hl = m.group(1)
                break
        page_row_list.append({
            "row": row, "no": no, "service": service,
            "cell_tags": [c[0] for c in cells], "highlight": hl,
        })

    git_base = resolve_endpoint("git_ssh_base", args.git_base or git_base, ("GIT_SSH_BASE",))

    cache = {} if args.no_cache else load_cache()
    cache_group = cache.setdefault(group, {})
    tag_store = cache_group.setdefault("tags", {})
    prev_repos = dict(cache_group.get("repos", {}))
    now = time.time()

    rows = re.split(r"(?=<tr>)", html)
    candidates = []
    for idx, row in enumerate(rows):
        if "<tr>" not in row:
            continue
        repo = repo_from_row(row)
        if not repo or not repo.startswith(group + "/"):
            continue
        cells = re.findall(r"(<t[dh][^>]*>)(.*?)(</t[dh]>)", row, re.S)
        if len(cells) <= max(release_idx, docker_idx):
            continue
        service = plain(cells[1][1])
        if args.service and args.service.lower() not in service.lower():
            continue
        current = tag_from_cell(cells[release_idx][1]) or tag_from_cell(cells[docker_idx][1])
        if not current:
            continue
        m = TAG_RE.match(current)
        if not m:
            continue
        prefix, old_ver = m.group(1), m.group(2)
        candidates.append(
            {
                "row": row,
                "no": plain(cells[0][1]),
                "service": service,
                "repo": repo,
                "prefix": prefix,
                "current": current,
                "release_tag": tag_from_cell(cells[release_idx][1]),
                "docker_tag": tag_from_cell(cells[docker_idx][1]),
                "version_tag": tag_from_cell(cells[ver_idx][1]),
                "current_tag": tag_from_cell(cells[cur_idx][1]),
                "release_cell": cells[release_idx][1],
                "docker_cell": cells[docker_idx][1],
                "version_cell": cells[ver_idx][1],
                "current_cell": cells[cur_idx][1],
                "cell_tags": [cells[i][0] for i in range(len(cells))],
            }
        )

    pairs = {}
    for c in candidates:
        pairs.setdefault((c["repo"], c["prefix"]), set()).add(c["current"])
    ambiguous = {p for p, cur in pairs.items() if len(cur) > 1}

    groups = {}
    for c in candidates:
        groups.setdefault((c["repo"], c["prefix"]), []).append(c)

    tags_cache, errors, new_tags = {}, [], {}
    repos = sorted({pair[0] for pair in groups})
    fetched, stale_entries, cached_repos = {}, {}, set()
    to_fetch = []
    for repo in repos:
        entry = tag_store.get(repo)
        if entry and not args.scan and not args.no_cache and now - entry.get("at", 0) < args.cache_ttl:
            fetched[repo] = (entry.get("tags", []), None)
            cached_repos.add(repo)
        else:
            to_fetch.append(repo)
            stale_entries[repo] = entry
    if to_fetch:
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            for repo, res in zip(to_fetch, pool.map(lambda r: remote_tags(git_base, r), to_fetch)):
                fetched[repo] = res
    for repo in to_fetch:
        tags, err = fetched[repo]
        if err:
            errors.append(f"{repo}: {err}")
            continue
        if tags is not None:
            entry = stale_entries.get(repo)
            if args.scan and entry:
                fresh = sorted(set(tags) - set(entry.get("tags", [])))
                if fresh:
                    new_tags[repo] = fresh
            tag_store[repo] = {"at": now, "tags": tags}
    for pair in sorted(groups):
        tags_cache[pair] = fetched.get(pair[0], (None, None))[0]

    current_repos = {c["service"]: c["repo"] for c in candidates}
    cache_group["repos"] = current_repos
    cache_group["updated_at"] = now
    if not args.service:
        keep = set(current_repos.values())
        for repo in list(tag_store):
            if repo not in keep:
                del tag_store[repo]
    if not args.no_cache:
        save_cache(cache)

    new_services = sorted(set(current_repos) - set(prev_repos))
    moved_services = sorted(
        s for s, r in current_repos.items() if s in prev_repos and prev_repos[s] != r
    )
    if args.scan:
        print("=== SCAN ===")
        counts = f"rows: {len(candidates)} | services: {len(current_repos)}"
        if not prev_repos:
            print(f"{counts} | cache initialized (no previous snapshot)")
        else:
            print(f"{counts} | new: {', '.join(new_services) or 'none'}"
                  + (f" | repo changed: {', '.join(moved_services)}" if moved_services else ""))
        if new_tags:
            for repo, tags in sorted(new_tags.items()):
                print(f"new tags [{repo}]: {', '.join(tags)}")
        else:
            print("new tags: none (or first scan for this group)")
        print()

    changes = []
    paint_nos = set()
    if args.paint:
        paint_nos = {int(x) for x in re.findall(r"\d+", args.paint)}
    for pair in sorted(groups):
        tags = tags_cache.get(pair)
        if not tags:
            continue
        newest = newest_for_prefix(tags, pair[1])
        for c in groups[pair]:
            paint = c["no"].isdigit() and int(c["no"]) in paint_nos
            if pair in ambiguous:
                changes.append({**c, "newest": newest, "fields": [],
                                "action": "paint" if paint else "SKIP ambiguous (multiple rows in repo)"})
            elif not newest:
                changes.append({**c, "newest": None, "fields": [],
                                "action": "paint" if paint else "SKIP no numeric tag"})
            else:
                fields = []
                vm = TAG_RE.match(c["version_tag"]) if c["version_tag"] else None
                if vm and vm.group(1) == c["prefix"] and c["version_tag"] != newest:
                    fields.append("version")
                    if not cloned_page and c["current_tag"] and c["current_tag"] != c["version_tag"]:
                        fields.append("current")
                if c["release_tag"] and c["release_tag"] != newest:
                    fields.append("release")
                if c["docker_tag"] and c["docker_tag"] != newest:
                    fields.append("docker")
                action = "UPDATE" if fields else ("paint" if paint else "up-to-date")
                changes.append({**c, "newest": newest, "fields": fields, "action": action})

    if paint_nos:
        matched = {int(c["no"]) for c in changes if c["no"].isdigit()}
        missing = sorted(paint_nos - matched)
        if missing:
            print(f"warning: --paint rows not found: {', '.join(map(str, missing))}")

    to_apply = [c for c in changes if c["action"] in ("UPDATE", "paint")]

    clear_targets = []
    if args.clear_highlight is not None:
        wanted = {int(x) for x in re.findall(r"\d+", args.clear_highlight)}
        update_nos = {c["no"] for c in to_apply}
        for r in page_row_list:
            if r["highlight"] == "-" or r["no"] in update_nos:
                continue
            if wanted and not (r["no"].isdigit() and int(r["no"]) in wanted):
                continue
            clear_targets.append(r)
        if wanted:
            highlighted_nos = {int(r["no"]) for r in page_row_list
                               if r["highlight"] != "-" and r["no"].isdigit()}
            missing = sorted(wanted - highlighted_nos)
            if missing:
                print(f"warning: --clear-highlight rows not highlighted: {', '.join(map(str, missing))}")

    if args.clear_highlight is not None:
        print("=== CLEAR HIGHLIGHT ===")
        if clear_targets:
            print("| No | Service | Highlight |")
            print("|----|---------|-----------|")
            for r in clear_targets:
                print(f"| {r['no']} | {r['service']} | {r['highlight']} |")
        else:
            print("no highlighted rows to clear")
        print()

    print("=== DRY RUN ===")
    print(f"page: {page['title']} (id {page['id']}, version {page['version']['number']})")
    print(f"project: {project_name or '-'} | group: {group} | git: {git_base} | rows in group: {len(candidates)}")
    print(f"cache: {len(cached_repos)}/{len(repos)} repos reused (ttl {args.cache_ttl}s)")
    print()
    print("| No | Service | Tag | Status |")
    print("|----|---------|-----|--------|")
    for c in changes:
        if c["action"] == "UPDATE":
            old = c["current"] if {"release", "docker"} & set(c["fields"]) else c["version_tag"]
            tag, status = f"{old} -> {c['newest']}", "update: " + ", ".join(c["fields"])
        elif c["action"] == "up-to-date":
            tag, status = c["newest"], "up-to-date"
        elif c["action"] == "paint":
            tag, status = (c["newest"] or c["current"] or "-"), "paint: purple"
        elif c["action"].startswith("SKIP ambiguous"):
            tag, status = (c["newest"] or "-"), "skip: ambiguous"
        else:
            tag, status = "-", "skip: no tag"
        print(f"| {c['no']} | {c['service']} | {tag} | {status} |")
    for e in errors:
        print(f"| - | - | - | error: {e} |")

    if not args.apply:
        print_rows("RELEASE PAGE", page_rows(html, ver_idx, release_idx, docker_idx))
        print(f"\n{len(to_apply)} row(s) to sync, {len(clear_targets)} highlight(s) to clear. "
              "Re-run with --apply --approved to write (after user approval).")
        return

    if not to_apply and not clear_targets:
        print("\nnothing to apply.")
        print_rows("RELEASE PAGE", page_rows(html, ver_idx, release_idx, docker_idx))
        return

    print("\n=== APPLYING ===")

    updated = html
    for c in to_apply:
        row = c["row"]
        if "version" in c["fields"]:
            row = row.replace(c["version_cell"], update_release_cell(c["version_cell"], c["version_tag"], c["newest"]), 1)
        if "current" in c["fields"]:
            row = row.replace(c["current_cell"], update_release_cell(c["current_cell"], c["current_tag"], c["version_tag"]), 1)
        if "release" in c["fields"]:
            row = row.replace(c["release_cell"], update_release_cell(c["release_cell"], c["release_tag"], c["newest"]), 1)
        if "docker" in c["fields"]:
            row = row.replace(c["docker_cell"], update_docker_cell(c["docker_cell"], c["prefix"], c["newest"]), 1)
        for open_tag in c["cell_tags"]:
            row = row.replace(open_tag, paint_open_tag(open_tag, hl_color), 1)
        updated = updated.replace(c["row"], row, 1)

    for r in clear_targets:
        row = r["row"]
        for open_tag in r["cell_tags"]:
            row = row.replace(open_tag, clear_open_tag(open_tag), 1)
        updated = updated.replace(r["row"], row, 1)

    res = update_page(base, token, page, updated)
    updated_rows = [c for c in to_apply if c["fields"]]
    painted_rows = [c for c in to_apply if not c["fields"]]
    if updated_rows:
        print("\n=== SERVICES TO RELEASE ===")
        print("| No | Service | Tag |")
        print("|----|---------|-----|")
        for c in updated_rows:
            print(f"| {c['no']} | {c['service']} | {c['newest'] or c['current'] or '-'} |")
    if painted_rows:
        print(f"\npainted purple: {', '.join(c['no'] for c in painted_rows)}")
    if clear_targets:
        print(f"\ncleared highlights: {', '.join(r['no'] for r in clear_targets)}")
    print(f"\napplied {len(to_apply)} tag row(s), {len(clear_targets)} cleared row(s); "
          f"page now version {res['version']['number']}")
    print(f"release page: {page_url(page, base)}")

    fresh_page = api(base, token, "GET", f"/rest/api/content/{page['id']}?expand=body.storage,version")
    fresh_html = fresh_page["body"]["storage"]["value"]
    fresh_rows = {r[0]: r for r in page_rows(fresh_html, ver_idx, release_idx, docker_idx)}
    print("\n=== VERIFY HIGHLIGHT ===")
    print("| No | Service | Highlight | Result |")
    print("|----|---------|-----------|--------|")
    expected = [(c["no"], c["service"], hl_color) for c in to_apply]
    expected += [(r["no"], r["service"], "-") for r in clear_targets]
    ok = 0
    for no, service, want in expected:
        r = fresh_rows.get(no)
        hl = r[3] if r else "-"
        good = hl.lower() == want.lower()
        ok += good
        print(f"| {no} | {service} | {hl} | {'ok' if good else 'MISMATCH'} |")
    print(f"\nverified {ok}/{len(expected)} row(s) ({len(to_apply)} painted/updated, "
          f"{len(clear_targets)} cleared) (page v{fresh_page['version']['number']})")
    print_rows("RELEASE PAGE", page_rows(fresh_html, ver_idx, release_idx, docker_idx))


if __name__ == "__main__":
    main()
