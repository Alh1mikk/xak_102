#!/usr/bin/env bash
set -euo pipefail

# Локальный запуск тестов с покрытием.
# Требуется: Python 3.12, virtualenv, Node 20+, PostgreSQL (опционально для интеграционных тестов).

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "=== Backend ==="
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install --upgrade pip
backend/.venv/bin/python -m pip install -q -r backend/requirements.txt
backend/.venv/bin/python -m pytest backend -q --cov=app --cov-report=term-missing --cov-report=term --cov-fail-under=80

echo
echo "=== Frontend ==="
cd frontend
if [ ! -d node_modules ]; then
  npm ci
fi
npm run test:coverage
npm run coverage:check
