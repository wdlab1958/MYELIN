# MYELIN monorepo — make targets used by the session protocol (CLAUDE.md)
#   make test            run all tests
#   make lint            ruff check + format check
#   make typecheck       mypy (strict)
#   make gate P=<n>      run Phase gate checks (scripts/gate.py)
#   make phases          regenerate docs/phases/P*.md from the spec
#   make schemas         export JSON Schemas to docs/spec/schema/
#   make fixtures        regenerate tests/fixtures/vaults/{basic,seeded-violations}
#   make golden          regenerate tests/fixtures/golden/init-basic (review the diff!)
#   make packs           validate packs/
#   make sync            uv sync (all workspace members + dev group)

UV ?= uv
P  ?= 0

.PHONY: sync test lint fmt typecheck gate phases schemas fixtures golden packs check clean

sync:
	$(UV) sync --all-packages --group dev

test: sync
	$(UV) run pytest -q

lint: sync
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt: sync
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

typecheck: sync
	$(UV) run mypy

check: lint typecheck test

gate: sync
	$(UV) run python scripts/gate.py $(P)

phases:
	python3 scripts/split_phases.py

schemas: sync
	$(UV) run python scripts/export_schemas.py

fixtures:
	python3 scripts/gen_fixture_vault.py
	python3 scripts/gen_seeded_vault.py

golden: sync
	$(UV) run python scripts/gen_golden.py

packs: sync
	$(UV) run python scripts/validate_packs.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
