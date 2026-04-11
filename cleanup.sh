#!/bin/bash
# Cleanup script to remove unnecessary files and folders
# Usage: ./cleanup.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() { echo -e "${BLUE}ℹ ${NC}$1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

echo "========================================"
echo "  DeepRepo Cleanup Script"
echo "========================================"
echo ""

cd "$SCRIPT_DIR"

# Remove .DS_Store files
print_info "Removing .DS_Store files..."
find . -name ".DS_Store" -type f -delete 2>/dev/null || true
print_success "Removed .DS_Store files"

# Remove __pycache__ directories
print_info "Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
print_success "Removed __pycache__ directories"

# Remove .pytest_cache
print_info "Removing .pytest_cache..."
rm -rf .pytest_cache 2>/dev/null || true
print_success "Removed .pytest_cache"

# Remove build artifacts
print_info "Removing build artifacts..."
rm -rf deeprepo_core/build 2>/dev/null || true
rm -rf deeprepo_core/dist 2>/dev/null || true
rm -rf deeprepo_core/src/*.egg-info 2>/dev/null || true
print_success "Removed build artifacts"

# Remove MCP publisher tool (will be re-downloaded when needed)
print_info "Removing MCP publisher tool..."
rm -rf .mcp-publisher 2>/dev/null || true
print_success "Removed MCP publisher tool"

# Remove test vector files
print_info "Removing test vector files..."
find . -name "test_vectors_*.json" -type f -delete 2>/dev/null || true
rm -rf test_data_* 2>/dev/null || true
print_success "Removed test vector files"

# Remove Python cache files
print_info "Removing Python cache files..."
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
find . -type f -name "*.pyd" -delete 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
print_success "Removed Python cache files"

echo ""
print_success "Cleanup complete! 🧹"
echo ""
print_info "Note: These files/folders will be automatically ignored by git:"
echo "  - .DS_Store files"
echo "  - __pycache__/ directories"
echo "  - dist/ and build/ folders"
echo "  - .pytest_cache/"
echo "  - *.egg-info/ folders"
echo "  - .mcp-publisher/ folder"
echo ""
print_info "To verify what will be ignored, run: git status"

