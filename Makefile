.PHONY: help install install-dev test lint format clean build upload docs

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install:  ## Install the package
	pip install -e .

install-dev:  ## Install development dependencies
	pip install -e .
	pip install -r requirements-dev.txt

test:  ## Run tests
	pytest tests/ --cov=src/echr_extractor --cov-report=term-missing

lint:  ## Run linting checks
	flake8 src tests
	black --check src tests
	isort --check-only src tests

format:  ## Format code
	black src tests
	isort src tests

clean:  ## Clean build artifacts
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:  ## Build package
	python -m build

upload:  ## Upload to PyPI (requires TWINE_PASSWORD env var)
	twine upload dist/*

docs:  ## Build documentation
	@echo "Documentation not yet implemented"
