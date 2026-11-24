# AGENTS.md

Agent instructions for every coding agent. `CLAUDE.md` is a one-line `@AGENTS.md` stub: edit this file.

Ansible collection `fclairamb.solidping` for SolidPing (`../solidping`): a `server` role and modules
over the v1 REST API. It mirrors the Terraform provider (`../terraform-provider-solidping`), whose
resources are the reference for what each module manages. Origin: issue fclairamb/solidping#1018.

## Layout
- `plugins/module_utils/solidping.py`: the HTTP client (`SolidPingAPI`), the shared connection
  options and the comparison helpers. Every module goes through it.
- `plugins/doc_fragments/solidping.py`: the connection options and the attribute fragments.
- `plugins/modules/`: one module per resource plus its `*_info` module.
- `roles/server/`: install the binary (systemd service) or the container. Molecule scenario in
  `roles/server/molecule/default`.
- `tests/unit/`: pytest, run by `ansible-test units`. `tests/integration/targets/`: one target per
  module family, against a real server (`setup_solidping` logs in and sets `solidping_token`).

## Commands
| Command | Purpose |
|---|---|
| `make venv` | Create `.venv` with ansible-core, pytest and molecule (uv) |
| `make sanity` / `make units` | `ansible-test sanity` / `units` |
| `make test-server` then `make integration` | Integration targets against `ghcr.io/fclairamb/solidping` in test mode (`TARGETS=check` for one) |
| `make molecule` | The server role in a systemd container (needs Docker) |
| `make build` | Build the Galaxy archive |

## Rules
- A module is idempotent and supports check mode and diff mode. Only the options the task sets are
  compared with the server; in `config` / `settings`, only the keys the task writes
  (`subset_matches`). Compare through the helpers (`same_value`, `same_timestamp`, `same_set`),
  never `==`: the API reads empty strings back as `null` and answers timestamps in UTC.
- Secrets (`config_sensitive`, `settings_sensitive`, `password`) are never returned by the API,
  so they are not compared: `secrets_update` / `password_update` (`on_create` or `always`).
- Check the API behaviour against a running server before modelling it (what a PATCH clears,
  which keys the server omits when empty). Every module needs an integration target covering
  create, idempotent re-run, update, check mode and delete.
- Keep the module code Python 3.7 compatible (the oldest target of ansible-core 2.17).
- `ansible-test sanity` must pass with no ignore file. Fix the code, never add `tests/sanity/ignore-*.txt`.
- Never name a real company in code, tests, examples or docs: use `acme` (`acme.com`, `alice@acme.com`).
- Never commit a token or a key. Secrets: `GALAXY_API_KEY` (Galaxy publish), `CI_PAT` (optional).

## Pull requests and releases
- Squash-merge only, the PR title is the commit subject: it must be a conventional commit
  (`pr-title.yml` checks it). release-please derives the version, `CHANGELOG.md` and the
  `galaxy.yml` version from it: never edit them by hand outside the release PR.
- Merging the release PR tags `vX.Y.Z`; `release-please.yml` then builds the archive, attaches it
  to the release and publishes it to Galaxy.
- Labels: `automerge` (merges once CI is green), `autopilot` / `will-automerge` / `autorelease`
  (same meaning as in solidping).

## Specs
- Filename format: `YYYY-MM-DD-NN-title.md` (`NN` unique per day).
- Active: `specs/todos/`, done: `specs/done/YYYY/MM/`, backlog: `specs/backlog/`.
- Never delete the `specs/todos/` directory itself, even when it is empty.
- Issues about the collection are filed in this repository.
