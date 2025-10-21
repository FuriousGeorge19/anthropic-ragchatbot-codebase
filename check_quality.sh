#!/bin/bash

# Code Quality Check Script
# This script runs all code quality checks on the backend code

set -e  # Exit on any error

echo "================================"
echo "Running Code Quality Checks"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track overall status
FAILED=0

# Run Black (check mode)
echo "1. Checking code formatting with Black..."
if uv run black --check backend/ main.py; then
    echo -e "${GREEN}✓ Black formatting check passed${NC}"
else
    echo -e "${RED}✗ Black formatting check failed${NC}"
    echo "  Run './format_code.sh' to auto-fix formatting issues"
    FAILED=1
fi
echo ""

# Run isort (check mode)
echo "2. Checking import sorting with isort..."
if uv run isort --check-only backend/ main.py; then
    echo -e "${GREEN}✓ isort check passed${NC}"
else
    echo -e "${RED}✗ isort check failed${NC}"
    echo "  Run './format_code.sh' to auto-fix import sorting"
    FAILED=1
fi
echo ""

# Run flake8
echo "3. Running flake8 linter..."
if uv run flake8 backend/ main.py; then
    echo -e "${GREEN}✓ flake8 check passed${NC}"
else
    echo -e "${RED}✗ flake8 found issues${NC}"
    FAILED=1
fi
echo ""

# Run mypy
echo "4. Running mypy type checker..."
if uv run mypy backend/; then
    echo -e "${GREEN}✓ mypy type check passed${NC}"
else
    echo -e "${YELLOW}⚠ mypy found type issues${NC}"
    echo "  Note: Type checking is informational only"
fi
echo ""

# Final summary
echo "================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All quality checks passed!${NC}"
    exit 0
else
    echo -e "${RED}Some quality checks failed.${NC}"
    echo "Please fix the issues above before committing."
    exit 1
fi
