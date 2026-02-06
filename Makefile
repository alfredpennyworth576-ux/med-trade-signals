.PHONY: test lint clean run help install

# Default target
help:
	@echo "Med-Trade-Signals Development Commands"
	@echo ""
	@echo "Commands:"
	@echo "  test        - Run all tests"
	@echo "  test-cov    - Run tests with coverage"
	@echo "  lint        - Run linting checks"
	@echo "  format      - Format code with black and isort"
	@echo "  run         - Run the pipeline"
	@echo "  install     - Install dependencies"
	@echo "  clean       - Clean build artifacts and cache"
	@echo "  typecheck   - Run type checker"

# Install dependencies
install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

# Run all tests
test:
	pytest tests/ -v --tb=short

# Run tests with coverage
test-cov:
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# Run linting
lint:
	flake8 src/ tests/ --max-line-length=88 --extend-ignore=E203
	isort --check-only --diff src/ tests/
	black --check src/ tests/

# Format code
format:
	black src/ tests/
	isort src/ tests/

# Run the pipeline
run:
	python pipeline.py

# Run with specific source
run-pubmed:
	python pipeline.py --source=pubmed

run-fda:
	python pipeline.py --source=fda

run-reddit:
	python pipeline.py --source=reddit

# Clean build artifacts
clean:
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.tox' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.eggs' -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ *.egg-info/ 2>/dev/null || true
	rm -rf htmlcov/ .coverage 2>/dev/null || true
	rm -rf .mypy_cache/ 2>/dev/null || true

# Type checking
typecheck:
	mypy src/ --ignore-missing-imports

# Quick test run (no verbose)
test-quick:
	pytest tests/ -q

# Watch tests (requires pytest-watch)
test-watch:
	ptw tests/

# Check for missing tests
test-missing:
	pytest tests/ --collect-only -q | grep "no tests"
