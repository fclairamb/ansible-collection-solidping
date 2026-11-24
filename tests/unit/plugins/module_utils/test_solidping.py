# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingError,
    changed_fields,
    diff_of,
    find_one,
    format_api_error,
    mask_secrets,
    parse_timestamp,
    same_set,
    same_timestamp,
    same_value,
    subset_matches,
)


@pytest.mark.parametrize('desired, current, expected', [
    ('a', 'a', True),
    ('a', 'b', False),
    ('', None, True),
    (None, '', True),
    ({}, None, True),
    ([], None, True),
    (1, 1.0, True),
    (True, 1, False),
    (False, None, False),
    ({'a': 1}, {'a': 1}, True),
    ({'a': 1}, {'a': 1, 'b': 2}, False),
    (['a', 'b'], ['b', 'a'], False),
])
def test_same_value(desired, current, expected):
    assert same_value(desired, current) is expected


def test_subset_matches_ignores_server_keys():
    assert subset_matches({'url': 'https://acme.com'}, {'url': 'https://acme.com', 'method': 'GET'})
    assert not subset_matches({'url': 'https://acme.com/x'}, {'url': 'https://acme.com'})
    assert not subset_matches({'timeout': 5}, {})
    assert subset_matches({}, None)


def test_same_set():
    assert same_set(['b', 'a'], ['a', 'b'])
    assert same_set(None, [])
    assert not same_set(['a'], ['a', 'b'])


@pytest.mark.parametrize('desired, current, expected', [
    ('2026-12-01T02:00:00+01:00', '2026-12-01T01:00:00Z', True),
    ('2026-12-01T01:00:00Z', '2026-12-01T01:00:00.000Z', True),
    ('2026-12-01T01:00:00Z', '2026-12-01T01:00:01Z', False),
    ('2026-12-01T01:00:00-0230', '2026-12-01T03:30:00Z', True),
    ('', None, True),
    ('2026-12-01T01:00:00Z', None, False),
    ('tomorrow', 'tomorrow', True),
])
def test_same_timestamp(desired, current, expected):
    assert same_timestamp(desired, current) is expected


def test_parse_timestamp_rejects_garbage():
    assert parse_timestamp('not a date') is None
    assert parse_timestamp(None) is None


def test_changed_fields_skips_unmanaged_keys():
    current = {'name': 'Website', 'period': '00:01:00', 'config': {'url': 'https://acme.com', 'method': 'GET'}}
    desired = {'name': 'Website', 'period': '00:02:00', 'description': None,
               'config': {'url': 'https://acme.com'}}
    assert changed_fields(current, desired, {'config': subset_matches}) == {'period': '00:02:00'}


def test_diff_of_masks_secrets():
    diff = diff_of({'password': None, 'name': 'a'}, {'password': 'x', 'name': 'b'}, ['password'])
    assert diff == {'before': {'password': None, 'name': 'a'}, 'after': {'password': '********', 'name': 'b'}}


def test_mask_secrets_copies():
    values = {'token': 'abc', 'url': 'https://acme.com'}
    assert mask_secrets(values, ['token', 'other']) == {'token': '********', 'url': 'https://acme.com'}
    assert values['token'] == 'abc'


def test_find_one():
    items = [{'name': 'a', 'uid': '1'}, {'name': 'b', 'uid': '2'}, {'name': 'b', 'uid': '3'}]
    assert find_one(items, 'name', 'a', 'channels')['uid'] == '1'
    assert find_one(items, 'name', 'c', 'channels') is None
    with pytest.raises(SolidPingError):
        find_one(items, 'name', 'b', 'channels')


def test_format_api_error():
    raw = ('{"title": "Validation failed", "code": "VALIDATION_ERROR", "detail": "bad input",'
           ' "fields": [{"name": "period", "message": "must be HH:MM:SS"}]}')
    message, code = format_api_error(400, raw)
    assert code == 'VALIDATION_ERROR'
    assert message == 'Validation failed: bad input\n  - period: must be HH:MM:SS (VALIDATION_ERROR, HTTP 400)'
    assert format_api_error(502, 'Bad gateway') == ('HTTP 502: Bad gateway', None)
    assert format_api_error(500, '') == ('HTTP 500', None)
