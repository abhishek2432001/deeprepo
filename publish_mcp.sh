#!/bin/bash
# DeepRepo MCP Registry Publishing Helper Script
# Usage: ./publish_mcp.sh

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PUBLISHER_DIR="$SCRIPT_DIR/.mcp-publisher"
PUBLISHER_BIN="$PUBLISHER_DIR/mcp-publisher"

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
    echo "Usage: $0"
    echo ""
    echo "This script publishes your DeepRepo MCP server to the MCP Registry."
    echo ""
    echo "Prerequisites:"
    echo "  - server.json file must exist in the repository root"
    echo "  - GitHub account for authentication (uses GitHub OIDC)"
    echo ""
    echo "The script will:"
    echo "  1. Download the MCP Publisher tool"
    echo "  2. Authenticate with GitHub OIDC"
    echo "  3. Publish your MCP server to the registry"
    exit 1
}

# Detect OS and architecture
detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    # Map architecture
    case "$ARCH" in
        x86_64)
            ARCH="amd64"
            ;;
        aarch64|arm64)
            ARCH="arm64"
            ;;
        *)
            print_error "Unsupported architecture: $ARCH"
            exit 1
            ;;
    esac
    
    # Map OS
    case "$OS" in
        darwin)
            OS="darwin"
            ;;
        linux)
            OS="linux"
            ;;
        *)
            print_error "Unsupported OS: $OS"
            exit 1
            ;;
    esac
    
    print_success "Detected platform: ${OS}_${ARCH}"
}

# Download MCP Publisher
download_publisher() {
    print_info "Downloading MCP Publisher tool..."
    
    # Create directory for publisher
    mkdir -p "$PUBLISHER_DIR"
    
    # Check if already downloaded
    if [ -f "$PUBLISHER_BIN" ]; then
        print_info "MCP Publisher already downloaded"
        print_info "Checking for updates..."
        
        # Get latest version URL
        LATEST_URL="https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_${OS}_${ARCH}.tar.gz"
        
        # Download to temp location
        TEMP_FILE=$(mktemp)
        if curl -sL "$LATEST_URL" -o "$TEMP_FILE" 2>/dev/null; then
            # Extract to temp location
            TEMP_DIR=$(mktemp -d)
            tar -xzf "$TEMP_FILE" -C "$TEMP_DIR" 2>/dev/null || true
            
            # Check if binary exists in temp
            if [ -f "$TEMP_DIR/mcp-publisher" ]; then
                mv "$TEMP_DIR/mcp-publisher" "$PUBLISHER_BIN"
                chmod +x "$PUBLISHER_BIN"
                print_success "MCP Publisher updated"
            fi
            
            rm -rf "$TEMP_DIR" "$TEMP_FILE"
        else
            print_warning "Could not check for updates, using existing version"
        fi
    else
        # Download latest version
        LATEST_URL="https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_${OS}_${ARCH}.tar.gz"
        
        print_info "Downloading from: $LATEST_URL"
        
        TEMP_FILE=$(mktemp)
        if ! curl -sL "$LATEST_URL" -o "$TEMP_FILE"; then
            print_error "Failed to download MCP Publisher"
            print_info "Please check your internet connection and try again"
            rm -f "$TEMP_FILE"
            exit 1
        fi
        
        # Extract
        tar -xzf "$TEMP_FILE" -C "$PUBLISHER_DIR" 2>/dev/null || {
            print_error "Failed to extract MCP Publisher"
            rm -f "$TEMP_FILE"
            exit 1
        }
        
        # Make executable
        chmod +x "$PUBLISHER_BIN"
        rm -f "$TEMP_FILE"
        
        print_success "MCP Publisher downloaded successfully"
    fi
    
    # Verify it works
    if [ ! -f "$PUBLISHER_BIN" ]; then
        print_error "MCP Publisher binary not found after download"
        exit 1
    fi
    
    # Test version
    if "$PUBLISHER_BIN" --version &>/dev/null; then
        VERSION=$("$PUBLISHER_BIN" --version 2>/dev/null || echo "unknown")
        print_success "MCP Publisher version: $VERSION"
    else
        print_warning "Could not verify MCP Publisher version"
    fi
}

# Check required files
check_files() {
    print_info "Checking required files..."
    
    # Check for server.json
    if [ ! -f "$SCRIPT_DIR/server.json" ]; then
        print_error "server.json not found!"
        print_info "Please create server.json in the repository root"
        print_info "See MCP_IMPLEMENTATION_PLAN.md for details"
        exit 1
    fi
    print_success "server.json found"
    
    # Validate JSON
    if ! python -m json.tool "$SCRIPT_DIR/server.json" > /dev/null 2>&1; then
        print_error "server.json is not valid JSON!"
        print_info "Please check the file format"
        exit 1
    fi
    print_success "server.json is valid JSON"
    
    # Check if we're in the right directory (should have server.json)
    cd "$SCRIPT_DIR"
    print_success "Working directory: $SCRIPT_DIR"
}

# Authenticate with MCP Registry
authenticate() {
    print_info "Authenticating with MCP Registry..."
    print_info "Using GitHub OIDC authentication"
    echo ""
    
    if "$PUBLISHER_BIN" login github-oidc; then
        print_success "Authentication successful!"
    else
        print_error "Authentication failed!"
        print_info "Make sure you have:"
        print_info "  1. A GitHub account"
        print_info "  2. Proper permissions"
        print_info "  3. Internet connectivity"
        exit 1
    fi
}

# Publish to MCP Registry
publish() {
    print_info "Publishing to MCP Registry..."
    echo ""
    
    # Get version from server.json
    VERSION=$(python -c "import json; print(json.load(open('server.json'))['version'])" 2>/dev/null || echo "unknown")
    print_info "Publishing version: $VERSION"
    echo ""
    
    # Publish
    if "$PUBLISHER_BIN" publish; then
        print_success "Publication to MCP Registry successful!"
        echo ""
        print_info "Your MCP server is now available in the marketplace!"
        echo ""
        print_info "Next steps:"
        echo "  1. Verify your server appears in the MCP Registry"
        echo "  2. Share the installation command with users:"
        echo -e "     ${YELLOW}pip install deeprepo[mcp]${NC}"
        echo "  3. Update your README with marketplace links"
        echo "  4. Create a GitHub release if you haven't already"
    else
        print_error "Publication failed!"
        print_info "Please check:"
        print_info "  1. Your server.json is correct"
        print_info "  2. You're authenticated"
        print_info "  3. The version hasn't been published before"
        exit 1
    fi
}

# Main script
main() {
    echo "========================================"
    echo "  DeepRepo MCP Registry Publisher"
    echo "========================================"
    echo ""
    
    # Detect platform
    detect_platform
    
    # Check files
    check_files
    
    # Download publisher
    download_publisher
    
    # Authenticate
    echo ""
    authenticate
    
    # Publish
    echo ""
    publish
    
    echo ""
    print_success "All done!
    echo ""
    print_info "Your MCP server is now published to the MCP Registry!"
}

# Run main function
main "$@"

