# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Shared client and helpers of the fclairamb.solidping modules."""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import datetime
import json
import re

from ansible.module_utils.basic import env_fallback
from ansible.module_utils.six.moves.urllib.parse import quote, urlencode
from ansible.module_utils.urls import fetch_url

PAGE_LIMIT = 100
MAX_PAGES = 1000


def solidping_argument_spec():
    """Connection options shared by every module (see the `solidping` doc fragment)."""
    return dict(
        url=dict(
            type='str',
            aliases=['endpoint'],
            fallback=(env_fallback, ['SOLIDPING_URL', 'SOLIDPING_ENDPOINT']),
        ),
        token=dict(
            type='str',
            no_log=True,
            fallback=(env_fallback, ['SOLIDPING_TOKEN']),
        ),
        org=dict(
            type='str',
            fallback=(env_fallback, ['SOLIDPING_ORG']),
        ),
        validate_certs=dict(type='bool', default=True),
        ca_path=dict(type='path'),
        timeout=dict(type='int', default=30),
    )


class SolidPingError(Exception):
    """An error answered by the API (or a transport failure)."""

    def __init__(self, message, status=None, code=None, body=None):
        super(SolidPingError, self).__init__(message)
        self.status = status
        self.code = code
        self.body = body


def format_api_error(status, raw):
    """Turn a `{title, code, detail, fields}` answer into one readable line."""
    data = None
    if raw:
        try:
            data = json.loads(raw)
        except ValueError:
            data = None

    if not isinstance(data, dict) or not data.get('title'):
        text = (raw or '').strip()
        if text and len(text) < 300:
            return 'HTTP {0}: {1}'.format(status, text), None
        return 'HTTP {0}'.format(status), None

    message = data['title']
    detail = data.get('detail')
    if detail and detail.lower() != message.lower():
        message += ': ' + detail
    for field in data.get('fields') or []:
        message += '\n  - {0}: {1}'.format(field.get('name'), field.get('message'))
    code = data.get('code')
    if code:
        message += ' ({0}, HTTP {1})'.format(code, status)
    else:
        message += ' (HTTP {0})'.format(status)
    return message, code


class SolidPingAPI(object):
    """Thin client over the v1 REST API, bound to one organization."""

    def __init__(self, module):
        self.module = module
        params = module.params
        # Not `required` in the argument spec: they usually come from
        # module_defaults or the environment, which linters do not see.
        missing = [name for name in ('url', 'token', 'org') if not params.get(name)]
        if missing:
            module.fail_json(msg='missing the connection option(s) {0}: set them on the task, in module_defaults '
                                 '(group/fclairamb.solidping.solidping) or with the SOLIDPING_URL, SOLIDPING_TOKEN '
                                 'and SOLIDPING_ORG environment variables'.format(', '.join(missing)))
        self.base_url = params['url'].rstrip('/')
        self.org = params['org']
        self.token = params['token']
        self.timeout = params['timeout']
        self.ca_path = params.get('ca_path')

    def org_path(self, *segments):
        parts = [quote(str(s), safe='') for s in segments]
        return '/api/v1/orgs/{0}/{1}'.format(quote(self.org, safe=''), '/'.join(parts))

    def request(self, method, path, body=None, query=None):
        """Send a request. Returns the decoded JSON (None for an empty body).

        Raises SolidPingError on a transport failure or an HTTP status >= 400.
        """
        url = self.base_url + path
        if query:
            url += '?' + urlencode(query)

        headers = {
            'Accept': 'application/json',
            'Authorization': 'Bearer ' + self.token,
            'User-Agent': 'ansible-fclairamb.solidping',
        }
        data = None
        if body is not None:
            data = json.dumps(body)
            headers['Content-Type'] = 'application/json'

        kwargs = dict(data=data, headers=headers, method=method, timeout=self.timeout, use_netrc=False)
        if self.ca_path:
            kwargs['ca_path'] = self.ca_path

        resp, info = fetch_url(self.module, url, **kwargs)
        status = info.get('status', -1)

        raw = None
        if resp is not None:
            raw = resp.read()
        elif 'body' in info:
            raw = info['body']
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8', errors='replace')

        if status == -1:
            raise SolidPingError('{0} {1}: {2}'.format(method, path, info.get('msg')), status=status)

        if status >= 400:
            message, code = format_api_error(status, raw)
            raise SolidPingError('{0} {1}: {2}'.format(method, path, message), status=status, code=code, body=raw)

        if not raw or not raw.strip():
            return None
        try:
            return json.loads(raw)
        except ValueError:
            raise SolidPingError('{0} {1}: the answer is not JSON'.format(method, path), status=status, body=raw)

    def get_or_none(self, path):
        """GET a resource, None when it does not exist (404)."""
        try:
            return self.request('GET', path)
        except SolidPingError as e:
            if e.status == 404:
                return None
            raise

    def delete(self, path):
        """DELETE a resource. A resource already gone is not an error."""
        try:
            self.request('DELETE', path)
        except SolidPingError as e:
            if e.status != 404:
                raise

    def list(self, path, query=None):
        """Every item of a `{data: [...]}` list, following the cursor pagination."""
        query = dict(query or {})
        query.setdefault('limit', PAGE_LIMIT)
        items = []
        for dummy in range(MAX_PAGES):
            page = self.request('GET', path, query=query) or {}
            items.extend(page.get('data') or [])
            cursor = (page.get('pagination') or {}).get('cursor')
            if not cursor or not page.get('data'):
                return items
            query['cursor'] = cursor
        raise SolidPingError('GET {0}: more than {1} pages'.format(path, MAX_PAGES))

    # Lookups shared by several modules.

    def resolve_check_uid(self, ref):
        """Uid of a check given by uid or slug."""
        check = self.get_or_none(self.org_path('checks', ref))
        if check is None:
            raise SolidPingError('no check with the uid or slug `{0}`'.format(ref), status=404)
        return check['uid']

    def resolve_check_group_uid(self, ref):
        """Uid of a check group given by uid or slug."""
        group = self.get_or_none(self.org_path('check-groups', ref))
        if group is not None and group.get('uid'):
            return group['uid']
        for group in self.list(self.org_path('check-groups')):
            if ref in (group.get('uid'), group.get('slug')):
                return group['uid']
        raise SolidPingError('no check group with the uid or slug `{0}`'.format(ref), status=404)

    def resolve_status_page(self, ref):
        """The status page given by uid or slug."""
        page = self.get_or_none(self.org_path('status-pages', ref))
        if page is None:
            raise SolidPingError('no status page with the uid or slug `{0}`'.format(ref), status=404)
        return page


