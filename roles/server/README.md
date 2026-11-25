# Role `fclairamb.solidping.server`

Installs a [SolidPing](https://www.solidping.io) server.

- `solidping_install_method: binary` (default): downloads the release binary for the host's
  architecture (amd64, arm64, riscv64), checks it against `solidping-checksums.txt`, installs it in
  `/usr/local/bin`, runs `solidping service install`, writes `config.env` (`0600`, owned by the
  `solidping` user) from `solidping_env` and keeps the systemd service enabled and running.
  Needs a host booted with systemd.
- `solidping_install_method: container`: runs `ghcr.io/fclairamb/solidping` with the same
  environment. Needs the `community.docker` collection and Docker on the host.

A change of version, of `solidping_env` or of `solidping_config` restarts the service.

## Example

```yaml
- hosts: monitoring
  become: true
  roles:
    - role: fclairamb.solidping.server
      vars:
        solidping_version: "0.54.1"   # or `latest`
        solidping_env:
          SP_ADMIN_EMAIL: admin@acme.com
          SP_DB_TYPE: postgres
          SP_DB_URL: "{{ vault_solidping_db_url }}"
```

## Variables

| Variable | Default | Meaning |
|---|---|---|
| `solidping_install_method` | `binary` | `binary` or `container` |
| `solidping_version` | `latest` | Version without the `v`, or `latest` |
| `solidping_env` | `{}` | `SP_*` environment variables |
| `solidping_config` | `{}` | Content of `config.yml` (binary), not managed when empty |
| `solidping_service_name` | `solidping` | systemd unit name |
| `solidping_bin_path` | `/usr/local/bin/solidping` | Where the binary goes |
| `solidping_data_dir` | `/var/lib/solidping` | Data folder of the service |
| `solidping_service_enabled` / `solidping_service_state` | `true` / `started` | Service at boot / now |
| `solidping_container_*` | see `defaults/main.yml` | Name, image, volume, ports, restart policy, networks, labels |

Every variable is described in `meta/argument_specs.yml` (`ansible-doc -t role fclairamb.solidping.server`).
