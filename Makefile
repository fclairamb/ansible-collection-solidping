# ansible-test needs the collection under ansible_collections/<namespace>/<name>:
# every target syncs the checkout to such a tree (outside this git tree) and runs there.
STAGE := $(HOME)/.cache/ansible-collection-solidping/ansible_collections/fclairamb/solidping
VENV ?= .venv
PYTHON ?= 3.13
ANSIBLE_CORE ?= >=2.20,<2.21
SOLIDPING_TEST_URL ?= http://localhost:4000
export PATH := $(abspath $(VENV))/bin:$(PATH)
# A ~/.netrc that is not 0600 breaks every HTTP call of Ansible.
export NETRC := /dev/null

.PHONY: venv stage sanity units integration test-server molecule build clean

venv:
	uv venv -q -p $(PYTHON) $(VENV)
	uv pip install -q -p $(VENV)/bin/python "ansible-core$(ANSIBLE_CORE)" pytest molecule "molecule-plugins[docker]" docker

stage:
	mkdir -p $(STAGE)
	rsync -a --delete --exclude .venv --exclude .git --exclude .cache --exclude tests/output ./ $(STAGE)/

sanity: stage
	cd $(STAGE) && ansible-test sanity --venv --python $(PYTHON) --requirements

units: stage
	cd $(STAGE) && ansible-test units --venv --python $(PYTHON) --requirements

# Needs a server in test mode: `make test-server` starts one on port 4000.
integration: stage
	sed 's#http://localhost:4000#$(SOLIDPING_TEST_URL)#' tests/integration/integration_config.yml.template \
		> $(STAGE)/tests/integration/integration_config.yml
	cd $(STAGE) && ansible-test integration --local --python $(PYTHON) $(TARGETS)

test-server:
	docker run -d --rm --name solidping-ansible-test -e SP_RUNMODE=test -p 4000:4000 ghcr.io/fclairamb/solidping:latest

molecule: stage
	$(abspath $(VENV))/bin/ansible-galaxy collection install -r roles/server/molecule/default/requirements.yml
	cd $(STAGE)/roles/server && molecule test

build:
	$(abspath $(VENV))/bin/ansible-galaxy collection build --force

clean:
	rm -rf $(STAGE) fclairamb-solidping-*.tar.gz
