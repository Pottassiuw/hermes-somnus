PYTHON ?= python3
.PHONY: test legacy namespace count-lines

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_smoke.py' -v

legacy:
	@test -n "$(LEGACY_SOURCE)" || (echo 'Supply LEGACY_SOURCE=/absolute/path/to/extracted/bundle'; exit 3)
	$(PYTHON) tests/legacy_regressions.py --source "$(LEGACY_SOURCE)" -v

namespace:
	@test -n "$(SSH_TARGET)" || (echo 'Supply SSH_TARGET for the disposable acceptance lab'; exit 3)
	$(PYTHON) bin/acceptance.py namespace --ssh-target "$(SSH_TARGET)"

count-lines:
	@echo "=== Lines of code in bin/ and ops/ ==="
	@wc -l bin/* ops/*.json ops/profile/* ops/systemd/* ops/ssh/* 2>/dev/null || true

install-host:
	@echo "Execute with root privileges: sudo ops/install.sh"
	sudo ops/install.sh
