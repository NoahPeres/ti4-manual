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
	ruff check src tests

typecheck:
	uv pip install ty
	ty check src tests

format:
	uv pip install ruff
	ruff format src tests

clean:
	rm -rf .venv __pycache__ .pytest_cache

update:
	uv pip compile --all-extras -o requirements.txt pyproject.toml
	make install

setup:
	python -m pip install uv || pip install uv
