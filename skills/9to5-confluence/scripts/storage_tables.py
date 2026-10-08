"""Pure, fail-closed helpers for rectangular Confluence storage tables."""
from decimal import Decimal, InvalidOperation
import html
import re
import xml.etree.ElementTree as ET

TABLE = re.compile(r'<table\b[^>]*>.*?</table>', re.S)
ROW = re.compile(r'<tr\b[^>]*>.*?</tr>', re.S)
CELL = re.compile(r'(<t[dh]\b[^>]*>)(.*?)(</t[dh]>)', re.S)
GROUP = re.compile(r'(<colgroup\b[^>]*>)(.*?)(</colgroup>)', re.S)
COL = re.compile(r'<col\b[^>]*/>')
STYLE = re.compile(r'style="width:\s*([\d.]+)%;"')

def _tree(body):
    try:
        return ET.fromstring('<root xmlns:ac="urn:ac" xmlns:ri="urn:ri">' + body + '</root>')
    except (ET.ParseError, TypeError):
        raise ValueError('Malformed storage XHTML; content withheld') from None

def _text(node):
    return re.sub(r'\s+', ' ', ''.join(node.itertext())).strip()

def _selected(body, table_index):
    nodes = _tree(body).findall('.//table')
    matches = list(TABLE.finditer(body))
    if (not isinstance(table_index, int) or isinstance(table_index, bool)
            or table_index < 0 or table_index >= len(nodes) or len(nodes) != len(matches)):
        raise ValueError('Unresolved table selection or unsupported nested markup')
    node, match = nodes[table_index], matches[table_index]
    if node.findall('.//table'):
        raise ValueError('Nested tables are unsupported')
    rows = node.findall('.//tr')
    raw_rows = list(ROW.finditer(match.group()))
    if not rows or len(rows) != len(raw_rows):
        raise ValueError('Unresolved table rows')
    headers = [_text(cell) for cell in rows[0]]
    if not headers or len(set(headers)) != len(headers) or any(not h for h in headers):
        raise ValueError('Empty or duplicate table headers')
    for row, raw in zip(rows, raw_rows):
        if len(row) != len(headers) or len(list(CELL.finditer(raw.group()))) != len(headers):
            raise ValueError('Nonrectangular tables are unsupported')
        for cell in row:
            if cell.tag not in ('td', 'th') or cell.get('colspan', '1') != '1' or cell.get('rowspan', '1') != '1':
                raise ValueError('Merged or unsupported table cells')
    if 'Service' in headers:
        values = [_text(row[headers.index('Service')]) for row in rows[1:]]
        values = [value for value in values if value]
        if len(set(values)) != len(values):
            raise ValueError('Duplicate service rows are unsupported')
    return match, headers, rows, raw_rows

def _width(value):
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid column width') from None
    if not number.is_finite() or not 0 < number < 100:
        raise ValueError('Column width must be between 0 and 100 percent')
    return number

def _expanded_group(table, expected_count, index, width):
    groups = list(GROUP.finditer(table))
    if not groups:
        return table
    if len(groups) != 1:
        raise ValueError('Multiple colgroups are unsupported')
    group = groups[0]
    cols = list(COL.finditer(group.group(2)))
    node_cols = _tree(group.group()).findall('.//col')
    if len(cols) != expected_count or len(node_cols) != expected_count:
        raise ValueError('Colgroup count mismatch; repair an explicitly known missing column first')
    widths = []
    for raw, node in zip(cols, node_cols):
        match = STYLE.search(raw.group())
        if not match or node.get('span', '1') != '1' or not re.fullmatch(r'width:\s*[\d.]+%;', node.get('style', '')):
            raise ValueError('Only individual explicit percentage-width columns are supported')
        try:
            number = Decimal(match[1])
        except InvalidOperation:
            raise ValueError('Invalid existing column width') from None
        if not number.is_finite() or number <= 0:
            raise ValueError('Invalid existing column width')
        widths.append(number)
    scale = (Decimal(100) - width) / sum(widths)
    expanded = []
    for raw, old_width in zip(cols, widths):
        value = format((old_width * scale).quantize(Decimal('0.000001')), 'f').rstrip('0').rstrip('.')
        expanded.append(STYLE.sub('style="width: ' + value + '%;"', raw.group(), count=1))
    new_width = format(width, 'f').rstrip('0').rstrip('.') if '.' in format(width, 'f') else format(width, 'f')
    expanded.insert(index, '<col style="width: ' + new_width + '%;" />')
    replacement = group.group(1) + ''.join(expanded) + group.group(3)
    return table[:group.start()] + replacement + table[group.end():]

