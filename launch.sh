#!/bin/bash

# ============================================================================
# Legal Web Spider Launcher Script
# ============================================================================
# Configurable variables - EDIT THESE TO CUSTOMIZE YOUR CRAWL
# ============================================================================

# === TARGET CONFIGURATION ===
TARGET_URL="https://docs.python.org"
MAX_PAGES=10000
MAX_DEPTH=3
REQUESTS_PER_SECOND=1.0

# === OUTPUT CONFIGURATION ===
OUTPUT_DIR="./results"
OUTPUT_FILE="spider_results_$(date +%Y%m%d_%H%M%S).json"
LOG_FILE="spider_log_$(date +%Y%m%d_%H%M%S).log"
LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR

# === SPIDER CONFIGURATION ===
USER_AGENT="SecuritySpider/1.0 (+https://yourcompany.com/spider-info)"
RESPECT_ROBOTS="true"
AVOID_AUTH="true"
AVOID_FORMS="true"

# === TIMEOUTS ===
CONNECT_TIMEOUT=5.0
READ_TIMEOUT=30.0
MAX_RETRIES=3

# === DOCKER OPTIONS (set to true to use Docker) ===
USE_DOCKER=false
DOCKER_IMAGE="legal-spider:latest"

# === NOTIFICATION OPTIONS ===
SEND_NOTIFICATION=false
SLACK_WEBHOOK=""
EMAIL_RECIPIENT=""

# ============================================================================
# SCRIPT LOGIC - DON'T EDIT BELOW UNLESS YOU KNOW WHAT YOU'RE DOING
# ============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to show banner
show_banner() {
    echo -e "${BLUE}"
    echo "============================================"
    echo "       Legal Web Spider Launcher"
    echo "============================================"
    echo -e "${NC}"
    echo "Target URL: $TARGET_URL"
    echo "Max Pages: $MAX_PAGES"
    echo "Max Depth: $MAX_DEPTH"
    echo "Rate Limit: $REQUESTS_PER_SECOND req/sec"
    echo "Output Dir: $OUTPUT_DIR"
    echo "Docker Mode: $USE_DOCKER"
    echo "============================================"
}

# Function to check dependencies
check_dependencies() {
    log_info "Checking dependencies..."
    
    if [ "$USE_DOCKER" = true ]; then
        if ! command -v docker &> /dev/null; then
            log_error "Docker not found! Please install Docker or set USE_DOCKER=false"
            exit 1
        fi
        log_success "Docker found"
        return 0
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 not found! Please install Python 3.7+"
        exit 1
    fi
    
    # Check pip packages
    if ! python3 -c "import requests, bs4" 2>/dev/null; then
        log_warning "Missing dependencies. Installing..."
        pip3 install requests beautifulsoup4
        if [ $? -ne 0 ]; then
            log_error "Failed to install dependencies"
            exit 1
        fi
    fi
    
    # Check spider module
    if [ ! -d "spider" ]; then
        log_error "Spider module not found! Make sure you're in the project directory"
        exit 1
    fi
    
    log_success "All dependencies satisfied"
}

# Function to setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    # Create output directory
    mkdir -p "$OUTPUT_DIR"
    
    # Set environment variables
    export SPIDER_START_URL="$TARGET_URL"
    export SPIDER_MAX_PAGES="$MAX_PAGES"
    export SPIDER_MAX_DEPTH="$MAX_DEPTH"
    export SPIDER_REQUESTS_PER_SECOND="$REQUESTS_PER_SECOND"
    export SPIDER_USER_AGENT="$USER_AGENT"
    export SPIDER_RESPECT_ROBOTS="$RESPECT_ROBOTS"
    export SPIDER_AVOID_AUTH="$AVOID_AUTH"
    export SPIDER_AVOID_FORMS="$AVOID_FORMS"
    export SPIDER_TIMEOUT_CONNECT="$CONNECT_TIMEOUT"
    export SPIDER_TIMEOUT_READ="$READ_TIMEOUT"
    export SPIDER_MAX_RETRIES="$MAX_RETRIES"
    export SPIDER_OUTPUT_FILE="$OUTPUT_DIR/$OUTPUT_FILE"
    export SPIDER_LOG_FILE="$OUTPUT_DIR/$LOG_FILE"
    export SPIDER_LOG_LEVEL="$LOG_LEVEL"
    
    log_success "Environment configured"
}