def find_one(items, key, value, what):
    """The single item whose `key` is `value`, None when there is none."""
    matches = [item for item in items if item.get(key) == value]
    if len(matches) > 1:
        raise SolidPingError(
            '{0} {1} match {2} `{3}`: pass `uid` to pick one'.format(len(matches), what, key, value))
    return matches[0] if matches else None


# Comparison helpers. The API normalizes some values (empty strings read back
# as null, timestamps in UTC, numbers as floats), so desired and current
# values are compared through these instead of `==`.

def empty_to_none(value):
    if value in ('', [], {}):
        return None
    return value


def same_value(desired, current):
    """Loose equality: `None`/empty alike, numbers by value, dicts and lists deep."""
    desired = empty_to_none(desired)
    current = empty_to_none(current)
    if desired is None or current is None:
        return desired is None and current is None
    if isinstance(desired, bool) or isinstance(current, bool):
        return desired is current
    if isinstance(desired, (int, float)) and isinstance(current, (int, float)):
        return float(desired) == float(current)
    if isinstance(desired, dict) and isinstance(current, dict):
        if set(desired) != set(current):
            return False
        return all(same_value(desired[k], current[k]) for k in desired)
    if isinstance(desired, list) and isinstance(current, list):
        if len(desired) != len(current):
            return False
        return all(same_value(d, c) for d, c in zip(desired, current))
    return desired == current


def subset_matches(desired, current):
    """Whether every key of `desired` has the same value in `current`.

    Used for `config` and `settings`: the server adds defaults of its own,
    only the keys the playbook writes are compared.
    """
    current = current or {}
    for key, value in (desired or {}).items():
        if not same_value(value, current.get(key)):
            return False
    return True


def same_set(desired, current):
    """Order-insensitive comparison of two lists of strings."""
    return sorted(desired or []) == sorted(current or [])


_TS_RE = re.compile(
    r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$', re.IGNORECASE)


def parse_timestamp(value):
    """Parse an RFC 3339 timestamp into an aware UTC datetime (None if it is not one)."""
    if not value:
        return None
    match = _TS_RE.match(value.strip())
    if not match:
        return None
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    fraction = match.group(7)
    micro = int(round(float(fraction) * 1000000)) if fraction else 0
    if micro >= 1000000:
        micro = 999999
    zone = match.group(8)
    offset = datetime.timedelta(0)
    if zone and zone.upper() != 'Z':
        sign = -1 if zone[0] == '-' else 1
        digits = zone[1:].replace(':', '')
        offset = sign * datetime.timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
    naive = datetime.datetime(year, month, day, hour, minute, second, micro)
    return naive - offset


def same_timestamp(desired, current):
    if empty_to_none(desired) is None or empty_to_none(current) is None:
        return empty_to_none(desired) is None and empty_to_none(current) is None
    parsed_desired = parse_timestamp(desired)
    parsed_current = parse_timestamp(current)
    if parsed_desired is None or parsed_current is None:
        return desired == current
    return parsed_desired == parsed_current


def mask_secrets(values, secret_keys):
    """Copy of `values` with the given keys replaced by a placeholder (for diffs)."""
    out = dict(values or {})
    for key in secret_keys or []:
        if out.get(key) is not None:
            out[key] = '********'
    return out


def compact(values):
    """Drop the None values of a dict."""
    return dict((k, v) for k, v in values.items() if v is not None)


def changed_fields(current, desired, comparators=None):
    """The entries of `desired` (API keys, None means unmanaged) that differ from `current`.

    `comparators` maps an API key to a function (desired, current) -> bool used
    instead of `same_value`.
    """
    comparators = comparators or {}
    out = {}
    for key, value in desired.items():
        if value is None:
            continue
        compare = comparators.get(key, same_value)
        if not compare(value, (current or {}).get(key)):
            out[key] = value
    return out


def diff_of(current, changes, secret_keys=None):
    """A `{before, after}` diff restricted to the changed keys."""
    before = dict((k, (current or {}).get(k)) for k in changes)
    after = dict(changes)
    return dict(before=mask_secrets(before, secret_keys), after=mask_secrets(after, secret_keys))


def fail_api(module, error, **kwargs):
    module.fail_json(msg=str(error), status=getattr(error, 'status', None), **kwargs)
