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
#   make perf            5,000-note index/search benchmark (MYELIN_PERF=1)
#   make mcp             run the MCP server on VAULT=<path> (stdio)
#   make emboss          regenerate design/dist + Obsidian theme from design/tokens.json
#   make a11y            text contrast / neon-as-text check
#   make emboss-lint     raw color literal lint (CSS/HTML/TSX)
#   make gallery         headless Chrome screenshot of the gallery → docs/reports/P5/gallery.png
#   make hub             run the Hub (API + built web) on VAULT=<path>, PORT=8787
#   make web             install + build the Hub web app
#   make e2e             Playwright e2e (Chrome channel) with screenshots → docs/reports/P6/
#   make sync            uv sync (all workspace members + dev group)

UV ?= uv
P  ?= 0

# Interpreter pin: this workstation's pyenv 3.12.11 is a mixed install (3.12.3 binary + 3.12.11 stdlib)
# and segfaults in asyncio. Prefer the consistent system CPython when present (PHASE_STATE P4 decision).
SYSTEM_PY := $(shell command -v /usr/bin/python3.12 2>/dev/null)
ifneq ($(SYSTEM_PY),)
export UV_PYTHON ?= $(SYSTEM_PY)
endif

.PHONY: sync test lint fmt typecheck gate phases schemas fixtures golden packs perf mcp emboss a11y emboss-lint gallery hub web e2e check clean

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

perf: sync
	MYELIN_PERF=1 $(UV) run pytest -q -s tests/test_perf_index.py

VAULT ?= .
mcp: sync
	$(UV) run myelin-mcp --vault $(VAULT)

emboss:
	python3 scripts/emboss.py build

a11y:
	python3 scripts/emboss.py a11y

emboss-lint:
	python3 scripts/emboss.py lint

PORT ?= 8787
web:
	npm install --prefix packages/myelin-hub/web --no-audit --no-fund
	npm run --prefix packages/myelin-hub/web build

hub: sync
	$(UV) run myelin-hub --vault $(VAULT) --port $(PORT)

e2e:
	npm run --prefix packages/myelin-hub/web e2e:screens

CHROME ?= $(shell command -v google-chrome google-chrome-stable chromium chromium-browser 2>/dev/null | head -1)
gallery:
	mkdir -p docs/reports/P5
	$(CHROME) --headless=new --disable-gpu --hide-scrollbars --window-size=1280,2400 \
	  --screenshot=docs/reports/P5/gallery.png file://$(CURDIR)/design/gallery/index.html

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
