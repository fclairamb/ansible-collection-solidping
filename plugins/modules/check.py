#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: check
short_description: Manage a SolidPing monitoring check
version_added: 0.1.0
description:
  - Create, update or delete a check (HTTP, TCP, DNS, heartbeat, ...) of a SolidPing organization.
  - The check is identified by O(slug), or by O(uid) to rename its slug.
  - Only the options set in the task are compared with the server, so defaults the server adds never
    show as a change. Inside O(config), only the keys written in the task are compared.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.resource
options:
  state:
    description:
      - V(present) creates or updates the check, V(absent) deletes it.
    type: str
    choices: [present, absent]
    default: present
  slug:
    description:
      - URL-friendly identifier, unique in the organization. Identifies the check unless O(uid) is set.
      - Required to create a check.
    type: str
  uid:
    description:
      - UID of an existing check. Takes precedence over O(slug) to find the check.
    type: str
  name:
    description:
      - Display name. Derived from the target by the server when omitted at creation.
    type: str
  description:
    description:
      - What the check monitors. An empty string clears it.
    type: str
  type:
    description:
      - Check type, for example V(http), V(tcp), V(icmp), V(dns), V(ssl), V(heartbeat) or V(domain).
      - Required to create a check. It cannot change afterwards, delete the check and create it again.
    type: str
  config:
    description:
      - Type-specific configuration, for example the C(url) of an V(http) check.
      - Required to create a check.
    type: dict
  config_sensitive:
    description:
      - Secret configuration keys (passwords, tokens), merged over O(config) when the check is written.
      - The server never returns them, so they cannot be compared. See O(secrets_update).
    type: dict
  secrets_update:
    description:
      - V(on_create) sends O(config_sensitive) only when the check is created (and when O(config) changes
        anyway). V(always) sends it on every run, which then always reports a change.
    type: str
    choices: [on_create, always]
    default: on_create
  enabled:
    description:
      - Whether the check runs. A new check is enabled unless this is V(false).
    type: bool
  period:
    description:
      - Interval between two runs, as C(HH:MM:SS), for example V(00:01:00).
    type: str
  regions:
    description:
      - Region slugs the check runs from. Setting it pins the check to these regions.
    type: list
    elements: str
  placement:
    description:
      - V(pinned) (O(regions) never moves) or V(auto) (the scheduler picks O(region_count) healthy regions).
    type: str
    choices: [pinned, auto]
  region_count:
    description:
      - Automatic placement only, how many regions run the check.
    type: int
  labels:
    description:
      - Key-value labels, used to filter checks and to feed status page section selectors.
      - Replaces every label of the check. An empty dict removes them.
    type: dict
  check_group:
    description:
      - UID or slug of the check group of the check. An empty string removes it from its group.
    type: str
  escalation_policy_uid:
    description:
      - UID of the escalation policy of the check. An empty string goes back to the inherited policy.
    type: str
'''

EXAMPLES = r'''
- name: Monitor the website every minute
  fclairamb.solidping.check:
    url: https://solidping.acme.com
    org: acme
    token: "{{ solidping_token }}"
    slug: website
    name: Website
    type: http
    config:
      url: https://www.acme.com
    period: "00:01:00"
    labels:
      env: prod

- name: Check an API with a bearer token kept out of the logs
  fclairamb.solidping.check:
    slug: api
    type: http
    config:
      url: https://api.acme.com/health
    config_sensitive:
      headers:
        Authorization: "Bearer {{ api_token }}"
  no_log: true

- name: Remove an old check
  fclairamb.solidping.check:
    slug: legacy-website
    state: absent
'''

RETURN = r'''
check:
  description:
    - The check as the server returns it. In check mode, the predicted check.
    - Empty when O(state=absent).
  returned: always
  type: dict
  sample:
    uid: 0b6f7c1e-2d4a-4c8e-9a51-7f3f2c1d9e00
    slug: website
    name: Website
    type: http
    config:
      url: https://www.acme.com
    enabled: true
    period: "00:01:00"
    labels:
      env: prod
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    changed_fields,
    diff_of,
    fail_api,
    mask_secrets,
    same_set,
    solidping_argument_spec,
    subset_matches,
)


