---
name: 9to5-release-confluence-sync
description: Sync a project's daily Confluence release page — create it when missing, update it when it exists — and refresh version, current version, Release Tag and Docker image cells to the newest git tags of the project's service repos; also paint or clear release-row highlights and check pending releases. Projects come from the skill's projects.json registry (dev-c7, dev-c7-ttdvkh). Use when the user mentions a release page, release tag, Docker image tag, dev-c7 or ttdvkh release, asks to prepare today's release page, sync release tags, or check which services still need release.
license: MIT
compatibility: Requires the zjira CLI and Confluence credentials in ~/.config/zjira/config.yaml; GitLab SSH access for tag discovery. Reads non-secret endpoints from config/endpoints.json.
metadata:
  version: "1.0.4"
---

# Release Sync

## Example output

Illustrative preview; tags and page version must come from the actual run.

```text
Project: example-project
Page: Example daily release (ID 12345, version 7)
Mode: dry run
| No | Service | Tag | Status |
| 1 | example-api | example-v1.0.1 | update: release, docker |
| 2 | example-worker | example-v1.0.0 | up-to-date |
1 row to sync; 0 highlights to clear. No remote write.
```

If the page changes before PUT, report the version conflict and request a new review
of the recomputed changes instead of claiming an applied result.

One engine for every project. Project settings live in a registry file instead of
per-skill hardcoding.

## Projects registry

`projects.json` next to this file:

```json
{
  "projects": {
    "dev-c7": {
      "root": "92618728",
      "group": "c7",
      "space": "C7GSAFEDA",
      "hl_color": "#998dd9",
      "page_link": "",
      "doc_link": ""
    },
    "dev-c7-ttdvkh": {
      "root": "92618730",
      "group": "c7-ttdvkh",
      "space": "C7GSAFEDA",
      "hl_color": "#c0b6f2",
      "page_link": "",
      "doc_link": ""
    }
  }
}
```

Fields: `root` (hierarchy root page whose monthly children hold the daily release
pages), `group` (top-level git namespace used for tag lookup), `space`
(Confluence space key), `hl_color` (highlight for rows that need release),
`page_link`/`doc_link` (reference links for humans and agents).

Selection order for a run: `--project` -> auto-detect by matching the cwd repo's
group against the registry -> explicit `--root/--group/--space/--hl-color`.

## Missing config — ask first

When the target project is not in the registry, or credentials do not work, stop
and collect the values from the user before syncing:

1. **Project key** — registry name, e.g. `dev-c7-ttdvkh`.
2. **Release page link** — a daily release page or its monthly parent page URL.
3. **Document link** — the space or root page that holds the release pages.
4. **Git group** — top-level repository namespace for tag lookup (e.g. `c7`, `c7-ttdvkh`).
5. **Highlight color** — purple shade for rows that need release (default `#998dd9`).
6. **Credentials** — Confluence base URL and token if `zjira whoami` fails.

## Internal endpoints — ask on first use

Internal hostnames are never hardcoded in this skill. They live in
`config/endpoints.json`, which is gitignored so they never enter the repository;
version control ships only `config/endpoints.example.json`.

Resolution order for every endpoint: CLI flag -> environment variable
(`CONFLUENCE_URL`, `GIT_SSH_BASE`, `CONFLUENCE_SPACE`) -> `config/endpoints.json`
-> ask the user. There is no hardcoded fallback.

If a required value is missing the script exits with instructions. Ask the user
for the internal URL or key, confirm it, then persist it:

```bash
python3 scripts/sync_release_tags.py --set-endpoint confluence_url=<url>
python3 scripts/sync_release_tags.py --set-endpoint git_ssh_base=<ssh-base>
python3 scripts/sync_release_tags.py --set-endpoint confluence_space=<KEY>
```

Keys: `confluence_url`, `confluence_space`, `git_ssh_base`, `jira_url`.
Run this whenever the environment changes or the user corrects a value.

Store non-secret project values with the registry command:

```bash
python3 scripts/sync_release_tags.py --add-project dev-c7-ttdvkh \
  --root 92618730 --group c7-ttdvkh --hl-color '#c0b6f2' \
  --page-link '<confluence-base>/display/<SPACE>/<page>' \
  --doc-link '<confluence-base>/display/<SPACE>'
```

