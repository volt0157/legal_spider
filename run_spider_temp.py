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
