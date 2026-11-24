#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: status_page
short_description: Manage a SolidPing status page
version_added: 0.1.0
description:
  - Create, update or delete a status page. Its sections are managed with M(fclairamb.solidping.status_page_section).
  - The page is identified by O(slug), or by O(uid) to rename its slug.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.resource
options:
  state:
    description:
      - V(present) creates or updates the page, V(absent) deletes it.
    type: str
    choices: [present, absent]
    default: present
  slug:
    description:
      - URL-friendly identifier of the page. Identifies the page unless O(uid) is set.
      - Required to create a page.
    type: str
  uid:
    description:
      - UID of an existing page. Takes precedence over O(slug) to find the page.
    type: str
  name:
    description:
      - Title of the page. Required to create a page.
    type: str
  description:
    description:
      - Text shown under the title. An empty string clears it.
    type: str
  visibility:
    description:
      - V(public) (world-readable), V(private) (hidden) or V(password) (unlocked with O(password)).
    type: str
    choices: [public, private, password]
  password:
    description:
      - Unlock password, required when O(visibility=password) (6 characters minimum).
      - The server never returns it. See O(password_update).
    type: str
  password_update:
    description:
      - V(on_create) sends O(password) only when the page is created or has no password yet.
        V(always) sends it on every run, which then always reports a change.
    type: str
    choices: [on_create, always]
    default: on_create
  enabled:
    description:
      - Whether the page is served.
    type: bool
  is_default:
    description:
      - Whether this is the default status page of the organization.
    type: bool
  show_availability:
    description:
      - Show the availability bars.
    type: bool
  show_response_time:
    description:
      - Show the response-time charts.
    type: bool
  history_period:
    description:
      - History window.
    type: str
    choices: ["24h", "7d", "30d", "90d"]
  language:
    description:
      - Language of the page, for example V(en) or V(fr).
    type: str
  auto_publish:
    description:
      - Publish incidents on the page automatically.
    type: bool
  auto_publish_delay_seconds:
    description:
      - Delay before an incident becomes public, in seconds (0 to 86400).
    type: int
  publish_degraded:
    description:
      - Also publish degraded incidents automatically.
    type: bool
  auto_resolve:
    description:
      - What an auto-published incident does when it resolves.
    type: str
    choices: [always, if_untouched, never]
  hide_branding:
    description:
      - Hide the SolidPing branding (needs a plan that allows it).
    type: bool
  custom_css:
    description:
      - Custom stylesheet injected in the public page (64 KB maximum, no C(@import)). An empty string clears it.
    type: str
  custom_domain:
    description:
      - Hostname the page is served on, for example V(status.acme.com). An empty string clears it.
    type: str
'''

EXAMPLES = r'''
- name: Public status page
  fclairamb.solidping.status_page:
    slug: acme
    name: Acme status
    description: Live status of the Acme services
    history_period: 30d
    custom_domain: status.acme.com

- name: Internal page behind a password
  fclairamb.solidping.status_page:
    slug: internal
    name: Internal services
    visibility: password
    password: "{{ status_page_password }}"
  no_log: true
'''

RETURN = r'''
status_page:
  description:
    - The status page as the server returns it. In check mode, the predicted page.
    - Empty when O(state=absent).
  returned: always
  type: dict
  sample:
    uid: efd6e2aa-9715-4088-927c-994f16c9dcaf
    slug: acme
    name: Acme status
    visibility: public
    enabled: true
    historyPeriod: 30d
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    changed_fields,
    diff_of,
    fail_api,
    solidping_argument_spec,
)