# Function to create runner script
create_runner() {
    cat > run_spider_temp.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import os
from spider import create_spider

def main():
    try:
        # Create spider with environment config
        spider = create_spider()
        
        print(f"🕷️  Starting crawl: {spider.config.start_url}")
        print(f"📄 Max pages: {spider.config.max_pages}")
        print(f"⚡ Rate limit: {spider.config.requests_per_second} req/sec")
        print("="*50)
        
        # Run the crawl
        results = spider.crawl()
        
        # Save results
        output_file = spider.config.output_file
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Print summary
        summary = results['summary']
        print("\n" + "="*50)
        print("🎉 CRAWL COMPLETE!")
        print(f"📊 Pages crawled: {summary['pages_crawled']}")
        print(f"🔗 Links found: {summary['links_discovered']}")
        print(f"⏱️  Duration: {summary['duration_seconds']:.1f}s")
        print(f"📈 Speed: {summary['pages_per_second']:.2f} pages/sec")
        print(f"💾 Output: {output_file}")
        
        if summary['errors_encountered'] > 0:
            print(f"⚠️  Errors: {summary['errors_encountered']}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n🛑 Crawl interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
EOF
}

# Function to run spider with Docker
run_docker() {
    log_info "Running spider with Docker..."
    
    # Check if image exists
    if ! docker image inspect "$DOCKER_IMAGE" &> /dev/null; then
        log_error "Docker image '$DOCKER_IMAGE' not found!"
        log_info "Build it first: docker build -t $DOCKER_IMAGE ."
        exit 1
    fi
    
    # Run container
    docker run --rm \
        -e SPIDER_START_URL="$TARGET_URL" \
        -e SPIDER_MAX_PAGES="$MAX_PAGES" \
        -e SPIDER_MAX_DEPTH="$MAX_DEPTH" \
        -e SPIDER_REQUESTS_PER_SECOND="$REQUESTS_PER_SECOND" \
        -e SPIDER_USER_AGENT="$USER_AGENT" \
        -e SPIDER_RESPECT_ROBOTS="$RESPECT_ROBOTS" \
        -e SPIDER_AVOID_AUTH="$AVOID_AUTH" \
        -e SPIDER_LOG_LEVEL="$LOG_LEVEL" \
        -v "$(pwd)/$OUTPUT_DIR:/app/results" \
        "$DOCKER_IMAGE"
}

# Function to run spider locally
run_local() {
    log_info "Running spider locally..."
    
    # Create and run the spider
    create_runner
    python3 run_spider_temp.py
    local exit_code=$?
    
    # Cleanup
    rm -f run_spider_temp.py
    
    return $exit_code
}

# Function to send notifications
send_notification() {
    local status=$1
    local message=$2
    
    if [ "$SEND_NOTIFICATION" = false ]; then
        return 0
    fi
    
    # Slack notification
    if [ -n "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Spider $status: $message\"}" \
            "$SLACK_WEBHOOK" &> /dev/null
    fi
    
    # Email notification (requires mailutils)
    if [ -n "$EMAIL_RECIPIENT" ] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "Spider $status" "$EMAIL_RECIPIENT"
    fi
}

# Function to validate URL
validate_url() {
    if [[ ! "$TARGET_URL" =~ ^https?:// ]]; then
        log_error "Invalid URL: $TARGET_URL (must start with http:// or https://)"
        exit 1
    fi
}

# Function to show help
show_help() {
    echo "Legal Web Spider Launcher"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -d, --docker   Force Docker mode"
    echo "  -l, --local    Force local mode"
    echo "  -v, --verbose  Enable verbose logging"
    echo "  -q, --quiet    Quiet mode (minimal output)"
    echo ""
    echo "Configuration:"
    echo "  Edit the variables at the top of this script"
    echo "  Or set environment variables with SPIDER_ prefix"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run with default config"
    echo "  $0 --docker          # Force Docker mode"
    echo "  $0 --verbose         # Enable debug logging"
    echo ""
}

# Main execution function
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_help
                exit 0
                ;;
            -d|--docker)
                USE_DOCKER=true
                shift
                ;;
            -l|--local)
                USE_DOCKER=false
                shift
                ;;
            -v|--verbose)
                LOG_LEVEL="DEBUG"
                shift
                ;;
            -q|--quiet)
                LOG_LEVEL="ERROR"
                shift
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Show banner
    show_banner
    
    # Validate configuration
    validate_url
    
    # Check dependencies
    check_dependencies
    
    # Setup environment
    setup_environment
    
    # Record start time
    start_time=$(date +%s)
    
    # Run spider
    if [ "$USE_DOCKER" = true ]; then
        run_docker
    else
        run_local
    fi
    
    local exit_code=$?
    
    # Calculate duration
    end_time=$(date +%s)
    duration=$((end_time - start_time))
    
    # Send notifications
    if [ $exit_code -eq 0 ]; then
        log_success "Spider completed successfully in ${duration}s"
        send_notification "SUCCESS" "Crawl completed for $TARGET_URL in ${duration}s"
    else
        log_error "Spider failed with exit code $exit_code"
        send_notification "FAILED" "Crawl failed for $TARGET_URL after ${duration}s"
    fi
    
    # Show output location
    if [ $exit_code -eq 0 ]; then
        echo ""
        log_info "Results saved to: $OUTPUT_DIR/$OUTPUT_FILE"
        log_info "Logs saved to: $OUTPUT_DIR/$LOG_FILE"
    fi
    
    exit $exit_code
}

# Trap interrupts
trap 'log_warning "Script interrupted"; exit 130' INT TERM

# Run main function
main "$@"
