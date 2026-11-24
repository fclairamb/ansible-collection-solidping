#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: notification_channel_info
short_description: Read SolidPing notification channels
version_added: 0.1.0
description:
  - Read one notification channel (by O(uid) or O(name)), or every channel of the organization.
  - A single channel comes with its C(settings), the list without them (the API does not return them in a list).
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.info
options:
  uid:
    description:
      - UID of the channel to read.
    type: str
  name:
    description:
      - Name of the channel to read.
    type: str
  type:
    description:
      - Only the channels of this type.
    type: str
'''

EXAMPLES = r'''
- name: Find the webhook channels
  fclairamb.solidping.notification_channel_info:
    type: webhook
  register: hooks
'''

RETURN = r'''
notification_channels:
  description:
    - The matching channels. A single channel read by O(uid) or O(name) gives a one-item list,
      a missing one an empty list.
  returned: always
  type: list
  elements: dict
  sample:
    - uid: 8ce76a1e-bc22-4b69-8e50-19a706a7ef00
      name: On-call
      type: webhook
      enabled: true
      isDefault: true
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    fail_api,
    find_one,
    solidping_argument_spec,
)


def main():
    argument_spec = dict(
        uid=dict(type='str'),
        name=dict(type='str'),
        type=dict(type='str'),
    )
    argument_spec.update(solidping_argument_spec())
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[('uid', 'name')],
                           supports_check_mode=True)
    params = module.params
    api = SolidPingAPI(module)

    try:
        uid = params['uid']
        if params['name']:
            match = find_one(api.list(api.org_path('channels')), 'name', params['name'], 'channels')
            uid = match['uid'] if match else None
            if uid is None:
                module.exit_json(changed=False, notification_channels=[])
        if uid:
            channel = api.get_or_none(api.org_path('channels', uid))
            channels = [channel] if channel is not None else []
        else:
            channels = api.list(api.org_path('channels'))
        if params['type']:
            channels = [c for c in channels if c.get('type') == params['type']]
        module.exit_json(changed=False, notification_channels=channels)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
