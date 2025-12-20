.PHONY: test lint type-check run

# run unit tests
test:
	PYTHONPATH=. pytest

# linter (ruff)
lint:
	PYTHONPATH=. ruff check app tests

# static types (mypy)
type-check:
	PYTHONPATH=. mypy app

# run the app
run:
	PYTHONPATH=. python -m app.cmd.main

# build example Excel report
excel:
	PYTHONPATH=. python -m app.cmd.build_example_excel

.PHONY: tag deploy-dev

tag:
	@echo "Latest dev tags:"; git tag -l "[0-9]*.[0-9]*.[0-9]*-${SUFFIX}" --sort=-version:refname | head -5
	@latest=$$(git tag -l "[0-9]*.[0-9]*.[0-9]*-${SUFFIX}" --sort=-version:refname | head -1); \
	if [ -n "$$latest" ]; then \
		major=$$(echo $$latest | cut -d. -f1); \
		minor=$$(echo $$latest | cut -d. -f2); \
		patch=$$(echo $$latest | cut -d. -f3 | cut -d- -f1); \
		next_version=$$major.$$minor.$$((patch + 1))-${SUFFIX}; \
	else \
		next_version="0.1.0-${SUFFIX}"; \
	fi; \
	echo -n "Enter new version (leave blank for default: $$next_version): "; \
	read version; \
	if [ -z "$$version" ]; then version=$$next_version; fi; \
	if ! echo "$$version" | grep -q "\-${SUFFIX}$$"; then \
		echo "Error: Version must end with -${SUFFIX}"; exit 1; \
	fi; \
	git tag $$version && echo "Tagged: $$version"

deploy-dev: lint type-check test
	git fetch --tags
	@branch=$$(git branch --show-current); \
	if [ "$$branch" != "dev" ]; then \
		echo "Error: Can only deploy-dev from dev branch (current: $$branch)"; \
		exit 1; \
	fi
	$(MAKE) tag SUFFIX=dev
	git push origin dev
	git push --tags
