PYTHON := uv python

venv:
	uv venv

install:
	uv pip install -r requirements.txt
	uv pip install -e .

test:
	uv pip install -r requirements.txt
	uv run pytest --cov .

lint:
	uv pip install ruff
	uv run ruff check src tests

typecheck:
	uv pip install ty
	uv run ty check src tests

format:
	uv pip install ruff
	uv run ruff format src tests

.PHONY: precommit
precommit: format lint typecheck test

clean:
	rm -rf .venv __pycache__ .pytest_cache

update:
	uv pip compile --all-extras -o requirements.txt pyproject.toml
	make install

setup:
	python -m pip install uv || pip install uv
