"""Offline checks for diagram artifacts, page-link anchors and flat HTML tables.

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


class _Tables(HTMLParser):
    """Bounded HTML reader; unsupported table structure fails explicitly."""

    _blocks = {"p", "div", "br", "li", "ul", "ol", "pre", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = self.row = self.cell = None

    def _finish_cell(self):
        if self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None

    def _finish_row(self):
        self._finish_cell()
        if self.row is not None:
            if not self.row:
                raise ValueError("Empty HTML table row")
            self.table.append(self.row)
            self.row = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.table is not None:
                raise ValueError("Nested HTML tables are unsupported")
            self.table = []
        elif self.table is not None and tag == "tr":
            self._finish_row()
            self.row = []
        elif self.table is not None and tag in ("td", "th"):
            if self.row is None:
                raise ValueError("HTML table cell without a row")
            for name, value in attrs:
                if name in ("rowspan", "colspan") and value != "1":
                    raise ValueError("Merged HTML table cells are unsupported")
            self._finish_cell()
            self.cell = []
        elif self.cell is not None:
            if tag in ("script", "style", "template"):
                raise ValueError("Non-prose HTML table cell content is unsupported")
            if tag in self._blocks:
                self.cell.append(" ")

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)
        elif self.table is not None and text.strip():
            raise ValueError("HTML table text outside a cell is unsupported")

    def handle_endtag(self, tag):
        if self.table is None:
            return
        if tag in ("td", "th"):
            if self.cell is None:
                raise ValueError("Unexpected HTML table cell end")
            self._finish_cell()
        elif tag in ("tr", "thead", "tbody", "tfoot"):
            self._finish_row()
        elif tag == "table":
            self._finish_row()
            if not self.table or any(len(row) != len(self.table[0]) for row in self.table):
                raise ValueError("Empty or ragged HTML table")
            self.tables.append(self.table)
            self.table = None
        elif self.cell is not None and tag in self._blocks:
            self.cell.append(" ")


def html_tables(view):
    """Return flat rectangular tables' normalized text, not links or CSS semantics.

    HTML void elements/entities and omitted row/cell end tags are accepted.
    Nested/merged/ragged or unclosed tables raise ValueError. No network or writes.
    """
    parser = _Tables()
    parser.feed(view)
    parser.close()
    if parser.table is not None:
        raise ValueError("Unclosed HTML table")
    return parser.tables


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
