#!/usr/bin/env python3
"""
Legal Web Spider Module

A production-ready, ethical web crawler built for cybersecurity professionals.
Respects robots.txt, avoids authentication areas, and provides comprehensive audit trails.

Main Components:
- quick_crawl(): Simple one-liner function for basic crawling
- create_spider(): Full-featured spider with configuration
- SpiderConfig: Configuration management class
- LegalSpider: Main spider orchestrator class

Example Usage:
    # Simple usage
    from spider import quick_crawl
    results = quick_crawl('https://example.com', max_pages=50)
    
    # Advanced usage
    from spider import create_spider, SpiderConfig
    config = SpiderConfig(start_url='https://example.com', max_pages=100)
    spider = create_spider()
    spider.config = config
    results = spider.crawl()
"""

# Import main public API
try:
    from .spider import quick_crawl, create_spider, LegalSpider
    from .config import SpiderConfig, load_config, create_example_config
    from .utils import SpiderError, setup_logging
    from .safety import SafetyManager
    from .http_client import HTTPClient
except ImportError as e:
    # Graceful handling of missing dependencies
    import sys
    print(f"Warning: Failed to import spider components: {e}")
    print("Make sure you have installed: pip install requests beautifulsoup4")
    sys.exit(1)

# Define public API
__all__ = [
    # Main functions (most commonly used)
    'quick_crawl',
    'create_spider',
    
    # Configuration
    'SpiderConfig',
    'load_config',
    'create_example_config',
    
    # Main classes
    'LegalSpider',
    'SafetyManager', 
    'HTTPClient',
    
    # Utilities
    'SpiderError',
    'setup_logging',
]

# Module metadata
__version__ = "1.0.0"
__author__ = "Legal Spider Team"
__description__ = "Ethical web crawler for cybersecurity professionals"
__license__ = "MIT"

# Quick version check
def version():
    """Return module version."""
    return __version__

# Module-level configuration check
def check_dependencies():
    """Check if all required dependencies are available."""
    try:
        import requests
        import bs4
        return True, "All dependencies available"
    except ImportError as e:
        return False, f"Missing dependency: {e}"

# Convenience function for module info
def info():
    """Display module information."""
    deps_ok, deps_msg = check_dependencies()
    
    print(f"Legal Web Spider v{__version__}")
    print(f"Description: {__description__}")
    print(f"Dependencies: {deps_msg}")
    print(f"Components loaded: {len(__all__)} items")
    print("\nQuick start:")
    print("  from spider import quick_crawl")
    print("  results = quick_crawl('https://example.com')")
    print("  print(results['summary'])")

# Module initialization message (only in debug mode)
if __debug__:
    deps_ok, _ = check_dependencies()
    if not deps_ok:
        print("Warning: Some dependencies missing. Run: pip install requests beautifulsoup4")
