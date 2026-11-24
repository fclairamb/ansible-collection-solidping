#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: status_page_info
short_description: Read SolidPing status pages
version_added: 0.1.0
description:
  - Read one status page (by O(uid) or O(slug)), or every status page of the organization.
  - Their sections are read with M(fclairamb.solidping.status_page_section_info).
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.info
options:
  uid:
    description:
      - UID of the page to read.
    type: str
  slug:
    description:
      - Slug of the page to read.
    type: str
'''

EXAMPLES = r'''
- name: Read the default status page
  fclairamb.solidping.status_page_info:
  register: pages

- name: Its slug
  ansible.builtin.debug:
    msg: "{{ (pages.status_pages | selectattr('isDefault') | first).slug }}"
'''

RETURN = r'''
status_pages:
  description:
    - The matching pages. A single page read by O(uid) or O(slug) gives a one-item list,
      a missing one an empty list.
  returned: always
  type: list
  elements: dict
  sample:
    - uid: efd6e2aa-9715-4088-927c-994f16c9dcaf
      slug: acme
      name: Acme status
      visibility: public
      isDefault: true
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
        slug=dict(type='str'),
    )
    argument_spec.update(solidping_argument_spec())
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[('uid', 'slug')],
                           supports_check_mode=True)
    params = module.params
    api = SolidPingAPI(module)

    try:
        ref = params['uid'] or params['slug']
        if ref:
            page = api.get_or_none(api.org_path('status-pages', ref))
            pages = [page] if page is not None else []
        else:
            pages = api.list(api.org_path('status-pages'))
        module.exit_json(changed=False, status_pages=pages)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
