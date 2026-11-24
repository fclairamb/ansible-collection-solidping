#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: check_info
short_description: Read SolidPing checks
version_added: 0.1.0
description:
  - Read one check (by O(uid) or O(slug)), or every check of the organization.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.info
options:
  uid:
    description:
      - UID of the check to read.
    type: str
  slug:
    description:
      - Slug of the check to read.
    type: str
  labels:
    description:
      - Only the checks that carry all these labels.
    type: dict
  type:
    description:
      - Only the checks of this type.
    type: str
'''

EXAMPLES = r'''
- name: Read every production check
  fclairamb.solidping.check_info:
    labels:
      env: prod
  register: prod_checks

- name: Print their status
  ansible.builtin.debug:
    msg: "{{ item.slug }}: {{ item.status }}"
  loop: "{{ prod_checks.checks }}"
'''

RETURN = r'''
checks:
  description:
    - The matching checks. A single check read by O(uid) or O(slug) gives a one-item list,
      a missing one an empty list.
  returned: always
  type: list
  elements: dict
  sample:
    - uid: 0b6f7c1e-2d4a-4c8e-9a51-7f3f2c1d9e00
      slug: website
      name: Website
      type: http
      status: up
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    fail_api,
    solidping_argument_spec,
)


def matches(check, params):
    if params['type'] and check.get('type') != params['type']:
        return False
    labels = check.get('labels') or {}
    for key, value in (params['labels'] or {}).items():
        if labels.get(key) != value:
            return False
    return True


def main():
    argument_spec = dict(
        uid=dict(type='str'),
        slug=dict(type='str'),
        labels=dict(type='dict'),
        type=dict(type='str'),
    )
    argument_spec.update(solidping_argument_spec())
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[('uid', 'slug')],
                           supports_check_mode=True)
    params = module.params
    api = SolidPingAPI(module)

    try:
        ref = params['uid'] or params['slug']
        if ref:
            check = api.get_or_none(api.org_path('checks', ref))
            checks = [check] if check is not None else []
        else:
            checks = api.list(api.org_path('checks'))
        module.exit_json(changed=False, checks=[c for c in checks if matches(c, params)])
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
