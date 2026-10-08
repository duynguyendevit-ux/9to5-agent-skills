"""Offline checks for approved diagram artifacts and Confluence page-link anchors.

No credentials, filesystem reads or network requests. The caller verifies page
identity separately and supplies artifacts/hashes from the approved render manifest.
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
import urllib.parse


class _Anchors(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


def _origin(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("Expected an HTTP(S) origin without credentials")
    return parts.scheme, parts.hostname, parts.port or (443 if parts.scheme == "https" else 80)


def has_page_link(view, page_id, *, base_url, space=None, title=None):
    """Match a same-origin page anchor; this does not prove the target exists."""
    page_id = str(page_id)
    origin = _origin(base_url)
    parser = _Anchors()
    parser.feed(view)
    for link in parser.links:
        href = link.get("href")
        if not href or href.startswith("#") or "unresolved" in link.get("class", "").casefold():
            continue
        if link.get("data-linked-resource-type", "page") != "page":
            continue
        resource_id = link.get("data-linked-resource-id")
        if resource_id and resource_id != page_id:
            continue
        try:
            url = urllib.parse.urljoin(base_url.rstrip("/") + "/", href)
            if _origin(url) != origin:
                continue
            parts = urllib.parse.urlsplit(url)
            query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
        except ValueError:
            continue
        if "pageId" in query:
            if parts.path.endswith("/pages/viewpage.action") and query["pageId"] == [page_id]:
                return True
            continue
        display = parts.path.split("/display/", 1)
        if len(display) != 2:
            continue
        route = display[1].split("/")
        if len(route) != 2:
            continue
        route_space, route_title = map(urllib.parse.unquote_plus, route)
        if space is not None and route_space != space:
            continue
        if title is not None and route_title != title:
            continue
        if resource_id == page_id or (space is not None and title is not None):
            return True
    return False


def verify_diagram_label(label, source, image, *, source_sha256, image_sha256):
    """Check a label and artifact hashes from a previously approved render manifest."""
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != source_sha256:
        raise ValueError("Reviewed diagram source hash mismatch")
    if hashlib.sha256(image).hexdigest() != image_sha256:
        raise ValueError("Reviewed diagram image hash mismatch")
    if not label or label not in source:
        raise ValueError("Diagram label absent from reviewed source")
    return True
