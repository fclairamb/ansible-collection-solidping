#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: maintenance_window
short_description: Manage a SolidPing maintenance window
version_added: 0.1.0
description:
  - Create, update or delete a planned maintenance, during which the checks it covers raise no incident.
  - The window is identified by O(title), or by O(uid) to rename it.
  - Timestamps are compared as instants, so V(2026-12-01T02:00:00+01:00) matches the V(2026-12-01T01:00:00Z)
    the server returns.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.resource
options:
  state:
    description:
      - V(present) creates or updates the window, V(absent) deletes it.
    type: str
    choices: [present, absent]
    default: present
  title:
    description:
      - Title of the window. Identifies the window unless O(uid) is set, so it must be unique.
      - Required to create a window.
    type: str
  uid:
    description:
      - UID of an existing window. Takes precedence over O(title) to find the window.
    type: str
  description:
    description:
      - What the maintenance is about. An empty string clears it.
    type: str
  start_at:
    description:
      - Start, as an RFC 3339 timestamp (V(2026-12-01T02:00:00+01:00)). Required to create a window.
    type: str
  end_at:
    description:
      - End, as an RFC 3339 timestamp. Required to create a window.
    type: str
  recurrence:
    description:
      - How the window repeats. A new window does not repeat unless this is set.
    type: str
    choices: [none, daily, weekly, monthly]
  recurrence_end:
    description:
      - When a recurring window stops repeating, as an RFC 3339 timestamp. An empty string clears it.
    type: str
  checks:
    description:
      - UIDs or slugs of the checks under maintenance. Replaces the list, an empty list removes them all.
      - When omitted, the checks of the window are left as they are.
    type: list
    elements: str
  check_groups:
    description:
      - UIDs or slugs of the check groups under maintenance. Replaces the list, an empty list removes them all.
      - When omitted, the check groups of the window are left as they are.
    type: list
    elements: str
'''

EXAMPLES = r'''
- name: Nightly database maintenance
  fclairamb.solidping.maintenance_window:
    title: Nightly database backup
    start_at: "2026-12-01T02:00:00+01:00"
    end_at: "2026-12-01T02:30:00+01:00"
    recurrence: daily
    checks:
      - database
      - api

- name: Cancel it
  fclairamb.solidping.maintenance_window:
    title: Nightly database backup
    state: absent
'''

RETURN = r'''
maintenance_window:
  description:
    - The window as the server returns it, with its C(checks) and C(checkGroups) UIDs.
      In check mode, the predicted window.
    - Empty when O(state=absent).
  returned: always
  type: dict
  sample:
    uid: 5e842232-ee3e-49c1-8ce0-4d476d6427e1
    title: Nightly database backup
    startAt: "2026-12-01T01:00:00Z"
    endAt: "2026-12-01T01:30:00Z"
    recurrence: daily
    checks: [e90bd341-1c7a-4f7d-90c2-c6e20b3eedfc]
    checkGroups: []
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    changed_fields,
    diff_of,
    fail_api,
    find_one,
    same_set,
    same_timestamp,
    solidping_argument_spec,
)


def find_window(api, params):
    if params['uid']:
        return api.get_or_none(api.org_path('maintenance-windows', params['uid']))
    return find_one(api.list(api.org_path('maintenance-windows')), 'title', params['title'], 'maintenance windows')


def window_targets(api, uid):
    links = api.list(api.org_path('maintenance-windows', uid, 'checks'))
    checks = [link['checkUid'] for link in links if link.get('checkUid')]
    groups = [link['checkGroupUid'] for link in links if link.get('checkGroupUid')]
    return checks, groups


def main():
    argument_spec = dict(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        title=dict(type='str'),
        uid=dict(type='str'),
        description=dict(type='str'),
        start_at=dict(type='str'),
        end_at=dict(type='str'),
        recurrence=dict(type='str', choices=['none', 'daily', 'weekly', 'monthly']),
        recurrence_end=dict(type='str'),
        checks=dict(type='list', elements='str'),
        check_groups=dict(type='list', elements='str'),
    )
    argument_spec.update(solidping_argument_spec())

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[('title', 'uid')],
        supports_check_mode=True,
    )
    params = module.params
    api = SolidPingAPI(module)

    try:
        current = find_window(api, params)
        if params['uid'] and current is None and params['state'] == 'present':
            module.fail_json(msg='no maintenance window with the uid `{0}`'.format(params['uid']))

        if params['state'] == 'absent':
            if current is None:
                module.exit_json(changed=False, maintenance_window={})
            if not module.check_mode:
                api.delete(api.org_path('maintenance-windows', current['uid']))
            module.exit_json(changed=True, maintenance_window={},
                             diff=dict(before=dict(title=current.get('title')), after={}))

        checks = None
        if params['checks'] is not None:
            checks = [api.resolve_check_uid(ref) for ref in params['checks']]
        groups = None
        if params['check_groups'] is not None:
            groups = [api.resolve_check_group_uid(ref) for ref in params['check_groups']]

        desired = {
            'title': params['title'],
            'description': params['description'],
            'startAt': params['start_at'],
            'endAt': params['end_at'],
            'recurrence': params['recurrence'],
            'recurrenceEnd': params['recurrence_end'],
        }

        if current is None:
            missing = [opt for opt in ('title', 'start_at', 'end_at') if params[opt] is None]
            if missing:
                module.fail_json(msg='creating a maintenance window needs: {0}'.format(', '.join(missing)))
            body = dict((k, v) for k, v in desired.items() if v not in (None, ''))
            body.setdefault('recurrence', 'none')
            after = dict(body, checks=checks or [], checkGroups=groups or [])
            diff = dict(before={}, after=after)
            if module.check_mode:
                module.exit_json(changed=True, maintenance_window=after, diff=diff)
            window = api.request('POST', api.org_path('maintenance-windows'), body)
            if checks or groups:
                api.request('PUT', api.org_path('maintenance-windows', window['uid'], 'checks'),
                            {'checkUids': checks or [], 'checkGroupUids': groups or []})
            window['checks'], window['checkGroups'] = window_targets(api, window['uid'])
            module.exit_json(changed=True, maintenance_window=window, diff=diff)

        current_checks, current_groups = window_targets(api, current['uid'])
        current = dict(current, checks=current_checks, checkGroups=current_groups)

        changes = changed_fields(current, desired, {
            'startAt': same_timestamp,
            'endAt': same_timestamp,
            'recurrenceEnd': same_timestamp,
        })
        # An explicit null clears these (an empty string is refused).
        for key in ('description', 'recurrenceEnd'):
            if changes.get(key) == '':
                changes[key] = None

        targets = {}
        if checks is not None and not same_set(checks, current_checks):
            targets['checks'] = checks
        if groups is not None and not same_set(groups, current_groups):
            targets['checkGroups'] = groups

        if not changes and not targets:
            module.exit_json(changed=False, maintenance_window=current)

        diff = diff_of(current, dict(changes, **targets))
        if module.check_mode:
            module.exit_json(changed=True, maintenance_window=dict(current, **dict(changes, **targets)), diff=diff)

        window = current
        if changes:
            window = api.request('PATCH', api.org_path('maintenance-windows', current['uid']), changes)
        if targets:
            api.request('PUT', api.org_path('maintenance-windows', current['uid'], 'checks'), {
                'checkUids': targets.get('checks', current_checks),
                'checkGroupUids': targets.get('checkGroups', current_groups),
            })
        window['checks'], window['checkGroups'] = window_targets(api, current['uid'])
        module.exit_json(changed=True, maintenance_window=window, diff=diff)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
