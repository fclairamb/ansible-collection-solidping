#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: maintenance_window_info
short_description: Read SolidPing maintenance windows
version_added: 0.1.0
description:
  - Read one maintenance window (by O(uid) or O(title)), or every window of the organization,
    with the checks and check groups they cover.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.info
options:
  uid:
    description:
      - UID of the window to read.
    type: str
  title:
    description:
      - Title of the window to read.
    type: str
'''

EXAMPLES = r'''
- name: Is a maintenance running?
  fclairamb.solidping.maintenance_window_info:
  register: windows

- name: Say so
  ansible.builtin.debug:
    msg: "{{ windows.maintenance_windows | selectattr('status', 'equalto', 'active') | map(attribute='title') | list }}"
'''

RETURN = r'''
maintenance_windows:
  description:
    - The matching windows, each with its C(checks) and C(checkGroups) UIDs.
  returned: always
  type: list
  elements: dict
  sample:
    - uid: 5e842232-ee3e-49c1-8ce0-4d476d6427e1
      title: Nightly database backup
      startAt: "2026-12-01T01:00:00Z"
      endAt: "2026-12-01T01:30:00Z"
      recurrence: daily
      status: upcoming
      checks: [e90bd341-1c7a-4f7d-90c2-c6e20b3eedfc]
      checkGroups: []
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    fail_api,
    solidping_argument_spec,
)


def main():
    argument_spec = dict(
        uid=dict(type='str'),
        title=dict(type='str'),
    )
    argument_spec.update(solidping_argument_spec())
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[('uid', 'title')],
                           supports_check_mode=True)
    params = module.params
    api = SolidPingAPI(module)

    try:
        if params['uid']:
            window = api.get_or_none(api.org_path('maintenance-windows', params['uid']))
            windows = [window] if window is not None else []
        else:
            windows = api.list(api.org_path('maintenance-windows'))
            if params['title']:
                windows = [w for w in windows if w.get('title') == params['title']]
        for window in windows:
            links = api.list(api.org_path('maintenance-windows', window['uid'], 'checks'))
            window['checks'] = [link['checkUid'] for link in links if link.get('checkUid')]
            window['checkGroups'] = [link['checkGroupUid'] for link in links if link.get('checkGroupUid')]
        module.exit_json(changed=False, maintenance_windows=windows)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
