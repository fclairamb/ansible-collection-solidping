#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: status_page_section_info
short_description: Read the sections of a SolidPing status page
version_added: 0.1.0
description:
  - Read one section of a status page (by O(uid) or O(slug)), or all of them, with their components.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.info
options:
  status_page:
    description:
      - UID or slug of the status page.
    type: str
    required: true
  uid:
    description:
      - UID of the section to read.
    type: str
  slug:
    description:
      - Slug of the section to read.
    type: str
'''

EXAMPLES = r'''
- name: Read the sections of the public page
  fclairamb.solidping.status_page_section_info:
    status_page: acme
  register: sections
'''

RETURN = r'''
status_page_sections:
  description:
    - The sections, in page order, each with its C(resources) (every component, the ones a selector
      added have C(managedBySelector=true)).
  returned: always
  type: list
  elements: dict
  sample:
    - uid: 67cde8b2-c163-4df6-b913-402c32d1a1cc
      name: Website
      slug: website
      position: 1
      resources:
        - checkUid: e90bd341-1c7a-4f7d-90c2-c6e20b3eedfc
          publicName: Website
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
        status_page=dict(type='str', required=True),
        uid=dict(type='str'),
        slug=dict(type='str'),
    )
    argument_spec.update(solidping_argument_spec())
    module = AnsibleModule(argument_spec=argument_spec, mutually_exclusive=[('uid', 'slug')],
                           supports_check_mode=True)
    params = module.params
    api = SolidPingAPI(module)

    try:
        page = api.get_or_none(api.org_path('status-pages', params['status_page']))
        if page is None:
            module.fail_json(msg='no status page with the uid or slug `{0}`'.format(params['status_page']))
        page_uid = page['uid']
        ref = params['uid'] or params['slug']
        if ref:
            section = api.get_or_none(api.org_path('status-pages', page_uid, 'sections', ref))
            sections = [section] if section is not None else []
        else:
            sections = api.list(api.org_path('status-pages', page_uid, 'sections'))
        sections = sorted(sections, key=lambda s: s.get('position') or 0)
        for section in sections:
            resources = api.list(api.org_path('status-pages', page_uid, 'sections', section['uid'], 'resources'))
            section['resources'] = sorted(resources, key=lambda r: r.get('position') or 0)
        module.exit_json(changed=False, status_page_sections=sections)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
