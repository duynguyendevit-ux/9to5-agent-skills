#!/usr/bin/env python3
"""Safely update standard release-table rows in one Confluence page version."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable


DEFAULT_HIGHLIGHT = "#c0b6f2"
DEFAULT_PROFILE_CONFIG = Path(__file__).resolve().parent.parent / "references" / "release-profiles.json"
SKILL_DIR = Path(__file__).resolve().parent.parent
ENDPOINTS_PATH = SKILL_DIR / "config" / "endpoints.json"
ENDPOINT_KEYS = ("confluence_url", "jira_url", "gitlab_url", "git_ssh_base")
CELL_RE = re.compile(r"<t[dh]\b[^>]*>.*?</t[dh]>", re.IGNORECASE | re.DOTALL)
ROW_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)


def load_endpoints() -> dict[str, str]:
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


def save_endpoint(key: str, value: str) -> Path:
    if key not in ENDPOINT_KEYS:
        sys.exit(f"unknown endpoint '{key}'; expected one of: {', '.join(ENDPOINT_KEYS)}")
    data: dict[str, Any] = {}
    if ENDPOINTS_PATH.exists():
        data = json.loads(ENDPOINTS_PATH.read_text(encoding="utf-8"))
    data[key] = value.rstrip("/")
    ENDPOINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENDPOINTS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return ENDPOINTS_PATH


def resolve_endpoint(key: str, cli_value: str | None, env_vars: tuple[str, ...]) -> str:
    """CLI flag -> environment variable -> config/endpoints.json -> ask the user."""
    if cli_value:
        return cli_value.rstrip("/")
    for var in env_vars:
        if os.environ.get(var):
            return os.environ[var].strip().rstrip("/")
    value = load_endpoints().get(key)
    if value:
        return value.rstrip("/")
    sys.exit(
        f"missing {key}: ask the user for the internal URL, then persist it with\n"
        f"  {Path(__file__).name} --set-endpoint {key}=<url>\n"
        f"or write it into {ENDPOINTS_PATH}\n"
        f"(version control only ships config/endpoints.example.json; do not commit the real value)"
    )



@dataclass(frozen=True)
class ServiceSpec:
    name: str
    repo: Path | None
    gitlab_project: str
    docker_image: str
    explicit_tag: str | None = None
    explicit_tag_url: str | None = None


@dataclass(frozen=True)
class Release:
    name: str
    tag: str
    tag_url: str
    docker_image: str
    repo: Path | None = None
    create_from_ref: str | None = None


class ConfluenceClient:
    def __init__(self, base_url: str, token: str, insecure: bool = False):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.context = ssl._create_unverified_context() if insecure else None

    def request(self, path: str, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, context=self.context) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Confluence {method} failed: HTTP {error.code}: {detail}") from error

    def get_page(self, page_id: str) -> dict[str, Any]:
        return self.request(f"/rest/api/content/{page_id}?expand=body.storage,version,space")

    def find_page(self, title: str, space_key: str | None = None) -> dict[str, Any]:
        query = {"title": title, "expand": "body.storage,version,space", "limit": "10"}
        if space_key:
            query["spaceKey"] = space_key
        result = self.request("/rest/api/content?" + urllib.parse.urlencode(query))
        matches = [page for page in result.get("results", []) if page.get("title") == title]
        if space_key:
            matches = [page for page in matches if page.get("space", {}).get("key") == space_key]
        if len(matches) != 1:
            ids = [str(page.get("id")) for page in matches]
            raise ValueError(f"Expected one Confluence page titled {title!r}, found {len(matches)}: {ids}")
        return matches[0]

    def find_daily_page(
        self,
        daily_date: str,
        service_names: list[str],
        space_key: str | None = None,
    ) -> dict[str, Any]:
        cql = f'type=page AND title ~ "{daily_date}"'
        if space_key:
            cql += f' AND space="{space_key}"'
        query = {
            "cql": cql,
            "expand": "body.storage,version,space",
            "limit": "50",
        }
        result = self.request("/rest/api/content/search?" + urllib.parse.urlencode(query))
        matches = [
            page
            for page in result.get("results", [])
            if page.get("title", "").strip().endswith(daily_date)
        ]
        if len(matches) == 1:
            return matches[0]
        scored: list[tuple[int, dict[str, Any]]] = []
        for page in matches:
            body = page.get("body", {}).get("storage", {}).get("value", "")
            score = 0
            for service in service_names:
                try:
                    find_service_row(body, service)
                    score += 1
                except ValueError:
                    pass
            scored.append((score, page))
        best_score = max((score for score, _ in scored), default=0)
        best_pages = [page for score, page in scored if score == best_score and score > 0]
        if len(best_pages) != 1:
            choices = [
                f"{page.get('id')}:{page.get('title')} (service matches={score})"
                for score, page in scored
            ]
            raise ValueError(
                f"Cannot uniquely select Confluence page for {daily_date}: {choices}"
            )
        return best_pages[0]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    page_group = parser.add_mutually_exclusive_group()
    page_group.add_argument("--page", help="ID/URL, or 'today'; defaults to today's release page")
    page_group.add_argument("--page-id", help="Backward-compatible numeric page ID")
    page_group.add_argument("--page-title", help="Exact page title; combine with --space-key when possible")
    parser.add_argument("--date", dest="release_date", help="Release page date in DD.MM.YYYY; defaults to today")
    parser.add_argument("--space-key")
    parser.add_argument("--service-name", action="append", default=[], help="Service from release-services.json")
    parser.add_argument("--service", action="append", default=[], metavar="NAME|REPO|GITLAB_PROJECT|DOCKER_IMAGE")
    parser.add_argument("--release", action="append", default=[], metavar="NAME|TAG|TAG_URL|DOCKER_IMAGE")
    parser.add_argument("--tag-url", action="append", default=[], help="Existing GitLab tag URL; service and image come from the selected profile")
    parser.add_argument("--tag", action="append", default=[], metavar="SERVICE=TAG", help="Override discovered tag")
    parser.add_argument("--profile", help="Release profile; interactive mode asks when omitted")
    parser.add_argument("--service-config", type=Path, help="Override the service registry selected by --profile")
    parser.add_argument("--base-url", help="Confluence base URL; resolved from config/endpoints.json when omitted")
    parser.add_argument("--gitlab-url", help="GitLab base URL; resolved from config/endpoints.json when omitted")
    parser.add_argument("--set-endpoint", metavar="KEY=VALUE",
                        help=f"persist an internal endpoint to {ENDPOINTS_PATH} and exit; keys: {', '.join(ENDPOINT_KEYS)}")
    parser.add_argument("--highlight-color", default=DEFAULT_HIGHLIGHT)
    parser.add_argument("--highlight-columns", default="0-8")
    parser.add_argument("--include-hotfix", action="store_true")
    parser.add_argument("--all-services", action="store_true", help="Disable develop/page change filtering in the interactive picker")
    parser.add_argument("--no-fetch", action="store_true")
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approved", action="store_true",
                        help="required for non-interactive writes; confirm the user approved the dry run")
    args = parser.parse_args(argv)
    if args.set_endpoint:
        if "=" not in args.set_endpoint:
            parser.error("--set-endpoint expects KEY=VALUE")
        key, value = args.set_endpoint.split("=", 1)
        path = save_endpoint(key.strip(), value.strip())
        print(f"saved {key.strip()} to {path}")
        raise SystemExit(0)
    return args


def read_token(config_path: Path | None = None) -> str:
    path = config_path or Path.home() / ".config" / "zjira" / "config.yaml"
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^confluence_token:\s*(.+?)\s*$", text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"Missing confluence_token in {path}")
    token = match.group(1).strip().strip("'\"")
    if not token:
        raise RuntimeError(f"Empty confluence_token in {path}")
    return token


def parse_columns(value: str) -> set[int]:
    columns: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"Invalid highlight range: {part}")
            columns.update(range(start, end + 1))
        else:
            columns.add(int(part))
    if any(column < 0 for column in columns):
        raise ValueError("Highlight columns must be non-negative")
    return columns


def parse_overrides(values: Iterable[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--tag must be SERVICE=TAG")
        service, tag = value.split("=", 1)
        if not service or not tag or service in overrides:
            raise ValueError(f"Invalid or duplicate tag override: {value}")
        overrides[service] = tag
    return overrides


def split_exact(value: str, count: int, option: str) -> list[str]:
    parts = value.split("|")
    if len(parts) != count or not all(parts):
        raise ValueError(f"{option} must contain {count} non-empty pipe-separated fields")
    return parts


def load_service_specs(args: argparse.Namespace) -> tuple[list[ServiceSpec], list[Release]]:
    overrides = parse_overrides(args.tag)
    specs: list[ServiceSpec] = []
    explicit_releases: list[Release] = []
    registry: dict[str, Any] = {}
    if args.service_name:
        registry = json.loads(args.service_config.read_text(encoding="utf-8"))
    for name in args.service_name:
        if name not in registry:
            raise ValueError(f"Unknown service {name!r} in {args.service_config}")
        item = registry[name]
        specs.append(ServiceSpec(name, Path(item["repo"]), item["gitlab_project"], item["docker_image"], overrides.pop(name, None)))
    for raw in args.service:
        name, repo, project, image = split_exact(raw, 4, "--service")
        specs.append(ServiceSpec(name, Path(repo), project, image, overrides.pop(name, None)))
    for raw in args.release:
        name, tag, tag_url, image = split_exact(raw, 4, "--release")
        explicit_releases.append(Release(name, tag, tag_url, image))
    if overrides:
        raise ValueError("Tag override has no matching service: " + ", ".join(sorted(overrides)))
    names = [item.name for item in specs] + [item.name for item in explicit_releases]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError("Duplicate services: " + ", ".join(duplicates))
    return specs, explicit_releases


def load_registry(path: Path) -> dict[str, Any]:
    registry = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(registry, dict) or not registry:
        raise ValueError(f"Service registry must be a non-empty JSON object: {path}")
    return registry


def resolve_service_config(args: argparse.Namespace) -> Path:
    if args.service_config:
        return args.service_config
    profiles = json.loads(DEFAULT_PROFILE_CONFIG.read_text(encoding="utf-8"))
    try:
        return Path(__file__).resolve().parent.parent / profiles[args.profile]["service_config"]
    except KeyError as error:
        raise ValueError(f"Unknown release profile: {args.profile}") from error


def choose_profile(
    args: argparse.Namespace,
    input_fn=input,
    output=sys.stdout,
    interactive_terminal: bool | None = None,
) -> str:
    if args.service_config:
        return args.profile or "custom"
    if args.profile:
        return args.profile
    tag_urls = " ".join(args.tag_url).lower()
    page_reference = (args.page or "").lower()
    if "/c7-ttdvkh/" in tag_urls or "/243." in page_reference:
        args.profile = "c7-ttdvkh"
        return args.profile
    if "/c7/ttch/" in tag_urls or "/255." in page_reference:
        args.profile = "c7-ttch"
        return args.profile
    interactive_request = not (args.service_name or args.service or args.release or args.tag_url)
    is_terminal = sys.stdin.isatty() if interactive_terminal is None else interactive_terminal
    if not interactive_request or not is_terminal:
        args.profile = "c7-ttch"
        return args.profile
    profiles = json.loads(DEFAULT_PROFILE_CONFIG.read_text(encoding="utf-8"))
    names = list(profiles)
    print("Available release projects:", file=output)
    for index, name in enumerate(names, start=1):
        print(f"{index}. {name}", file=output)
    choice = input_fn("Select project [1]: ").strip() or "1"
    selected = parse_number_selection(choice, len(names))
    if len(selected) != 1:
        raise ValueError("Select exactly one release project")
    args.profile = names[selected[0]]
    return args.profile


def registry_spec(name: str, item: dict[str, Any], explicit_tag: str | None = None) -> ServiceSpec:
    return ServiceSpec(
        name,
        Path(item["repo"]),
        item["gitlab_project"],
        item["docker_image"],
        explicit_tag,
    )


def project_path(value: str) -> str:
    if re.match(r"https?://", value):
        return urllib.parse.urlparse(value).path.strip("/")
    return value.strip("/")


def release_from_tag_url(raw_url: str, registry: dict[str, Any]) -> Release:
    parsed = urllib.parse.urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid GitLab tag URL: {raw_url}")
    marker = "/-/tags/"
    if marker not in parsed.path:
        raise ValueError(f"GitLab tag URL must contain {marker}: {raw_url}")
    raw_project, raw_tag = parsed.path.split(marker, 1)
    project = urllib.parse.unquote(raw_project.strip("/"))
    tag = urllib.parse.unquote(raw_tag.strip("/"))
    if not project or not tag or "/" in tag:
        raise ValueError(f"Invalid GitLab project or tag in URL: {raw_url}")
    matches = [
        registry_spec(name, item)
        for name, item in registry.items()
        if project_path(item["gitlab_project"]) == project
    ]
    if len(matches) != 1:
        names = [spec.name for spec in matches]
        raise ValueError(f"Expected one registry service for project {project!r}, found: {names}")
    spec = matches[0]
    return Release(
        spec.name,
        tag,
        raw_url,
        spec.docker_image.rstrip(":") + ":" + tag,
        spec.repo,
    )


def verify_remote_tag_exists(release: Release) -> None:
    if release.repo is None:
        raise ValueError(f"Missing repository for {release.name}")
    remote = run_git(
        release.repo,
        "ls-remote",
        "--tags",
        "origin",
        f"refs/tags/{release.tag}",
    )
    if not remote.strip():
        raise ValueError(f"Remote tag does not exist for {release.name}: {release.tag}")


def run_git(repo: Path, *args: str) -> str:
    if not repo.is_dir():
        raise ValueError(f"Local repo does not exist: {repo}")
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode:
        raise RuntimeError(f"git failed for {repo}: {process.stderr.strip()}")
    return process.stdout


def select_latest_tag(tags: Iterable[str], include_hotfix: bool = False) -> str:
    candidates = [tag.strip() for tag in tags if tag.strip()]
    if not include_hotfix:
        candidates = [tag for tag in candidates if "hotfix" not in tag.lower()]
    if not candidates:
        qualifier = "" if include_hotfix else " non-hotfix"
        raise ValueError(f"No{qualifier} tags found")
    return candidates[0]


def discover_tags(spec: ServiceSpec, fetch: bool, include_hotfix: bool, limit: int = 5) -> list[str]:
    if spec.repo is None:
        raise ValueError(f"Missing repo for {spec.name}")
    if fetch:
        run_git(
            spec.repo,
            "fetch",
            "--quiet",
            "origin",
            "+refs/tags/*:refs/remotes/origin/tags/*",
        )
    namespace = "refs/remotes/origin/tags" if fetch else "refs/tags"
    output = run_git(
        spec.repo,
        "for-each-ref",
        "--sort=-creatordate",
        "--format=%(refname)",
        namespace,
    )
    prefix = namespace.rstrip("/") + "/"
    tags = [line.removeprefix(prefix) for line in output.splitlines() if line]
    if not include_hotfix:
        tags = [tag for tag in tags if "hotfix" not in tag.lower()]
    if not tags:
        qualifier = "" if include_hotfix else " non-hotfix"
        raise ValueError(f"No{qualifier} tags found for {spec.name}")
    return tags[:limit]


def develop_commit_count(spec: ServiceSpec, latest_tag: str, fetch: bool) -> int:
    if spec.repo is None:
        raise ValueError(f"Missing repo for {spec.name}")
    if fetch:
        run_git(spec.repo, "fetch", "--quiet", "origin", "develop")
    tag_refs = [
        f"refs/remotes/origin/tags/{latest_tag}",
        f"refs/tags/{latest_tag}",
    ]
    tag_commit = ""
    for tag_ref in tag_refs:
        process = subprocess.run(
            ["git", "-C", str(spec.repo), "rev-parse", "--verify", f"{tag_ref}^{{commit}}"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.returncode == 0:
            tag_commit = process.stdout.strip()
            break
    if not tag_commit:
        raise ValueError(f"Cannot resolve latest tag commit for {spec.name}: {latest_tag}")
    count = run_git(
        spec.repo,
        "rev-list",
        "--count",
        f"{tag_commit}..origin/develop",
    ).strip()
    if not count.isdigit():
        raise ValueError(f"Cannot count develop commits for {spec.name}")
    return int(count)


def service_has_develop_changes(develop_commits: int | None) -> bool:
    return develop_commits is not None and develop_commits > 0


def release_for_tag(
    spec: ServiceSpec,
    tag: str,
    gitlab_url: str,
    create_from_ref: str | None = None,
) -> Release:
    project_url = spec.gitlab_project.rstrip("/")
    if not re.match(r"https?://", project_url):
        project_url = gitlab_url.rstrip("/") + "/" + project_url.lstrip("/")
    if project_url.endswith("/-/tags"):
        project_url = project_url[:-7]
    tag_url = project_url + "/-/tags/" + urllib.parse.quote(tag, safe="")
    return Release(
        spec.name,
        tag,
        tag_url,
        spec.docker_image.rstrip(":") + ":" + tag,
        spec.repo,
        create_from_ref,
    )


def discover_release(spec: ServiceSpec, gitlab_url: str, fetch: bool, include_hotfix: bool) -> Release:
    tag = spec.explicit_tag
    if not tag:
        tag = discover_tags(spec, fetch, include_hotfix, limit=1)[0]
    return release_for_tag(spec, tag, gitlab_url)


def parse_number_selection(value: str, maximum: int) -> list[int]:
    normalized = value.strip().lower()
    if normalized in {"a", "all"}:
        return list(range(maximum))
    selected: list[int] = []
    for part in normalized.split(","):
        if not part.strip().isdigit():
            raise ValueError("Selection must be comma-separated numbers or 'a'")
        index = int(part.strip()) - 1
        if index < 0 or index >= maximum:
            raise ValueError(f"Selection out of range: {part}")
        if index not in selected:
            selected.append(index)
    if not selected:
        raise ValueError("Select at least one item")
    return selected


def increment_tag(tag: str) -> str:
    match = re.search(r"(\d+)(?!.*\d)", tag)
    if not match:
        raise ValueError(f"Cannot infer next tag from {tag!r}")
    next_number = str(int(match.group(1)) + 1).zfill(len(match.group(1)))
    return tag[: match.start()] + next_number + tag[match.end() :]


def resolve_tag_commit(release: Release, fetch_source: bool = True) -> tuple[str, str]:
    if release.repo is None or release.create_from_ref is None:
        raise ValueError(f"Missing tag creation source for {release.name}")
    source_ref = release.create_from_ref
    if fetch_source and source_ref.startswith("origin/"):
        branch = source_ref.removeprefix("origin/")
        run_git(release.repo, "fetch", "--quiet", "origin", branch)
    existing = run_git(
        release.repo,
        "ls-remote",
        "--tags",
        "origin",
        f"refs/tags/{release.tag}",
    ).strip()
    if existing:
        raise ValueError(f"Remote tag already exists for {release.name}: {release.tag}")
    commit = run_git(
        release.repo,
        "rev-parse",
        "--verify",
        f"{source_ref}^{{commit}}",
    ).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", commit):
        raise ValueError(f"Cannot resolve commit for {release.name} from {source_ref}")
    description = run_git(
        release.repo,
        "show",
        "-s",
        "--format=%h %s",
        commit,
    ).strip()
    return commit, description


def push_remote_tag(release: Release, commit: str) -> None:
    if release.repo is None:
        raise ValueError(f"Missing repository for {release.name}")
    run_git(
        release.repo,
        "push",
        "origin",
        f"{commit}:refs/tags/{release.tag}",
    )
    remote = run_git(
        release.repo,
        "ls-remote",
        "--tags",
        "origin",
        f"refs/tags/{release.tag}",
    )
    if not remote.strip():
        raise RuntimeError(f"Remote tag verification failed for {release.name}: {release.tag}")


def interactive_releases(
    args: argparse.Namespace,
    body: str,
    input_fn=input,
    output=sys.stdout,
) -> list[Release]:
    if not sys.stdin.isatty() and input_fn is input:
        raise ValueError(
            "No services provided and stdin is not interactive; use --service-name or run in a terminal"
        )
    registry = load_registry(args.service_config)
    candidates: list[tuple[ServiceSpec, list[str], str]] = []
    print("Available services:", file=output)
    for name, item in registry.items():
        spec = registry_spec(name, item)
        try:
            tags = discover_tags(spec, not args.no_fetch, args.include_hotfix)
        except (OSError, RuntimeError, ValueError) as error:
            print(f"- skipped {name}: {error}", file=output)
            continue
        _, _, cells = find_service_row(body, name)
        release_version = plain_text(cell_inner(cells[3].group(0)))
        current_version = plain_text(cell_inner(cells[4].group(0)))
        develop_commits: int | None = None
        develop_note = "unknown"
        try:
            develop_commits = develop_commit_count(spec, tags[0], not args.no_fetch)
            develop_note = f"+{develop_commits}"
        except (OSError, RuntimeError, ValueError) as error:
            develop_note = f"unknown ({error})"
        if not args.all_services and not service_has_develop_changes(develop_commits):
            continue
        candidates.append((spec, tags, current_version))
        index = len(candidates)
        print(
            f"{index}. {name} | deployed: {current_version or '-'} | page: {release_version or '-'} | latest: {tags[0]} | develop: {develop_note}",
            file=output,
        )
    if not candidates:
        if args.all_services:
            raise ValueError("No selectable services have usable tags")
        raise ValueError("No services need release; use --all-services to show every registered service")
    selected = parse_number_selection(
        input_fn("Select services (comma-separated, a=all): "), len(candidates)
    )
    releases: list[Release] = []
    for candidate_index in selected:
        spec, tags, _ = candidates[candidate_index]
        print(f"\nTags for {spec.name}:", file=output)
        for tag_index, tag in enumerate(tags, start=1):
            suffix = " (latest)" if tag_index == 1 else ""
            print(f"{tag_index}. {tag}{suffix}", file=output)
        print("c. Create a new tag", file=output)
        choice = input_fn("Select tag [1], c=create, or enter exact tag: ").strip()
        if not choice:
            tag = tags[0]
            release = release_for_tag(spec, tag, args.gitlab_url)
        elif choice.lower() == "c":
            suggested_tag = increment_tag(tags[0])
            tag = input_fn(f"New tag [{suggested_tag}]: ").strip() or suggested_tag
            source_ref = input_fn("Source ref [origin/develop]: ").strip() or "origin/develop"
            release = release_for_tag(
                spec,
                tag,
                args.gitlab_url,
                create_from_ref=source_ref,
            )
        elif choice.isdigit():
            tag_index = int(choice) - 1
            if tag_index < 0 or tag_index >= len(tags):
                raise ValueError(f"Tag selection out of range for {spec.name}: {choice}")
            tag = tags[tag_index]
            release = release_for_tag(spec, tag, args.gitlab_url)
        else:
            tag = choice
            release = release_for_tag(spec, tag, args.gitlab_url)
        releases.append(release)
    return releases


def resolve_page(
    client: ConfluenceClient,
    reference: str | None,
    title: str | None,
    space_key: str | None,
    daily_date: str,
    service_names: list[str],
) -> dict[str, Any]:
    if title:
        return client.find_page(title, space_key)
    if reference is None or reference.lower() in {"today", "current"}:
        return client.find_daily_page(daily_date, service_names, space_key)
    if reference.isdigit():
        return client.get_page(reference)
    parsed = urllib.parse.urlparse(reference)
    query = urllib.parse.parse_qs(parsed.query)
    page_ids = query.get("pageId", [])
    if page_ids and page_ids[0].isdigit():
        return client.get_page(page_ids[0])
    match = re.search(r"/display/([^/]+)/(.+)$", parsed.path)
    if match:
        resolved_space = urllib.parse.unquote(match.group(1))
        resolved_title = urllib.parse.unquote_plus(match.group(2))
        return client.find_page(resolved_title, resolved_space)
    raise ValueError("Cannot resolve page reference; use numeric ID, pageId URL, /display/SPACE/title, or --page-title")


def cell_inner(cell: str) -> str:
    match = re.fullmatch(r"<t[dh]\b[^>]*>(.*)</t[dh]>", cell, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Unexpected table cell structure")
    return match.group(1)


def plain_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    return " ".join(html.unescape(text).split())


def replace_inner(cell: str, content: str) -> str:
    match = re.fullmatch(r"(<t[dh]\b[^>]*>).*?(</t[dh]>)", cell, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Unexpected table cell structure")
    return match.group(1) + content + match.group(2)


def highlight_cell(cell: str, color: str) -> str:
    open_match = re.match(r"<t[dh]\b[^>]*>", cell, re.IGNORECASE | re.DOTALL)
    if not open_match:
        raise ValueError("Unexpected table cell opening tag")
    opening = open_match.group(0)
    class_match = re.search(r'\sclass=("[^"]*"|\'[^\']*\')', opening, re.IGNORECASE)
    classes: list[str] = []
    if class_match:
        classes = class_match.group(1)[1:-1].split()
        opening = opening[: class_match.start()] + opening[class_match.end() :]
    classes = [item for item in classes if not item.startswith("highlight-")]
    classes.append("highlight-" + color)
    opening = re.sub(r"\sdata-highlight-colour=(\"[^\"]*\"|'[^']*')", "", opening, flags=re.IGNORECASE)
    attributes = f' class="{html.escape(" ".join(classes), quote=True)}" data-highlight-colour="{html.escape(color, quote=True)}"'
    opening = opening[:-1].rstrip() + attributes + ">"
    return opening + cell[open_match.end() :]


def find_service_row(body: str, service: str) -> tuple[re.Match[str], str, list[re.Match[str]]]:
    matches: list[tuple[re.Match[str], str, list[re.Match[str]]]] = []
    for row_match in ROW_RE.finditer(body):
        row = row_match.group(0)
        cells = list(CELL_RE.finditer(row))
        if any(plain_text(cell_inner(cell.group(0))) == service for cell in cells):
            matches.append((row_match, row, cells))
    if len(matches) != 1:
        raise ValueError(f"Expected one release row for {service}, found {len(matches)}")
    return matches[0]


def validate_release(release: Release) -> None:
    if not release.tag or any(character.isspace() for character in release.tag):
        raise ValueError(f"Invalid tag for {release.name}: {release.tag!r}")
    parsed = urllib.parse.urlparse(release.tag_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.path.endswith("/" + urllib.parse.quote(release.tag, safe="")):
        raise ValueError(f"Invalid tag URL for {release.name}: {release.tag_url}")
    if not release.docker_image.endswith(":" + release.tag):
        raise ValueError(f"Docker image does not end with tag for {release.name}: {release.docker_image}")


def update_release_row(body: str, release: Release, color: str, highlight_columns: set[int]) -> tuple[str, str]:
    row_match, row, cells = find_service_row(body, release.name)
    if len(cells) < 9:
        raise ValueError(f"Expected at least 9 columns for {release.name}, found {len(cells)}")
    if highlight_columns and max(highlight_columns) >= len(cells):
        raise ValueError(f"Highlight column exceeds row width for {release.name}: {len(cells)}")
    current_version = cell_inner(cells[4].group(0))
    replacements = {
        3: f'<a href="{html.escape(release.tag_url, quote=True)}" title="">{html.escape(release.tag)}</a>',
        5: f'<a href="{html.escape(release.tag_url, quote=True)}" title="">{html.escape(release.tag_url)}</a>',
        7: html.escape(release.docker_image),
    }
    for index in range(len(cells) - 1, -1, -1):
        cell_match = cells[index]
        new_cell = cell_match.group(0)
        if index in replacements:
            new_cell = replace_inner(new_cell, replacements[index])
        if index in highlight_columns:
            new_cell = highlight_cell(new_cell, color)
        row = row[: cell_match.start()] + new_cell + row[cell_match.end() :]
    updated = body[: row_match.start()] + row + body[row_match.end() :]
    _, updated_row, updated_cells = find_service_row(updated, release.name)
    if cell_inner(updated_cells[4].group(0)) != current_version:
        raise AssertionError(f"current version changed for {release.name}")
    verify_release_row(updated, release, current_version, color, highlight_columns)
    return updated, current_version


def verify_release_row(body: str, release: Release, current_version: str, color: str, highlight_columns: set[int]) -> None:
    _, _, cells = find_service_row(body, release.name)
    if plain_text(cell_inner(cells[3].group(0))) != release.tag:
        raise AssertionError(f"version verification failed for {release.name}")
    if release.tag_url not in cell_inner(cells[3].group(0)) or release.tag_url not in cell_inner(cells[5].group(0)):
        raise AssertionError(f"tag URL verification failed for {release.name}")
    if plain_text(cell_inner(cells[7].group(0))) != release.docker_image:
        raise AssertionError(f"Docker image verification failed for {release.name}")
    if cell_inner(cells[4].group(0)) != current_version:
        raise AssertionError(f"current version verification failed for {release.name}")
    for index in highlight_columns:
        opening = re.match(r"<t[dh]\b[^>]*>", cells[index].group(0), re.IGNORECASE | re.DOTALL).group(0)
        if f'highlight-{color}' not in opening or f'data-highlight-colour="{color}"' not in opening:
            raise AssertionError(f"highlight verification failed for {release.name} column {index}")


def page_payload(page: dict[str, Any], body: str, services: list[str]) -> dict[str, Any]:
    return {
        "id": str(page["id"]),
        "type": "page",
        "title": page["title"],
        "space": {"key": page["space"]["key"]},
        "version": {
            "number": page["version"]["number"] + 1,
            "message": "Update release tags: " + ", ".join(services),
        },
        "body": {"storage": {"value": body, "representation": "storage"}},
    }


def main(argv: list[str] | None = None) -> int:
    pushed_tags: list[str] = []
    try:
        args = parse_args(argv)
        args.base_url = resolve_endpoint("confluence_url", args.base_url, ("CONFLUENCE_URL",))
        args.gitlab_url = resolve_endpoint("gitlab_url", args.gitlab_url, ("GITLAB_URL",))
        choose_profile(args)
        args.service_config = resolve_service_config(args)
        color = args.highlight_color
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("--highlight-color must be a six-digit hex color")
        highlight_columns = parse_columns(args.highlight_columns)
        release_date = args.release_date or date.today().strftime("%d.%m.%Y")
        datetime.strptime(release_date, "%d.%m.%Y")
        client = ConfluenceClient(args.base_url, read_token(), args.insecure)
        registry_services = list(load_registry(args.service_config))
        page = resolve_page(
            client,
            args.page or args.page_id,
            args.page_title,
            args.space_key,
            release_date,
            registry_services,
        )
        original_body = page["body"]["storage"]["value"]
        interactive = not (args.service_name or args.service or args.release or args.tag_url)
        specs, releases = load_service_specs(args)
        if interactive:
            releases = interactive_releases(args, original_body)
        else:
            registry = load_registry(args.service_config)
            direct_releases = [
                release_from_tag_url(tag_url, registry) for tag_url in args.tag_url
            ]
            for release in direct_releases:
                verify_remote_tag_exists(release)
            releases.extend(direct_releases)
            releases.extend(
                discover_release(spec, args.gitlab_url, not args.no_fetch, args.include_hotfix)
                for spec in specs
            )
        names = [release.name for release in releases]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError("Duplicate services: " + ", ".join(duplicates))
        for release in releases:
            validate_release(release)
        tag_plans: dict[str, tuple[str, str]] = {}
        for release in releases:
            if release.create_from_ref:
                tag_plans[release.name] = resolve_tag_commit(
                    release,
                    fetch_source=not args.no_fetch,
                )
        updated_body = original_body
        current_versions: dict[str, str] = {}
        for release in releases:
            updated_body, current_versions[release.name] = update_release_row(
                updated_body, release, color, highlight_columns
            )

        changed = updated_body != original_body
        summary: dict[str, Any] = {
            "page_id": str(page["id"]),
            "title": page["title"],
            "current_version": page["version"]["number"],
            "next_version": page["version"]["number"] + 1,
            "dry_run": args.dry_run,
            "changed": changed,
            "releases": [
                {
                    "service": release.name,
                    "tag": release.tag,
                    "tag_url": release.tag_url,
                    "docker_image": release.docker_image,
                    "current_version_preserved": plain_text(current_versions[release.name]),
                    "create_tag": (
                        {
                            "source_ref": release.create_from_ref,
                            "commit": tag_plans[release.name][0],
                            "commit_description": tag_plans[release.name][1],
                        }
                        if release.create_from_ref
                        else None
                    ),
                }
                for release in releases
            ],
        }
        if args.dry_run or not changed:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0

        if interactive:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            if input("Apply this update to Confluence? [y/N]: ").strip().lower() != "y":
                print("Cancelled; no Confluence data was changed.")
                return 0
        elif not args.approved:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            raise SystemExit(
                "refusing to write: run with --dry-run, show the summary to the user, get explicit "
                "approval, then re-run with --approved"
            )

        for release in releases:
            if release.create_from_ref:
                push_remote_tag(release, tag_plans[release.name][0])
                pushed_tags.append(f"{release.name}:{release.tag}")

        expected_version = page["version"]["number"] + 1
        client.request(f'/rest/api/content/{page["id"]}', method="PUT", payload=page_payload(page, updated_body, [item.name for item in releases]))
        verified_page = client.get_page(str(page["id"]))
        if verified_page["version"]["number"] != expected_version:
            raise AssertionError(f"Expected page version {expected_version}, got {verified_page['version']['number']}")
        verified_body = verified_page["body"]["storage"]["value"]
        for release in releases:
            verify_release_row(verified_body, release, current_versions[release.name], color, highlight_columns)
        summary["updated_version"] = verified_page["version"]["number"]
        summary["verified"] = True
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (AssertionError, OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        if pushed_tags:
            print(
                "warning: tags were created before the failure: " + ", ".join(pushed_tags),
                file=sys.stderr,
            )
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
