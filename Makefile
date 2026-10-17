.PHONY: sync lint type test check gate

P ?= current

sync:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

type:
	uv run mypy

test:
	uv run pytest

check: lint type test

# Phase Gate: make gate P=0  (P=current 이면 PHASE_STATE.md의 current_phase 사용)
gate: check
	uv run python scripts/gate.py $(P)