def _replace_table(body, match, table):
    result = body[:match.start()] + table + body[match.end():]
    _tree(result)
    return result

def replace_cell(body, service, column, value, *, table_index=0):
    match, headers, nodes, rows = _selected(body, table_index)
    if 'Service' not in headers or column not in headers:
        raise ValueError('Required service/field header not found')
    si, ci = headers.index('Service'), headers.index(column)
    indexes = [i for i, row in enumerate(nodes[1:], 1) if _text(row[si]) == service]
    if len(indexes) != 1:
        raise ValueError('Service row is missing or ambiguous')
    row = rows[indexes[0]]
    cells = list(CELL.finditer(row.group()))
    cell = cells[ci]
    updated = row.group()[:cell.start(2)] + value + row.group()[cell.end(2):]
    table = match.group()[:row.start()] + updated + match.group()[row.end():]
    result = _replace_table(body, match, table)
    _selected(result, table_index)
    return result

def insert_column(body, name, after, *, width=8, table_index=0):
    if not isinstance(name, str) or not name.strip():
        raise ValueError('Column name is required')
    name = name.strip()
    match, headers, _, rows = _selected(body, table_index)
    if after not in headers:
        raise ValueError('Insertion header not found')
    index = headers.index(after) + 1
    if name in headers:
        if headers.index(name) != index:
            raise ValueError('Existing column is in a different position')
        return body
    new_width = _width(width)
    table = match.group()
    for position in range(len(rows) - 1, -1, -1):
        row = rows[position]
        neighbor = list(CELL.finditer(row.group()))[index - 1]
        inner = '<p>' + html.escape(name) + '</p>' if position == 0 else '<p><br /></p>'
        new = neighbor.group(1) + inner + neighbor.group(3)
        offset = row.start() + neighbor.end()
        table = table[:offset] + new + table[offset:]
    table = _expanded_group(table, len(headers), index, new_width)
    result = _replace_table(body, match, table)
    _selected(result, table_index)
    return result

def repair_colgroup(body, omitted_header, *, width=8, table_index=0):
    match, headers, _, _ = _selected(body, table_index)
    if omitted_header not in headers:
        raise ValueError('Explicit omitted header not found')
    groups = list(GROUP.finditer(match.group()))
    if not groups:
        return body
    if len(groups) != 1:
        raise ValueError('Multiple colgroups are unsupported')
    count = len(list(COL.finditer(groups[0].group(2))))
    if count == len(headers):
        return body
    if count != len(headers) - 1:
        raise ValueError('Repair requires exactly one known missing colgroup column')
    updated = _expanded_group(match.group(), count, headers.index(omitted_header), _width(width))
    return _replace_table(body, match, updated)

def storage_matches(approved, saved, *, width_tolerance='0.000002'):
    """Compare all body content, allowing only specified serialization differences."""
    try:
        tolerance = Decimal(str(width_tolerance))
    except InvalidOperation:
        raise ValueError('Invalid width tolerance') from None
    if not tolerance.is_finite() or not 0 <= tolerance <= Decimal('0.00001'):
        raise ValueError('Width tolerance must be bounded by 0.00001 percent')
    def same(a, b):
        if a.tag != b.tag or (a.text or '') != (b.text or '') or (a.tail or '') != (b.tail or '') or len(a) != len(b):
            return False
        ignore = '{urn:ac}macro-id' if a.tag == '{urn:ac}structured-macro' else None
        aa = {k: v for k, v in a.attrib.items() if k != ignore}
        bb = {k: v for k, v in b.attrib.items() if k != ignore}
        if a.tag == 'col' and set(aa) == set(bb) and 'style' in aa:
            ma = re.fullmatch(r'width:\s*([\d.]+)%;', aa['style'])
            mb = re.fullmatch(r'width:\s*([\d.]+)%;', bb['style'])
            if ma and mb:
                try:
                    if abs(Decimal(ma[1]) - Decimal(mb[1])) <= tolerance:
                        aa['style'] = bb['style']
                except InvalidOperation:
                    return False
        return aa == bb and all(same(x, y) for x, y in zip(a, b))
    return same(_tree(approved), _tree(saved))
