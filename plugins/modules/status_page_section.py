#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: status_page_section
short_description: Manage a section of a SolidPing status page
version_added: 0.1.0
description:
  - Create, update or delete a section of a status page, and the components (checks or check groups) it shows.
  - The section is identified by O(slug), O(name) or O(uid) inside its O(status_page).
  - Components come from O(selector) (filled by the server from labels or a check group), from
    O(resources) (a curated list), or from both.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.resource
options:
  state:
    description:
      - V(present) creates or updates the section, V(absent) deletes it.
    type: str
    choices: [present, absent]
    default: present
  status_page:
    description:
      - UID or slug of the status page.
    type: str
    required: true
  slug:
    description:
      - Identifier of the section inside the page. Derived from O(name) by the server when omitted.
    type: str
  uid:
    description:
      - UID of an existing section. Takes precedence over O(slug) and O(name) to find the section.
    type: str
  name:
    description:
      - Title of the section. Required to create a section. Finds the section when neither O(uid) nor O(slug) is set.
    type: str
  position:
    description:
      - Position of the section in the page, from 1.
    type: int
  selector:
    description:
      - Dynamic membership. The server shows every check the rule matches.
      - An empty dict removes the selector.
    type: dict
    suboptions:
      all:
        description: Every check of the organization.
        type: bool
      labels:
        description: Checks that carry all these labels.
        type: dict
      check_group:
        description: UID or slug of a check group whose checks are shown.
        type: str
  resources:
    description:
      - Curated components of the section, in display order. Replaces the curated list of the section,
        an empty list removes them all. Components added by O(selector) are not affected.
      - When omitted, the curated components are left as they are.
    type: list
    elements: dict
    suboptions:
      check:
        description: UID or slug of a check. Exactly one of O(resources[].check) and O(resources[].check_group).
        type: str
      check_group:
        description: UID or slug of a check group.
        type: str
      public_name:
        description: Name shown on the page instead of the check name.
        type: str
      explanation:
        description: Help text shown next to the component.
        type: str
'''

EXAMPLES = r'''
- name: Section listing the production checks
  fclairamb.solidping.status_page_section:
    status_page: acme
    name: Production
    selector:
      labels:
        env: prod

- name: Hand-picked components
  fclairamb.solidping.status_page_section:
    status_page: acme
    name: Website
    position: 1
    resources:
      - check: website
        public_name: Website
      - check: api
        public_name: Public API
        explanation: REST API used by the mobile apps
'''

RETURN = r'''
status_page_section:
  description:
    - The section as the server returns it, with its curated C(resources). In check mode, the predicted section.
    - Empty when O(state=absent).
  returned: always
  type: dict
  sample:
    uid: 67cde8b2-c163-4df6-b913-402c32d1a1cc
    name: Website
    slug: website
    position: 1
    selector:
    resources:
      - uid: 56efa334-664b-494a-9c4e-09184d00d9e8
        checkUid: e90bd341-1c7a-4f7d-90c2-c6e20b3eedfc
        publicName: Website
        position: 1
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    changed_fields,
    diff_of,
    fail_api,
    find_one,
    same_value,
    solidping_argument_spec,
)


def find_section(api, page_uid, params):
    if params['uid'] or params['slug']:
        return api.get_or_none(api.org_path('status-pages', page_uid, 'sections', params['uid'] or params['slug']))
    return find_one(api.list(api.org_path('status-pages', page_uid, 'sections')), 'name', params['name'], 'sections')


def desired_selector(api, selector):
    """API form of the selector option: None (unmanaged), {} (remove) or a rule."""
    if selector is None:
        return None
    out = {}
    if selector.get('all'):
        out['all'] = True
    if selector.get('labels'):
        out['labels'] = selector['labels']
    if selector.get('check_group'):
        out['checkGroupUid'] = api.resolve_check_group_uid(selector['check_group'])
    return out


def curated(api, page_uid, section_uid):
    resources = api.list(api.org_path('status-pages', page_uid, 'sections', section_uid, 'resources'))
    resources = [r for r in resources if not r.get('managedBySelector')]
    return sorted(resources, key=lambda r: r.get('position') or 0)


def resource_key(res):
    if res.get('checkUid'):
        return 'check:' + res['checkUid']
    return 'group:' + (res.get('checkGroupUid') or '')


def desired_resources(api, resources):
    out = []
    for res in resources:
        item = {}
        if res.get('check'):
            item['checkUid'] = api.resolve_check_uid(res['check'])
        else:
            item['checkGroupUid'] = api.resolve_check_group_uid(res['check_group'])
        item['publicName'] = res.get('public_name') or ''
        item['explanation'] = res.get('explanation') or ''
        out.append(item)
    return out


