#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
module: notification_channel
short_description: Manage a SolidPing notification channel
version_added: 0.1.0
description:
  - Create, update or delete a notification channel (webhook, Slack, email, Telegram, ...).
  - The channel is identified by O(name), or by O(uid) to rename it.
  - Inside O(settings), only the keys written in the task are compared with the server.
author:
  - Florent Clairambault (@fclairamb)
extends_documentation_fragment:
  - fclairamb.solidping.solidping
  - fclairamb.solidping.solidping.actiongroup
  - fclairamb.solidping.solidping.resource
options:
  state:
    description:
      - V(present) creates or updates the channel, V(absent) deletes it.
    type: str
    choices: [present, absent]
    default: present
  name:
    description:
      - Display name. Identifies the channel unless O(uid) is set, so it must be unique.
      - Required to create a channel.
    type: str
  uid:
    description:
      - UID of an existing channel. Takes precedence over O(name) to find the channel.
    type: str
  type:
    description:
      - Channel type, for example V(webhook), V(slack), V(email), V(discord) or V(telegram).
      - Required to create a channel. It cannot change afterwards.
    type: str
  enabled:
    description:
      - Whether notifications are sent to the channel.
    type: bool
  is_default:
    description:
      - Whether new checks notify this channel.
    type: bool
  settings:
    description:
      - Type-specific settings, for example the C(url) of a V(webhook) channel.
    type: dict
  settings_sensitive:
    description:
      - Secret settings (tokens, passwords), merged over O(settings) when the channel is written.
      - The server never returns them, so they cannot be compared. See O(secrets_update).
    type: dict
  secrets_update:
    description:
      - V(on_create) sends O(settings_sensitive) only when the channel is created (and when O(settings)
        changes anyway). V(always) sends it on every run, which then always reports a change.
    type: str
    choices: [on_create, always]
    default: on_create
'''

EXAMPLES = r'''
- name: Send incidents to the on-call webhook
  fclairamb.solidping.notification_channel:
    name: On-call
    type: webhook
    settings:
      url: https://hooks.acme.com/solidping
    is_default: true

- name: Notify a Telegram chat, the bot token kept out of the logs
  fclairamb.solidping.notification_channel:
    name: Ops Telegram
    type: telegram
    settings:
      chatId: "-100123456"
    settings_sensitive:
      botToken: "{{ telegram_bot_token }}"
  no_log: true
'''

RETURN = r'''
notification_channel:
  description:
    - The channel as the server returns it. In check mode, the predicted channel.
    - Empty when O(state=absent).
  returned: always
  type: dict
  sample:
    uid: 8ce76a1e-bc22-4b69-8e50-19a706a7ef00
    name: On-call
    type: webhook
    enabled: true
    isDefault: true
    settings:
      url: https://hooks.acme.com/solidping
'''

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.fclairamb.solidping.plugins.module_utils.solidping import (
    SolidPingAPI,
    SolidPingError,
    changed_fields,
    diff_of,
    fail_api,
    find_one,
    mask_secrets,
    solidping_argument_spec,
    subset_matches,
)


def find_channel(api, params):
    if params['uid']:
        return api.get_or_none(api.org_path('channels', params['uid']))
    match = find_one(api.list(api.org_path('channels')), 'name', params['name'], 'channels')
    if match is None:
        return None
    # The list omits the settings: read the channel itself.
    return api.get_or_none(api.org_path('channels', match['uid']))


def main():
    argument_spec = dict(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        name=dict(type='str'),
        uid=dict(type='str'),
        type=dict(type='str'),
        enabled=dict(type='bool'),
        is_default=dict(type='bool'),
        settings=dict(type='dict'),
        settings_sensitive=dict(type='dict', no_log=True),
        secrets_update=dict(type='str', default='on_create', choices=['on_create', 'always'], no_log=False),
    )
    argument_spec.update(solidping_argument_spec())

    module = AnsibleModule(
        argument_spec=argument_spec,
        required_one_of=[('name', 'uid')],
        supports_check_mode=True,
    )
    params = module.params
    api = SolidPingAPI(module)

    try:
        current = find_channel(api, params)
        if params['uid'] and current is None and params['state'] == 'present':
            module.fail_json(msg='no notification channel with the uid `{0}`'.format(params['uid']))

        if params['state'] == 'absent':
            if current is None:
                module.exit_json(changed=False, notification_channel={})
            if not module.check_mode:
                api.delete(api.org_path('channels', current['uid']))
            module.exit_json(changed=True, notification_channel={},
                             diff=dict(before=dict(name=current.get('name'), type=current.get('type')), after={}))

        secrets = params['settings_sensitive'] or {}
        secret_keys = list(secrets)
        desired = {
            'name': params['name'],
            'enabled': params['enabled'],
            'isDefault': params['is_default'],
            'settings': params['settings'],
        }

        if current is None:
            missing = [opt for opt in ('name', 'type') if params[opt] is None]
            if missing:
                module.fail_json(msg='creating a notification channel needs: {0}'.format(', '.join(missing)))
            body = dict((k, v) for k, v in desired.items() if v is not None)
            body['type'] = params['type']
            body['settings'] = dict(params['settings'] or {}, **secrets)
            diff = dict(before={}, after=dict(body, settings=mask_secrets(body['settings'], secret_keys)))
            if module.check_mode:
                module.exit_json(changed=True, notification_channel=body, diff=diff)
            created = api.request('POST', api.org_path('channels'), body)
            module.exit_json(changed=True, notification_channel=created, diff=diff)

        if params['type'] is not None and params['type'] != current.get('type'):
            module.fail_json(msg='the channel `{0}` is of type `{1}`: a channel cannot change type, '
                                 'delete it and create it again'.format(current.get('name'), current.get('type')))

        changes = changed_fields(current, desired, {'settings': subset_matches})
        if secrets and (params['secrets_update'] == 'always' or 'settings' in changes):
            changes['settings'] = dict(params['settings'] or current.get('settings') or {}, **secrets)

        if not changes:
            module.exit_json(changed=False, notification_channel=current)

        diff = diff_of(current, changes)
        if 'settings' in changes:
            diff['after']['settings'] = mask_secrets(changes['settings'], secret_keys)
        if module.check_mode:
            module.exit_json(changed=True, notification_channel=dict(current, **changes), diff=diff)
        updated = api.request('PATCH', api.org_path('channels', current['uid']), changes)
        module.exit_json(changed=True, notification_channel=updated, diff=diff)
    except SolidPingError as e:
        fail_api(module, e)


if __name__ == '__main__':
    main()
