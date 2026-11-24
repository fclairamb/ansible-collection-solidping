# Ansible collection `fclairamb.solidping`

Install a [SolidPing](https://www.solidping.io) server and manage what it monitors from Ansible:
checks, notification channels, status pages and maintenance windows.

- **`fclairamb.solidping.server`**: a role that installs the release binary (amd64, arm64, riscv64)
  as a systemd service, or runs the container image, with its `SP_*` configuration.
- **Modules**, idempotent, with check mode and `--diff`:

| Module | Manages |
|---|---|
| `check` / `check_info` | Monitoring checks (HTTP, TCP, DNS, ICMP, SSL, heartbeat, ...) |
| `notification_channel` / `notification_channel_info` | Webhook, Slack, email, Telegram, ... channels |
| `status_page` / `status_page_info` | Status pages |
| `status_page_section` / `status_page_section_info` | Sections of a page and the components they show |
| `maintenance_window` / `maintenance_window_info` | Planned maintenance |

The modules mirror the resources of the [Terraform provider](https://github.com/fclairamb/terraform-provider-solidping).

## Install

```bash
ansible-galaxy collection install fclairamb.solidping
```

Or in `requirements.yml`:

```yaml
collections:
  - name: fclairamb.solidping
  # Only for `solidping_install_method: container`:
  - name: community.docker
```

Needs ansible-core 2.17 or later.

## Install a server

```yaml
- hosts: monitoring
  become: true
  roles:
    - role: fclairamb.solidping.server
      vars:
        solidping_version: "0.54.1"       # or `latest`
        solidping_env:
          SP_ADMIN_EMAIL: admin@acme.com
          SP_DB_TYPE: postgres
          SP_DB_URL: "{{ vault_solidping_db_url }}"
```

The role downloads `solidping-linux-<arch>.gz` from the GitHub release, checks it against
`solidping-checksums.txt`, installs it root-owned in `/usr/local/bin`, runs
`solidping service install` (unit `solidping`, data in `/var/lib/solidping`), writes `config.env`
(`0600`, owned by the `solidping` user) and keeps the service enabled and running. A change of
version, of `solidping_env` or of `solidping_config` restarts it. It needs a host booted with systemd.

To run the container instead (needs `community.docker` and Docker on the host):

```yaml
    - role: fclairamb.solidping.server
      vars:
        solidping_install_method: container
        solidping_container_ports: ["4000:4000"]
        solidping_env:
          SP_ADMIN_EMAIL: admin@acme.com
```

Every variable is listed in [`roles/server/meta/argument_specs.yml`](roles/server/meta/argument_specs.yml)
(`ansible-doc -t role fclairamb.solidping.server`).

## Manage the monitoring

Create an organization-scoped personal access token (**Account → Tokens**) and keep it in Ansible
Vault. Set the connection once for the play with the `fclairamb.solidping.solidping` group (or
through the `SOLIDPING_URL`, `SOLIDPING_TOKEN` and `SOLIDPING_ORG` environment variables):

```yaml
- hosts: localhost
  gather_facts: false
  module_defaults:
    group/fclairamb.solidping.solidping:
      url: https://solidping.acme.com
      org: acme
      token: "{{ vault_solidping_token }}"
  tasks:
    - name: Webhook for the on-call
      fclairamb.solidping.notification_channel:
        name: On-call
        type: webhook
        settings:
          url: https://hooks.acme.com/solidping
        is_default: true

    - name: Website check
      fclairamb.solidping.check:
        slug: website
        name: Website
        type: http
        config:
          url: https://www.acme.com
        period: "00:01:00"
        labels:
          env: prod

    - name: Public status page
      fclairamb.solidping.status_page:
        slug: acme
        name: Acme status

    - name: Its production section, filled from the labels
      fclairamb.solidping.status_page_section:
        status_page: acme
        name: Production
        selector:
          labels:
            env: prod

    - name: Nightly maintenance
      fclairamb.solidping.maintenance_window:
        title: Nightly backup
        start_at: "2026-12-01T02:00:00+01:00"
        end_at: "2026-12-01T02:30:00+01:00"
        recurrence: daily
        checks: [website]
```

How the modules compare:

- Resources are found by their natural key: `slug` for checks and status pages, `name` for
  channels, `slug` or `name` for sections (inside their page), `title` for maintenance windows.
  Pass `uid` to rename one.
- Only the options a task sets are compared and written. Inside `config` (checks) and `settings`
  (channels), only the keys the task writes are compared, so defaults the server adds never show
  as a change.
- Secrets go in `config_sensitive` / `settings_sensitive` / `password`. The server never returns
  them, so they are sent on creation only; `secrets_update: always` (`password_update: always`)
  sends them on every run, which then always reports a change. Add `no_log: true` to those tasks.
- Timestamps are compared as instants: `2026-12-01T02:00:00+01:00` matches the
  `2026-12-01T01:00:00Z` the server answers.
- `labels`, `resources`, `checks` and `check_groups` replace the whole list or map; an empty value
  removes everything, an omitted one leaves it alone.

Each module documents its options: `ansible-doc fclairamb.solidping.check`.

Other ways to drive SolidPing from Ansible (`sp apply`, Event-Driven Ansible on webhooks) are in the
[SolidPing documentation](https://docs.solidping.io/docs/ansible).

## Developing

```bash
make venv                 # .venv with ansible-core, pytest, molecule
make sanity units         # ansible-test sanity and unit tests
make test-server          # SolidPing in test mode on :4000 (Docker)
make integration          # every module against it (TARGETS=check for one)
make molecule             # the server role in a systemd container
```

CI runs sanity on every supported ansible-core, the units, the integration targets against
`ghcr.io/fclairamb/solidping:latest`, and molecule on Debian 12, Ubuntu 24.04 and Rocky Linux 9.

## Releasing

Releases are cut by release-please from conventional-commit PR titles. Merging the
`chore(release): vX.Y.Z` PR tags the version, attaches the built archive to the GitHub release and
publishes it to Ansible Galaxy. Repository secrets:

| Secret | Use |
|---|---|
| `GALAXY_API_KEY` | API key of the `fclairamb` namespace on galaxy.ansible.com |
| `CI_PAT` | Optional. Token release-please acts with, so the release PR gets a CI run |

## License

GPL-3.0-or-later, see [LICENSE](LICENSE).