def build_desired(api, params):
    """API keys the task manages (None = not managed)."""
    group = params['check_group']
    if group:
        group = api.resolve_check_group_uid(group)
    return {
        'slug': params['slug'],
        'name': params['name'],
        'description': params['description'],
        'enabled': params['enabled'],
        'period': params['period'],
        'regions': params['regions'],
        'placement': params['placement'],
        'regionCount': params['region_count'],
        'labels': params['labels'],
        'checkGroupUid': group,
        'escalationPolicyUid': params['escalation_policy_uid'],
        'config': params['config'],
    }


COMPARATORS = {
    'config': subset_matches,
    'regions': same_set,
}


def main():
    argument_spec = dict(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        slug=dict(type='str'),
        uid=dict(type='str'),
        name=dict(type='str'),
        description=dict(type='str'),
        type=dict(type='str'),
        config=dict(type='dict'),
        config_sensitive=dict(type='dict', no_log=True),
        secrets_update=dict(type='str', default='on_create', choices=['on_create', 'always'], no_log=False),
        enabled=dict(type='bool'),
        period=dict(type='str'),
        regions=dict(type='list', elements='str'),
        placement=dict(type='str', choices=['pinned', 'auto']),
        region_count=dict(type='int'),
        labels=dict(type='dict'),
        check_group=dict(type='str'),
        escalation_policy_uid=dict(type='str'),
    )
    argument_spec.update(solidping_argument_spec())

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[('slug', 'uid')],
        supports_check_mode=True,
    )
    params = module.params
    api = SolidPingAPI(module)

    try:
        ref = params['uid'] or params['slug']
        current = api.get_or_none(api.org_path('checks', ref))
        if params['uid'] and current is None and params['state'] == 'present':
            module.fail_json(msg='no check with the uid `{0}`'.format(params['uid']))

        if params['state'] == 'absent':
            if current is None:
                module.exit_json(changed=False, check={})
            if not module.check_mode:
                api.delete(api.org_path('checks', current['uid']))
            module.exit_json(changed=True, check={}, diff=dict(before=current, after={}))

        desired = build_desired(api, params)
        secrets = params['config_sensitive'] or {}
        secret_keys = list(secrets)

        if current is None:
            missing = [opt for opt in ('type', 'config') if params[opt] is None]
            if missing:
                module.fail_json(msg='creating a check needs: {0}'.format(', '.join(missing)))
            body = dict((k, v) for k, v in desired.items() if v is not None)
            body['type'] = params['type']
            body['config'] = dict(params['config'], **secrets)
            diff = dict(before={}, after=dict(body, config=mask_secrets(body['config'], secret_keys)))
            if module.check_mode:
                module.exit_json(changed=True, check=body, diff=diff)
            created = api.request('POST', api.org_path('checks'), body)
            module.exit_json(changed=True, check=created, diff=diff)

        if params['type'] is not None and params['type'] != current.get('type'):
            module.fail_json(msg='the type of the check `{0}` is `{1}`: a check cannot change type, '
                                 'delete it and create it again'.format(current.get('slug'), current.get('type')))

        changes = changed_fields(current, desired, COMPARATORS)
        if secrets and (params['secrets_update'] == 'always' or 'config' in changes):
            changes['config'] = dict(params['config'] or {}, **secrets)
        if 'config' in changes and params['config'] is None:
            # Only secrets to send: start from the server config so nothing else moves.
            changes['config'] = dict(current.get('config') or {}, **secrets)

        if not changes:
            module.exit_json(changed=False, check=current)

        diff = diff_of(current, changes)
        if 'config' in changes:
            diff['after']['config'] = mask_secrets(changes['config'], secret_keys)
        if module.check_mode:
            module.exit_json(changed=True, check=dict(current, **changes), diff=diff)
        updated = api.request('PATCH', api.org_path('checks', current['uid']), changes)
        module.exit_json(changed=True, check=updated, diff=diff)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
