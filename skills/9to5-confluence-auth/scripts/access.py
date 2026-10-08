#!/usr/bin/env python3
"""Separate GitLab/Jira/Confluence PAT login with masked terminal input."""
import argparse
import fcntl
import getpass
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import warnings

import auth

SERVICES = {'confluence': '/rest/api/user/current', 'jira': '/rest/api/2/myself',
            'gitlab': '/api/v4/user'}
PUBLIC = ('git_ssh_base', 'confluence_space', 'jira_task')


def load(path):
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except Exception:
        raise auth.ConfigError('Cannot read JSON dotfile; values withheld') from None
    if not isinstance(value, dict):
        raise auth.ConfigError('Dotfile must contain an object')
    return value


def save(path, before, changes):
    """Preserve unrelated keys; reject concurrent edits; atomic private write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise auth.ConfigError('Refusing symlink dotfile')
    lock = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if load(path) != before:
            raise auth.ConfigError('Dotfile changed; retry from current configuration')
        merged = dict(before, **changes)
        fd, name = tempfile.mkstemp(prefix='.access-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as handle:
                os.fchmod(handle.fileno(), 0o600)
                json.dump(merged, handle, indent=2)
                handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
    finally:
        os.close(lock)


def resolve(service, path, endpoints=None):
    # Use the same endpoint/Confluence credential precedence as auth.py.
    if service == 'confluence':
        url, token, _ = auth.resolve(overlay_path=path, endpoints_path=endpoints)
        return url, token
    legacy = auth.read_mapping(auth.default_paths()[0], 'yaml')
    local = load(path)
    config = dict(legacy, **local)
    ep = auth.read_mapping(endpoints, 'json') if endpoints else {}
    url = (os.environ.get(service.upper() + '_URL') or ep.get(service + '_url')
           or config.get(service + '_url'))
    token = config.get(service + '_token') or os.environ.get(service.upper() + '_TOKEN')
    if service == 'jira' and not token:
        # zjira's generic token is Jira's legacy PAT, never a GitLab fallback.
        token = legacy.get('token')
    if url:
        url = auth.validate_url(url)
    if token and (not isinstance(token, str) or '\r' in token or '\n' in token):
        raise auth.ConfigError('Invalid PAT; value withheld')
    return url, token


def check(service, url, token):
    if service == 'confluence':
        return auth.check(url, token)
    if not url or not token:
        return {'status': 'missing-config', 'verified': False}
    headers = {'Accept': 'application/json'}
    headers['PRIVATE-TOKEN' if service == 'gitlab' else 'Authorization'] = token if service == 'gitlab' else 'Bearer ' + token
    try:
        request = urllib.request.Request(url + SERVICES[service], headers=headers)
        with auth.opener().open(request, timeout=20) as response:
            body = response.read(65537)
            if response.status != 200 or len(body) > 65536:
                return {'status': 'invalid-response', 'verified': False}
            data = json.loads(body)
            known = isinstance(data, dict) and bool(data.get('id') if service == 'gitlab' else data.get('key') or data.get('name') or data.get('accountId'))
            return {'status': 'authenticated' if known else 'unverified', 'verified': known}
    except urllib.error.HTTPError as exc:
        exc.close()
        return {'status': 'unauthenticated' if exc.code == 401 else 'forbidden' if exc.code == 403 else 'redirect-blocked' if 300 <= exc.code < 400 else 'unverified', 'verified': False, 'http_status': exc.code}
    except (ValueError, UnicodeError):
        return {'status': 'invalid-response', 'verified': False}
    except Exception:
        return {'status': 'network-error', 'verified': False}


def terminal():
    if not (sys.stdin.isatty() and sys.stderr.isatty()):
        raise auth.ConfigError('Interactive terminal required; run this command locally. Paste PAT only at the masked prompt')


def validate_public(key, value):
    if key == 'jira_task' and not re.fullmatch(r'[A-Z][A-Z0-9_]*-\d+', value):
        raise auth.ConfigError('Invalid Jira issue key')
    if key == 'confluence_space' and not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise auth.ConfigError('Invalid Confluence space key')
    if key == 'git_ssh_base':
        try:
            parsed = urllib.parse.urlsplit(value)
            if (parsed.scheme != 'ssh' or not parsed.hostname or not parsed.username
                    or parsed.password or parsed.path not in ('', '/')
                    or parsed.query or parsed.fragment or any(c.isspace() for c in value)):
                raise ValueError
            parsed.port
        except ValueError:
            raise auth.ConfigError('Git source must be an SSH base: ssh://user@host[:port]') from None
        value = value.rstrip('/')
    return value


def run(args):
    before = load(args.config)
    if args.command == 'configure':
        terminal()
        changes = {}
        for key in args.keys:
            if before.get(key) and not args.replace:
                continue
            value = input(key + ' (blank to skip): ').strip()
            if not value:
                continue
            changes[key] = validate_public(key, value)
        if changes:
            save(args.config, before, changes)
        return {'status': 'configured', 'saved_keys': sorted(changes)}
    services = list(SERVICES) if args.service == 'all' else [args.service]
    results = {}
    for service in services:
        url, token = resolve(service, args.config, args.endpoints)
        state = check(service, url, token)
        if args.command == 'login' and (args.replace or state['status'] in ('missing-config', 'unauthenticated')):
            terminal()
            if not url:
                url = auth.validate_url(input(service + ' base URL: ').strip())
            # User sees the exact destination before typing a new credential.
            print('PAT destination: ' + url, file=sys.stderr)
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                token = getpass.getpass(service + ' PAT (paste, input hidden): ').strip()
            if not token or '\r' in token or '\n' in token:
                raise auth.ConfigError('Empty or invalid PAT; nothing saved')
            state = check(service, url, token)
            if state['verified']:
                save(args.config, before, {service + '_url': url, service + '_token': token})
                before = load(args.config)
                state['saved'] = True
        results[service] = dict(state, url_present=bool(url), token_present=bool(token))
    return {'services': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=auth.default_paths()[1])
    parser.add_argument('--endpoints', type=Path)
    subs = parser.add_subparsers(dest='command', required=True)
    status = subs.add_parser('status'); status.add_argument('service', choices=[*SERVICES, 'all'])
    login = subs.add_parser('login'); login.add_argument('service', choices=SERVICES)
    login.add_argument('--replace', action='store_true', help='Explicit credential replacement in a terminal')
    config = subs.add_parser('configure'); config.add_argument('keys', nargs='+', choices=PUBLIC)
    config.add_argument('--replace', action='store_true', help='Explicitly change existing non-secret fields')
    args = parser.parse_args()
    try:
        report = run(args)
    except (auth.ConfigError, EOFError, KeyboardInterrupt) as exc:
        report = {'status': 'setup-incomplete', 'reason': str(exc) if isinstance(exc, auth.ConfigError) else 'Input cancelled'}
    except Exception:
        report = {'status': 'setup-failed', 'reason': 'Details withheld'}
    print(json.dumps(report))
    return 0 if report.get('status') == 'configured' or report.get('services') and all(x['verified'] for x in report['services'].values()) else 2


if __name__ == '__main__':
    raise SystemExit(main())
