#!/usr/bin/env python3
"""
Direct spider test script - bypasses launch.sh to avoid output redirection
"""

import os
import sys

# Set environment variables
os.environ['SPIDER_START_URL'] = 'https://www.athinorama.gr/'
os.environ['SPIDER_MAX_PAGES'] = '3'
os.environ['SPIDER_MAX_DEPTH'] = '2'
os.environ['SPIDER_LOG_LEVEL'] = 'DEBUG'

# Import and run spider
try:
    from spider import quick_crawl
    
    print("🚀 DIRECT TEST: Starting spider without launch.sh...")
    print("This will show us the raw debug output")
    print("=" * 60)
    
    # Run the spider directly
    results = quick_crawl(
        start_url='https://www.athinorama.gr/',
        max_pages=3,
        max_depth=2
    )
    
    print("=" * 60)
    print("🎉 DIRECT TEST COMPLETED!")
    print(f"📊 Results: {results['summary']}")
    
except Exception as e:
    print(f"❌ DIRECT TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
