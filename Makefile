.PHONY: help install lock check format format-check lint pre-push run docker-build docker-run docker-stop
.PHONY: install-poetry

IMAGE ?= swimming-app:latest
PORT ?= 8501
CONTAINER ?= swimming-app
CSV_DIR ?= $(CURDIR)/CSV
POETRY ?= $(shell if command -v poetry >/dev/null 2>&1; then command -v poetry; \
	elif [ -x "$$HOME/.local/bin/poetry" ]; then echo "$$HOME/.local/bin/poetry"; \
	elif [ -x "$$HOME/Library/Python/3.12/bin/poetry" ]; then echo "$$HOME/Library/Python/3.12/bin/poetry"; \
	fi)

guard-poetry:
	@if [ -z "$(POETRY)" ]; then \
		echo "Poetry is not installed."; \
		echo "Run: make install-poetry"; \
		exit 1; \
	fi

help:
	@echo "Available commands:"
	@echo "  make install-poetry - Install Poetry"
	@echo "  make install      - Install Python dependencies with Poetry"
	@echo "  make lock         - Regenerate poetry.lock from pyproject.toml"
	@echo "  make check        - Syntax-check core scripts"
	@echo "  make format       - Auto-format code with Ruff"
	@echo "  make format-check - Verify formatting without changes"
	@echo "  make lint         - Run Ruff lint checks"
	@echo "  make pre-push     - Required quality gate before push/PR"
	@echo "  make run          - Run Streamlit app locally via Poetry"
	@echo "  make docker-build - Build Docker image ($(IMAGE))"
	@echo "  make docker-run   - Run Docker with local CSV mounted (live data)"
	@echo "  make docker-stop  - Stop/remove running app container"

install-poetry:
	@if command -v brew >/dev/null 2>&1; then \
		echo "Installing Poetry via Homebrew..."; \
		brew list poetry >/dev/null 2>&1 || brew install poetry; \
	else \
		echo "Homebrew not found. Falling back to Poetry installer script..."; \
		curl -sSL https://install.python-poetry.org | python3 -; \
	fi
	@echo "Poetry installed. If 'poetry' is not found, run:"
	@echo "  export PATH=\"$$HOME/.local/bin:$$PATH\""

install: guard-poetry
	$(POETRY) install

lock: guard-poetry
	$(POETRY) lock

check: guard-poetry
	$(POETRY) run python -m py_compile src/swimming_app/streamlit_app.py src/swimming_app/run_app.py src/swimming_app/pdf_parser.py

format: guard-poetry
	$(POETRY) run ruff format src
	$(POETRY) run ruff check --fix src

format-check: guard-poetry
	$(POETRY) run ruff format --check src

lint: guard-poetry
	$(POETRY) run ruff check src

pre-push: format-check lint check
	@echo "Pre-push checks passed."

run: guard-poetry
	$(POETRY) run streamlit run src/swimming_app/streamlit_app.py --server.address localhost --server.port 8501

docker-build:
	docker build -f Dockerfile.swimming -t $(IMAGE) .

docker-run:
	docker run -d --name $(CONTAINER) \
		-p $(PORT):8501 \
		-v $(CSV_DIR):/app/CSV \
		$(IMAGE)
	@echo "App running at http://localhost:$(PORT)"
	@echo "Using mounted CSV directory: $(CSV_DIR)"

docker-stop:
	docker rm -f $(CONTAINER) || true
