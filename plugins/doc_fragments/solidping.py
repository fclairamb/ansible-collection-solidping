# -*- coding: utf-8 -*-
# Copyright: (c) 2026, Florent Clairambault
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment(object):

    DOCUMENTATION = r'''
options:
  url:
    description:
      - Root URL of the SolidPing server, without C(/api/v1), for example C(https://solidping.acme.com).
      - Read from the E(SOLIDPING_URL) (or E(SOLIDPING_ENDPOINT)) environment variable when omitted.
      - O(url), O(token) and O(org) must be set, on the task, in C(module_defaults) or in the environment.
    type: str
    aliases: [endpoint]
  token:
    description:
      - Personal access token of the organization (created under B(Account > Tokens)).
      - Read from the E(SOLIDPING_TOKEN) environment variable when omitted. Keep it in Ansible Vault.
    type: str
  org:
    description:
      - Slug of the organization.
      - Read from the E(SOLIDPING_ORG) environment variable when omitted.
    type: str
  validate_certs:
    description:
      - Verify the TLS certificate of the server. Set to V(false) only for a self-signed test server.
    type: bool
    default: true
  ca_path:
    description:
      - PEM file of the certificate authority to trust for the server.
    type: path
  timeout:
    description:
      - Timeout of each API request, in seconds.
    type: int
    default: 30
notes:
  - Set the connection options once for a play with C(module_defaults) and the
    C(group/fclairamb.solidping.solidping) group, see the examples of the README.
'''

    ACTIONGROUP = r'''
attributes:
  action_group:
    description: Use C(group/fclairamb.solidping.solidping) in C(module_defaults) to set the connection options.
    support: full
    membership:
      - fclairamb.solidping.solidping
'''

    RESOURCE = r'''
attributes:
  check_mode:
    description: Can run in check mode and return the changes it would make.
    support: full
  diff_mode:
    description: Returns the managed fields before and after the change.
    support: full
'''

    INFO = r'''
attributes:
  check_mode:
    description: Read-only, runs the same way in check mode.
    support: full
  diff_mode:
    description: Read-only, returns no diff.
    support: N/A
'''