def apply_resources(api, page_uid, section_uid, desired):
    current = curated(api, page_uid, section_uid)
    by_key = dict((resource_key(r), r) for r in current)
    order = []
    for want in desired:
        existing = by_key.pop(resource_key(want), None)
        path = api.org_path('status-pages', page_uid, 'sections', section_uid, 'resources')
        if existing is None:
            body = dict((k, v) for k, v in want.items() if v)
            created = api.request('POST', path, body)
            order.append(created['uid'])
            continue
        order.append(existing['uid'])
        if not (same_value(want['publicName'], existing.get('publicName')) and
                same_value(want['explanation'], existing.get('explanation'))):
            api.request('PATCH', api.org_path('status-pages', page_uid, 'sections', section_uid, 'resources',
                                              existing['uid']),
                        {'publicName': want['publicName'], 'explanation': want['explanation']})
    for stale in by_key.values():
        api.delete(api.org_path('status-pages', page_uid, 'sections', section_uid, 'resources', stale['uid']))
    final = [r['uid'] for r in curated(api, page_uid, section_uid)]
    if len(order) > 1 and final != order:
        api.request('POST', api.org_path('status-pages', page_uid, 'sections', section_uid, 'resources', 'reorder'),
                    {'uids': order})


def resources_differ(current, desired):
    if len(current) != len(desired):
        return True
    for have, want in zip(current, desired):
        if resource_key(have) != resource_key(want):
            return True
        if not (same_value(want['publicName'], have.get('publicName')) and
                same_value(want['explanation'], have.get('explanation'))):
            return True
    return False


def summarize(resources):
    keep = ('checkUid', 'checkGroupUid', 'publicName', 'explanation')
    return [dict((k, r.get(k)) for k in keep if r.get(k)) for r in resources]


def main():
    resource_spec = dict(
        check=dict(type='str'),
        check_group=dict(type='str'),
        public_name=dict(type='str'),
        explanation=dict(type='str'),
    )
    argument_spec = dict(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        status_page=dict(type='str', required=True),
        slug=dict(type='str'),
        uid=dict(type='str'),
        name=dict(type='str'),
        position=dict(type='int'),
        selector=dict(type='dict', options=dict(
            all=dict(type='bool'),
            labels=dict(type='dict'),
            check_group=dict(type='str'),
        )),
        resources=dict(type='list', elements='dict', options=resource_spec,
                       mutually_exclusive=[('check', 'check_group')],
                       required_one_of=[('check', 'check_group')]),
    )
    argument_spec.update(solidping_argument_spec())

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[('slug', 'uid', 'name')],
        supports_check_mode=True,
    )
    params = module.params
    api = SolidPingAPI(module)

    try:
        page_uid = api.resolve_status_page(params['status_page'])['uid']
        current = find_section(api, page_uid, params)
        if params['uid'] and current is None and params['state'] == 'present':
            module.fail_json(msg='no section with the uid `{0}` in the status page'.format(params['uid']))

        if params['state'] == 'absent':
            if current is None:
                module.exit_json(changed=False, status_page_section={})
            if not module.check_mode:
                api.delete(api.org_path('status-pages', page_uid, 'sections', current['uid']))
            module.exit_json(changed=True, status_page_section={},
                             diff=dict(before=dict(name=current.get('name'), slug=current.get('slug')), after={}))

        selector = desired_selector(api, params['selector'])
        resources = None if params['resources'] is None else desired_resources(api, params['resources'])
        desired = {
            'name': params['name'],
            'slug': params['slug'],
            'position': params['position'],
            'selector': selector,
        }

        if current is None:
            if params['name'] is None:
                module.fail_json(msg='creating a status page section needs: name')
            body = dict((k, v) for k, v in desired.items() if v is not None)
            if body.get('selector') == {}:
                del body['selector']
            after = dict(body)
            if resources is not None:
                after['resources'] = summarize(resources)
            diff = dict(before={}, after=after)
            if module.check_mode:
                module.exit_json(changed=True, status_page_section=after, diff=diff)
            section = api.request('POST', api.org_path('status-pages', page_uid, 'sections'), body)
            if resources:
                apply_resources(api, page_uid, section['uid'], resources)
            section['resources'] = curated(api, page_uid, section['uid'])
            module.exit_json(changed=True, status_page_section=section, diff=diff)

        changes = changed_fields(current, desired, {'selector': same_value})
        if 'selector' in changes and changes['selector'] == {}:
            changes['selector'] = None

        current_resources = curated(api, page_uid, current['uid'])
        resources_change = resources is not None and resources_differ(current_resources, resources)

        current = dict(current, resources=current_resources)
        if not changes and not resources_change:
            module.exit_json(changed=False, status_page_section=current)

        diff = diff_of(current, changes)
        if resources_change:
            diff['before']['resources'] = summarize(current_resources)
            diff['after']['resources'] = summarize(resources)
        if module.check_mode:
            predicted = dict(current, **changes)
            if resources_change:
                predicted['resources'] = resources
            module.exit_json(changed=True, status_page_section=predicted, diff=diff)

        section = current
        if changes:
            section = api.request('PATCH', api.org_path('status-pages', page_uid, 'sections', current['uid']), changes)
        if resources_change:
            apply_resources(api, page_uid, current['uid'], resources)
        section['resources'] = curated(api, page_uid, current['uid'])
        module.exit_json(changed=True, status_page_section=section, diff=diff)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
