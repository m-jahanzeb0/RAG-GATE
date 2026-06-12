# Contributing to RAG-Gate

Thank you for your interest in contributing to RAG-Gate! This document outlines the steps to get started.

## Prerequisites

- Python 3.12+
- Node.js 18+
- Docker Desktop (for PostgreSQL + Redis)
- Git

## Development Setup

### 1. Fork and Clone

```bash
git clone https://github.com/your-username/RAG-GATE.git
cd RAG-GATE
```

### 2. Backend Setup

```bash
cd rag_gate

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Start infrastructure
docker compose up -d db redis

# Run migrations
python manage.py migrate

# Start the backend
python manage.py runserver
```

### 3. Frontend Setup

```bash
cd rag_gate-ui

# Install dependencies
npm install

# Start dev server (proxies to backend on port 8000)
npm run dev
```

## Running Tests

Always run the full test suite before submitting a Pull Request:

```bash
cd rag_gate
python -m pytest tests/ --ds=core.test_settings -v
```

To run with coverage:

```bash
python -m pytest tests/ --ds=core.test_settings --cov=. --cov-report=term-missing
```

All **88 tests must pass** with **no regressions** before submitting a PR.

## Making Changes

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make your changes with clear, descriptive commits.
3. Add tests for any new functionality.
4. Ensure all tests pass.
5. Submit a Pull Request with a description of your changes.

## Code Style

- **Python:** Follow PEP 8. Use type hints where possible.
- **TypeScript:** Follow the project's ESLint configuration.
- **Django:** Follow Django's coding standards. No `views.py` in the `core` directory.

## Reporting Issues

- Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) template for bugs.
- Use the [Feature Request](.github/ISSUE_TEMPLATE/feature_request.md) template for new ideas.

## Code of Conduct

Be respectful, inclusive, and constructive. We are here to build great software together.