#!/bin/bash
# DeepRepo Publishing Helper Script
# Usage: ./publish.sh [test|prod]

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PACKAGE_DIR="$SCRIPT_DIR/deeprepo_core"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() { echo -e "${BLUE}INFO: ${NC}$1"; }
print_success() { echo -e "${GREEN}SUCCESS: ${NC}$1"; }
print_warning() { echo -e "${YELLOW}WARNING: ${NC}$1"; }
print_error() { echo -e "${RED}ERROR: ${NC}$1"; }

# Display usage
usage() {
    echo "Usage: $0 [test|prod]"
    echo ""
    echo "Commands:"
    echo "  test    - Build and upload to TestPyPI (recommended first)"
    echo "  prod    - Build and upload to PyPI (production)"
    echo ""
    echo "Examples:"
    echo "  $0 test    # Test publication on TestPyPI"
    echo "  $0 prod    # Publish to production PyPI"
    exit 1
}

# Check if we're in the right directory
check_directory() {
    if [ ! -d "$PACKAGE_DIR" ]; then
        print_error "Error: deeprepo_core directory not found!"
        print_info "Please run this script from the repository root."
        exit 1
    fi
    cd "$PACKAGE_DIR"
    print_success "Found deeprepo_core directory"
}

# Check required tools
check_tools() {
    print_info "Checking required tools..."
    
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed!"
        exit 1
    fi
    print_success "Python found: $(python --version)"
    
    if ! python -c "import build" &> /dev/null; then
        print_warning "build module not found. Installing..."
        pip install build
    fi
    print_success "build module available"
    
    if ! python -c "import twine" &> /dev/null; then
        print_warning "twine module not found. Installing..."
        pip install twine
    fi
    print_success "twine module available"
}

# Pre-flight checks
preflight_checks() {
    print_info "Running pre-flight checks..."
    
    # Check for required files
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found!"
        exit 1
    fi
    print_success "pyproject.toml found"
    
    if [ ! -f "README.md" ]; then
        print_warning "README.md not found in package directory"
        print_info "Creating README.md..."
        cat > README.md << 'EOF'
# DeepRepo

A production-grade Python library for RAG on local codebases.

See the main repository for full documentation.
EOF
        print_success "Created README.md"
    else
        print_success "README.md found"
    fi
    
    # Check if LICENSE exists (should be copied from root)
    if [ ! -f "LICENSE" ]; then
        print_warning "LICENSE not found in package directory"
        if [ -f "../LICENSE" ]; then
            print_info "Copying LICENSE from repository root..."
            cp ../LICENSE .
            print_success "Copied LICENSE"
        else
            print_error "LICENSE file not found!"
            print_info "Please create a LICENSE file in the repository root"
            exit 1
        fi
    else
        print_success "LICENSE found"
    fi
    
    # Check if author email is updated
    if grep -q "your.email@example.com" pyproject.toml; then
        print_warning "Author email not updated in pyproject.toml"
        print_info "Please update the author email before publishing"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check if GitHub URLs are updated
    if grep -q "yourusername/deeprepo" pyproject.toml; then
        print_warning "GitHub URLs not updated in pyproject.toml"
        print_info "Please update the GitHub URLs before publishing"
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Get current version
    VERSION=$(grep "^version = " pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    print_success "Package version: $VERSION"
}

# Clean old builds
clean_build() {
    print_info "Cleaning old builds..."
    rm -rf build/ dist/ *.egg-info
    print_success "Cleaned build artifacts"
}

# Build package
build_package() {
    print_info "Building package..."
    python -m build
    
    if [ $? -eq 0 ]; then
        print_success "Package built successfully!"
        print_info "Contents of dist/:"
        ls -lh dist/
    else
        print_error "Build failed!"
        exit 1
    fi
}

# Check package
check_package() {
    print_info "Checking package with twine..."
    python -m twine check dist/*
    
    if [ $? -eq 0 ]; then
        print_success "Package check passed!"
    else
        print_error "Package check failed!"
        exit 1
    fi
}

# Upload to TestPyPI
upload_test() {
    print_info "Uploading to TestPyPI..."
    print_warning "You will need your TestPyPI API token"
    print_info "Username: __token__"
    print_info "Password: pypi-... (your TestPyPI token)"
    echo ""
    
    python -m twine upload --repository testpypi dist/*
    
    if [ $? -eq 0 ]; then
        print_success "Upload to TestPyPI successful!"
        echo ""
        print_info "To test installation:"
        echo -e "  ${YELLOW}pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ deeprepo${NC}"
        echo ""
        print_info "View your package:"
        echo -e "  ${YELLOW}https://test.pypi.org/project/deeprepo/${NC}"
    else
        print_error "Upload to TestPyPI failed!"
        exit 1
    fi
}

# Upload to PyPI
upload_prod() {
    print_warning "WARNING: You are about to publish to PRODUCTION PyPI!"
    print_warning "This action CANNOT be undone. Make sure you tested on TestPyPI first."
    echo ""
    read -p "Are you sure you want to continue? (yes/NO) " -r
    echo
    if [[ ! $REPLY == "yes" ]]; then
        print_info "Publication cancelled."
        exit 0
    fi
    
    print_info "Uploading to PyPI..."
    print_warning "You will need your PyPI API token"
    print_info "Username: __token__"
    print_info "Password: pypi-... (your PyPI token)"
    echo ""
    
    python -m twine upload dist/*
    
    if [ $? -eq 0 ]; then
        print_success "Upload to PyPI successful!"
        echo ""
        print_info "Your package is now live!"
        echo -e "  ${YELLOW}pip install deeprepo${NC}"
        echo ""
        print_info "View your package:"
        echo -e "  ${YELLOW}https://pypi.org/project/deeprepo/${NC}"
        echo ""
        print_info "Next steps:"
        echo "  1. Create a git tag: git tag -a v$VERSION -m 'Release v$VERSION'"
        echo "  2. Push the tag: git push origin v$VERSION"
        echo "  3. Create a GitHub release"
        echo "  4. Update your README with PyPI badge"
    else
        print_error "Upload to PyPI failed!"
        exit 1
    fi
}

# Main script
main() {
    echo "========================================"
    echo "  DeepRepo Publishing Helper"
    echo "========================================"
    echo ""
    
    # Check arguments
    if [ $# -ne 1 ]; then
        usage
    fi
    
    MODE=$1
    
    # Validate mode
    if [ "$MODE" != "test" ] && [ "$MODE" != "prod" ]; then
        print_error "Invalid mode: $MODE"
        usage
    fi
    
    # Run checks and build
    check_directory
    check_tools
    preflight_checks
    clean_build
    build_package
    check_package
    
    # Upload based on mode
    echo ""
    if [ "$MODE" == "test" ]; then
        upload_test
    elif [ "$MODE" == "prod" ]; then
        upload_prod
    fi
    
    echo ""
    print_success "All done!"
}

# Run main function
main "$@"
