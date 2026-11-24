# -*- coding: utf-8 -*-
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible_collections.fclairamb.solidping.plugins.modules import status_page_section as section


class FakeAPI(object):
    """Records the requests on the resources of one section."""

    def __init__(self, resources):
        self.resources = [dict(r) for r in resources]
        self.calls = []
        self.next_uid = 100

    def org_path(self, *segments):
        return '/' + '/'.join(segments)

    def list(self, path):
        return [dict(r) for r in self.resources]

    def request(self, method, path, body=None):
        self.calls.append((method, path.split('/resources')[-1], body))
        if method == 'POST' and path.endswith('/reorder'):
            order = body['uids']
            self.resources.sort(key=lambda r: order.index(r['uid']))
            for i, res in enumerate(self.resources):
                res['position'] = i + 1
            return None
        if method == 'POST':
            self.next_uid += 1
            created = dict(body, uid=str(self.next_uid), position=len(self.resources) + 1)
            self.resources.append(created)
            return created
        if method == 'PATCH':
            uid = path.rsplit('/', 1)[-1]
            for res in self.resources:
                if res['uid'] == uid:
                    res.update(body)
        return None

    def delete(self, path):
        uid = path.rsplit('/', 1)[-1]
        self.calls.append(('DELETE', uid, None))
        self.resources = [r for r in self.resources if r['uid'] != uid]


def want(check, name=''):
    return {'checkUid': check, 'publicName': name, 'explanation': ''}


def test_resources_differ():
    current = [{'uid': '1', 'checkUid': 'a', 'publicName': 'A', 'position': 1}]
    assert not section.resources_differ(current, [want('a', 'A')])
    assert section.resources_differ(current, [want('a', 'B')])
    assert section.resources_differ(current, [want('b', 'A')])
    assert section.resources_differ(current, [])


def test_selector_resources_are_ignored():
    api = FakeAPI([
        {'uid': '1', 'checkUid': 'a', 'position': 1, 'managedBySelector': True},
        {'uid': '2', 'checkUid': 'b', 'publicName': 'B', 'position': 2},
    ])
    assert [r['uid'] for r in section.curated(api, 'p', 's')] == ['2']


def test_apply_resources_adds_updates_removes_and_orders():
    api = FakeAPI([
        {'uid': '1', 'checkUid': 'a', 'publicName': 'A', 'position': 1},
        {'uid': '2', 'checkUid': 'b', 'publicName': 'B', 'position': 2},
        {'uid': '3', 'checkUid': 'c', 'publicName': 'C', 'position': 3},
    ])
    section.apply_resources(api, 'p', 's', [want('c', 'C'), want('d', 'D'), want('a', 'A2')])

    methods = [call[0] for call in api.calls]
    assert methods.count('POST') == 2  # the new component, then the reorder
    assert ('DELETE', '2', None) in api.calls
    assert [r['checkUid'] for r in section.curated(api, 'p', 's')] == ['c', 'd', 'a']
    assert [r['publicName'] for r in section.curated(api, 'p', 's')] == ['C', 'D', 'A2']


def test_apply_resources_in_order_does_not_reorder():
    api = FakeAPI([
        {'uid': '1', 'checkUid': 'a', 'publicName': 'A', 'position': 1},
        {'uid': '2', 'checkUid': 'b', 'publicName': 'B', 'position': 2},
    ])
    section.apply_resources(api, 'p', 's', [want('a', 'A'), want('b', 'B')])
    assert api.calls == []