FIELDS = (
    ('slug', 'slug'),
    ('name', 'name'),
    ('description', 'description'),
    ('visibility', 'visibility'),
    ('enabled', 'enabled'),
    ('is_default', 'isDefault'),
    ('show_availability', 'showAvailability'),
    ('show_response_time', 'showResponseTime'),
    ('history_period', 'historyPeriod'),
    ('language', 'language'),
    ('auto_publish', 'autoPublish'),
    ('auto_publish_delay_seconds', 'autoPublishDelaySeconds'),
    ('publish_degraded', 'publishDegraded'),
    ('auto_resolve', 'autoResolve'),
    ('hide_branding', 'hideBranding'),
    ('custom_css', 'customCss'),
    ('custom_domain', 'customDomain'),
)


def main():
    argument_spec = dict(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        slug=dict(type='str'),
        uid=dict(type='str'),
        name=dict(type='str'),
        description=dict(type='str'),
        visibility=dict(type='str', choices=['public', 'private', 'password']),
        password=dict(type='str', no_log=True),
        password_update=dict(type='str', default='on_create', choices=['on_create', 'always'], no_log=False),
        enabled=dict(type='bool'),
        is_default=dict(type='bool'),
        show_availability=dict(type='bool'),
        show_response_time=dict(type='bool'),
        history_period=dict(type='str', choices=['24h', '7d', '30d', '90d']),
        language=dict(type='str'),
        auto_publish=dict(type='bool'),
        auto_publish_delay_seconds=dict(type='int'),
        publish_degraded=dict(type='bool'),
        auto_resolve=dict(type='str', choices=['always', 'if_untouched', 'never']),
        hide_branding=dict(type='bool'),
        custom_css=dict(type='str'),
        custom_domain=dict(type='str'),
    )
    argument_spec.update(solidping_argument_spec())

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[('slug', 'uid')],
        required_if=[('visibility', 'password', ('password',))],
        supports_check_mode=True,
    )
    params = module.params
    api = SolidPingAPI(module)

    try:
        current = api.get_or_none(api.org_path('status-pages', params['uid'] or params['slug']))
        if params['uid'] and current is None and params['state'] == 'present':
            module.fail_json(msg='no status page with the uid `{0}`'.format(params['uid']))

        if params['state'] == 'absent':
            if current is None:
                module.exit_json(changed=False, status_page={})
            if not module.check_mode:
                api.delete(api.org_path('status-pages', current['uid']))
            module.exit_json(changed=True, status_page={},
                             diff=dict(before=dict(slug=current.get('slug'), name=current.get('name')), after={}))

        desired = dict((api_key, params[opt]) for opt, api_key in FIELDS)

        if current is None:
            if params['name'] is None:
                module.fail_json(msg='creating a status page needs: name')
            body = dict((k, v) for k, v in desired.items() if v is not None)
            # `enabled` can only be written by an update.
            enabled = body.pop('enabled', None)
            if params['password'] is not None:
                body['password'] = params['password']
            diff = dict(before={}, after=dict((k, v) for k, v in body.items() if k != 'password'))
            if module.check_mode:
                module.exit_json(changed=True, status_page=diff['after'], diff=diff)
            created = api.request('POST', api.org_path('status-pages'), body)
            if enabled is False and created.get('enabled') is not False:
                created = api.request('PATCH', api.org_path('status-pages', created['uid']), {'enabled': False})
            module.exit_json(changed=True, status_page=created, diff=diff)

        changes = changed_fields(current, desired)
        if 'customDomain' in changes and changes['customDomain'] == '':
            changes['customDomain'] = None

        send_password = params['password'] is not None and (
            params['password_update'] == 'always' or not current.get('hasPassword'))

        if not changes and not send_password:
            module.exit_json(changed=False, status_page=current)

        diff = diff_of(current, changes)
        body = dict(changes)
        if send_password:
            body['password'] = params['password']
            diff['before']['password'] = '********' if current.get('hasPassword') else None
            diff['after']['password'] = '********'
        if module.check_mode:
            module.exit_json(changed=True, status_page=dict(current, **changes), diff=diff)
        updated = api.request('PATCH', api.org_path('status-pages', current['uid']), body)
        module.exit_json(changed=True, status_page=updated, diff=diff)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