Store secrets in `~/.config/opencode/release-sync.json` (mode `600`), which
overlays the zjira config. Only the token belongs here — the URL belongs in
`config/endpoints.json`:

```json
{
  "confluence_token": "<token>"
}
```

`config/endpoints.json` wins over this file for non-secret keys; if both define
`confluence_url` with different values, the script warns and uses
`config/endpoints.json`. A legacy `confluence_url` here still works when
`config/endpoints.json` does not define one.

Never print the token; write the file with the user's pasted value, then
`chmod 600`. Prefer `zjira init` when the user already uses the zjira CLI.
After storing, verify with a dry run (`--project <name>`) before any `--apply`.

## Nexus images and STG releases

- Treat the deployment environment, Git release tag and Docker image tag as separate
  facts. An STG release does not imply that its image tag starts with `stg-`.
  For TTDVKH, use the verified `c7-ttdvkh-*` image series unless Nexus confirms
  a different requested tag. Do not add or strip `stg-` to invent an image tag.
- Store Nexus API/UI URL, Docker repository name and pull registry authority in
  local `config/endpoints.json` as `nexus_url`, `nexus_docker_repository` and
  `docker_registry`. The Nexus UI/API port and Docker connector port differ;
  do not use the UI URL as a Docker pull prefix. Discover the registry from
  deployment or CI configuration, and the image path from the service's own
  configuration. Repository basename may differ from runtime service name.
- For `full nexus images`, first read the configured Nexus REST API. List Docker
  repositories with `GET /service/rest/v1/repositories`, then verify each exact
  image/tag using `GET /service/rest/v1/search` with URL-encoded query parameters:
  `repository=<docker repository>`, `docker.imageName=<image path>` and
  `docker.imageTag=<tag>`. Confirm returned component `name` and `version` match;
  follow `continuationToken` if needed. An empty result is not a verified image.
  Authentication or network failure means unverified, not absent. Never print credentials.
- Output `Service | Git tag | Full Docker image | Nexus verification`. Distinguish
  Git-only tags, Nexus-confirmed images and images currently deployed. Never claim
  that the highest Git tag is deployed or that it exists in Nexus without checking.
- If Confluence is unavailable, still provide a read-only service/tag/image list
  from Git and Nexus. Do not create tags, push images or write release pages as part
  of this fallback. Honor the requested service subset before scanning all services.
- The current sync engine copies the chosen Git tag into the Docker cell; it does
  not resolve a separate image tag or verify Nexus. If Git and Docker tags differ,
  do not apply that automatic Docker-cell update: prepare an explicit verified
  page diff and obtain approval. Preserve the Git release tag separately.

## Write safety

Every remote write (page creation, tag/paint/clear updates) requires a dry run and
explicit user approval:

1. Run without `--apply` and show the resulting table to the user.
2. Ask for approval (question tool, or in chat).
3. Only then re-run with `--apply --approved`.

The script refuses `--apply` without `--approved`. Never bundle the dry run and the
approved write in one command unless the user already approved that exact plan.

## Run

Dry-run first, show the plan, then apply.

```bash
S=~/.config/opencode/skills/9to5-release-confluence-sync/scripts/sync_release_tags.py

# explicit project
python3 "$S" --project dev-c7                         # dry run
python3 "$S" --project dev-c7 --apply --approved      # after approval

# auto-detect from the cwd repo's remote group
python3 "$S"
python3 "$S" --apply --approved

# another date / explicit page
python3 "$S" --project dev-c7 --date 2026-09-18
python3 "$S" --page 141395270 --project dev-c7 --apply --approved
```

Flags:

