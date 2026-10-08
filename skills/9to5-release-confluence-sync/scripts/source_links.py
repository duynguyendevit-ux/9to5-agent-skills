"""Construct release-table code links; callers verify mapping/branch separately."""
import html
import re
from urllib.parse import quote, urlsplit


def _web_base(web_base):
    if not isinstance(web_base, str):
        raise ValueError('Invalid web base; value withheld')
    parts = urlsplit(web_base)
    if (parts.scheme not in ('http', 'https') or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment
            or any(c.isspace() or ord(c) < 32 for c in web_base)):
        raise ValueError('Invalid code web base; value withheld')
    try:
        parts.port
    except ValueError:
        raise ValueError('Invalid web port; value withheld') from None
    return web_base.rstrip('/')


def source_urls(web_base, repository, branch):
    web_base = _web_base(web_base)
    if (not isinstance(repository, str) or len(repository.split('/')) < 2
            or any(not re.fullmatch(r'[A-Za-z0-9_.-]+', part) or part in ('.', '..', '-')
                   for part in repository.split('/'))):
        raise ValueError('Invalid repository path; value withheld')
    if (not isinstance(branch, str) or not branch or branch.startswith('-')
            or any(c.isspace() or ord(c) < 32 for c in branch)
            or any(c in branch for c in '~^:?*[\\') or '..' in branch
            or branch.startswith('/') or branch.endswith('/') or branch.endswith('.lock')
            or '@{' in branch or '//' in branch):
        raise ValueError('Invalid branch name; value withheld')
    root = web_base.rstrip('/') + '/' + repository
    return root, root + '/-/tree/' + quote(branch, safe='')


def source_cells(service, web_base, repository, branch):
    root, tree = source_urls(web_base, repository, branch)
    return (f'<p><a href="{html.escape(root, quote=True)}">{html.escape(service)}</a></p>',
            f'<p><a href="{html.escape(tree, quote=True)}">{html.escape(branch)}</a></p>')


def release_version_note(jira_base, project, version_id, name):
    """Build one overall note; callers verify version/project identity via Jira."""
    base = _web_base(jira_base)
    if not isinstance(project, str) or not re.fullmatch(r'[A-Z][A-Z0-9_]*', project):
        raise ValueError('Invalid Jira project key; value withheld')
    version_id = str(version_id)
    if not re.fullmatch(r'[1-9][0-9]*', version_id):
        raise ValueError('Invalid Jira version ID; value withheld')
    if not isinstance(name, str) or not name.strip() or any(ord(c) < 32 for c in name):
        raise ValueError('Invalid Jira version name; value withheld')
    url = base + '/projects/' + project + '/versions/' + version_id
    return ('<p><strong>Jira Release Version: </strong>'
            f'<a href="{html.escape(url, quote=True)}">{html.escape(name)}</a></p>')
