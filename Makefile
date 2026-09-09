.PHONY: test lint check install

test:
	python3 -m pytest -q

lint:
	shellcheck scripts/*.sh
	python3 -m compileall -q somnus

check: lint test
	@echo "somnus: all checks passed"

install:
	install -m 755 scripts/somnus-*.sh $(HOME)/.hermes/scripts/
	cp -r skills/somnus-* $(HOME)/.hermes/skills/
	@echo "Now merge config.example.yaml into ~/.hermes/config.yaml"