| Flag | Meaning |
|------|---------|
| `--project NAME` | Project from the registry (`dev-c7`, `dev-c7-ttdvkh`, ...) |
| `--config PATH` | Alternate registry file |
| `--add-project NAME` | Register/update a project, then exit (`--root --group --space --hl-color --page-link --doc-link`) |
| `--page URL\|ID` | Explicit page; skips the today lookup and creation |
| `--root URL\|ID` | Hierarchy root; daily pages resolve under its monthly children |
| `--space KEY` | Confluence space key (default: the project's or `config/endpoints.json`) |
| `--date YYYY-MM-DD` | Release date, default today |
| `--template URL\|ID` | Page cloned when creating a missing page |
| `--no-create` | Fail instead of creating a missing page |
| `--hl-color HEX` | Highlight for rows that need release (project default) |
| `--group G` | Git group, default from the registry or the cwd repo remote |
| `--git-base URL` | SSH base; default the cwd repo remote or `config/endpoints.json` |
| `--set-endpoint KEY=VALUE` | Persist an internal endpoint to `config/endpoints.json` and exit |
| `--service NAME` | Restrict to rows whose service name contains this string |
| `--paint N,N` | Force the purple highlight on the given row numbers |
| `--fill-empty-tag` | With `--service`, fill an empty Release Tag cell with the newest tag (never runs without `--service`) |
| `--clear-highlight [N,N]` | Remove highlights: all highlighted rows, or the listed numbers |
| `--scan` | Refresh every repo from git and report new services/tags (ignores the cache) |
| `--no-cache` | Do not read or write the repo/tag cache |
| `--cache-ttl SECONDS` | Cached tag list lifetime, default `120` |
| `--jobs N` | Parallel `git ls-remote` fetches, default `8` |
| `--apply` | Write changes; requires `--approved` |
| `--approved` | Confirms the user approved the dry-run result |

## Behavior

### Kiểm tra service và màu kế thừa

- Trước khi đề xuất release, đối chiếu từng dòng: service, repository từ link của
  chính dòng đó, tag series, Release Tag, Docker image, version/current version.
  Dùng `--scan --no-cache` để lấy tag mới từ remote cho lần kiểm tra này.
- Khi tạo trang mới từ ngày trước, script xóa highlight trên các ô của dòng service
  có số thứ tự. Trước đó, nếu `Release Tag` khác `Current version` (kể cả Current
  version trống), chép nội dung Release Tag cùng link sang Current version. Thực hiện
  cả khi remote chưa có tag mới. Release Tag trống/không đọc được thì không ghi đè
  Current version. Giữ ô Release Tag làm baseline cho lần kiểm tra tag mới và giữ
  định dạng header. Đây là chuyển tiếp bản ghi, không xác minh deployment. Tag copy là baseline,
  không phải bằng chứng service cần release hôm nay. Chỉ tô lại dòng có cập nhật
  đã kiểm tra hoặc được yêu cầu `--paint` rõ ràng.
- Với trang đã tồn tại, đọc trang release trước đó trong cùng project/hierarchy.
  So sánh bằng service + repository + tag series, không ghép theo số thứ tự vì
  các dòng có thể đổi vị trí. Tag giống ngày trước và không có cập nhật mới thì
  đề xuất `--clear-highlight N,N` cho đúng các dòng màu kế thừa đã xác minh.
  Nếu người dùng đã yêu cầu release lại/paint hôm nay thì giữ màu theo yêu cầu đó.
- Không xóa tất cả màu chỉ vì Git báo up-to-date: tag được cập nhật hôm nay cũng
  sẽ là up-to-date ở lần chạy tiếp theo. Không dùng `--clear-highlight` không có
  danh sách để sửa màu kế thừa trên một trang có cả cập nhật mới.
- Dòng thiếu repo/tag, sai group, nhiều repo/tag xung đột, trùng service hoặc lỗi
  Git phải được báo riêng là chưa xác minh; không coi dòng bị script bỏ qua là
  đã kiểm tra. Không tự tô/xóa màu cho dòng chưa xác minh.
- Preview tạo trang hiện chỉ báo kế hoạch clone/reset màu, chưa kiểm tra tag từng
  service. Đọc template và hoàn thành đối chiếu remote trước khi xin duyệt tạo trang.
- Báo các dòng liên quan với nhãn cột tiếng Anh của trang release (xem **Chat report format**),
  rồi dry-run danh sách clear/update cụ thể và lấy approval trước remote write.
  Sau apply đọc lại trang để xác nhận tag mới có màu, tag chỉ copy không còn màu.

Ví dụ minh họa: `example-api | example/repo | v1.2.3 | v1.2.3 | v1.2.3 | clear row 4 | chỉ kế thừa từ ngày trước`.

- Today's page is created when missing and updated when it exists: numbered
  `max NNN + 1`, parented under the current monthly page, cloned from the newest
  daily page; numbering/template fall back to the newest month with daily pages.
  A missing monthly page stops the run with an explicit error.
- Repositories are derived from each row's own GitLab links (`/-/tree/`, `/-/tags/`).
- Tag series comes from the row's current tag (`c7-ttch-v0.0.341` -> prefix
  `c7-ttch-v0.0.`), highest `prefix + number` wins; `hotfix` tags are ignored.
