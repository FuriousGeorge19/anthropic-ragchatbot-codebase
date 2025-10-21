#!/bin/bash

# Code Formatting Script
# This script automatically formats all Python code

set -e  # Exit on any error

echo "================================"
echo "Auto-formatting Python Code"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Run isort
echo "1. Sorting imports with isort..."
uv run isort backend/ main.py
echo -e "${GREEN}✓ Imports sorted${NC}"
echo ""

# Run Black
echo "2. Formatting code with Black..."
uv run black backend/ main.py
echo -e "${GREEN}✓ Code formatted${NC}"
echo ""

echo "================================"
echo -e "${GREEN}Code formatting complete!${NC}"
echo "Run './check_quality.sh' to verify all quality checks pass."