- `version` cell -> newest tag (when it already holds one); `current version` rolls
  over to the previous `version`; `Release Tag` and `Docker image` follow the newest.
- Updated rows (service needs release) get the project highlight on every cell
  (`class="highlight-<color>"` plus `data-highlight-colour`) — Confluence renders
  from the class, so both are written.
- Rows sharing one repository with different current tags (append-only logs such as
  `alleyway-portal`, `ttch-migration`) are marked `skip: ambiguous` and left alone.
- Cache: `cache.json` next to this skill stores service->repo and tag lists per
  group; stale entries refresh in parallel with a 15s SSH connect timeout.
- Before PUT, the script checks that the page version still equals the version of the
  body it edited. It submits that original version plus one; changes before the check
  abort locally and changes after it conflict at Confluence. Re-run and review on conflict.
- After every apply the page is re-read and highlights are verified.

## Output

The CLI prints a full diagnostic table for a dry run:

```
| No | Service | Tag | Status |
```

Status: `update: <fields>`, `paint: purple`, `up-to-date`, `skip: ambiguous`,
`skip: no tag`, `error:<message>`.

After `--apply`: `=== SERVICES TO RELEASE ===` (`| No | Service | Tag |`) or
`painted purple: N, N`, then `cleared highlights: N, N`, then the applied counts
and `release page: <url>`, then `=== VERIFY HIGHLIGHT ===`
(`| No | Service | Highlight | Result |` with `ok`/`MISMATCH`).

`=== RELEASE PAGE ===` (`| No | Service | Tag | Highlight |` for every service on
the page) prints after every run.

## Chat report format

- Write the release report in English. Use the page's exact field names and casing
  for page values: `No`, `Service`, `version`, `current version`, `Release Tag`,
  `Docker image`, `Status`. Do not rename `Release Tag` to "Git tag" or `Docker image`
  to "Dev image": they describe different facts. Other page fields (for example
  `Branch`, `Release Note`, `Test`) are included only when relevant and read.
- Lead with the project, the linked daily page (title/ID and version when known),
  and `Dry run` or `Applied`. Show only requested, changed, highlighted, or
  unverified rows rather than pasting the CLI's entire `=== RELEASE PAGE ===` table.
  If no tag changed, say so instead of implying a fresh release from a copied tag.
- For page updates, use `| No | Service | version | current version | Release Tag |
  Docker image | Action |` as the compact table. Each page-field value must come
  from that row; `Action` is the proposed/applied change (including paint/clear),
  not the page's `Status` field. Omit unchanged columns only when the user asks for
  a narrower comparison. Before approval, state exactly which rows and fields
  will change; after approval, verify the affected rows by re-reading the page.
- When comparing with Git or a dev deployment, add separate, explicitly sourced
  columns `Latest Git tag` and `Dev image (observed)`, or a short comparison table
  with those headings. Compare the tag's commit to the deployed image digest/tag
  only when verified; a matching commit does not prove a Nexus release-tag image
  exists or that STG is deployed. Never replace page values with observed values
  without an approved page update.
- Report missing repositories, ambiguous tags, and unverified images separately
  as `Unverified`. Retain the Nexus-specific `Service | Git tag | Full Docker image |
  Nexus verification` format when the user explicitly requests full Nexus images.

## Report back

Use the compact chat format above: identify the page and mode, show affected rows
and their verified sources, and state the re-read result (including `MISMATCH`).
