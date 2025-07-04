#!/usr/bin/env python3
"""
Legal Web Spider Main Module

Main orchestrator that coordinates all spider components to perform
ethical, legal, and efficient web crawling with comprehensive reporting.
"""

import time
import logging
from dataclasses import dataclass, field
from collections import deque
from typing import Dict, List, Optional, Set, Any
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

from .config import SpiderConfig, load_config
from .utils import (
    extract_domain, is_same_domain, normalize_url, 
    setup_logging, Timer, SpiderError
)
from .safety import SafetyManager
from .http_client import HTTPClient


@dataclass
class URLItem:
    """
    Represents a URL to be crawled with metadata.
    """
    url: str
    depth: int
    parent_url: Optional[str] = None
    discovered_at: float = field(default_factory=time.time)
    priority: int = 0
    
    def __lt__(self, other):
        """Allow sorting by priority."""
        return self.priority < other.priority


class URLQueue:
    """
    Manages URL crawling queue with deduplication and priority handling.
    """
    
    def __init__(self, max_size: int = 10000):
        self.queue = deque()
        self.visited: Set[str] = set()
        self.in_queue: Set[str] = set()
        self.max_size = max_size
        self.logger = logging.getLogger('LegalSpider.URLQueue')
    
    def add_url(self, url: str, depth: int, parent: Optional[str] = None, priority: int = 0) -> bool:
        """
        Add URL to queue if not already processed.
        
        Args:
            url: URL to add
            depth: Crawl depth
            parent: Parent URL that discovered this URL
            priority: Priority (lower = higher priority)
            
        Returns:
            True if added, False if duplicate or queue full
        """
        normalized_url = normalize_url(url)
        
        # Check if already processed or in queue
        if normalized_url in self.visited or normalized_url in self.in_queue:
            return False
        
        # Check queue size limit
        if len(self.queue) >= self.max_size:
            self.logger.warning(f"Queue size limit reached: {self.max_size}")
            return False
        
        # Add to queue
        url_item = URLItem(
            url=normalized_url,
            depth=depth,
            parent_url=parent,
            priority=priority
        )
        
        self.queue.append(url_item)
        self.in_queue.add(normalized_url)
        
        return True
    
    def get_next_url(self) -> Optional[URLItem]:
        """Get next URL to crawl."""
        if not self.queue:
            return None
        
        url_item = self.queue.popleft()
        self.in_queue.remove(url_item.url)
        self.visited.add(url_item.url)
        
        return url_item
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self.queue) == 0
    
    def size(self) -> int:
        """Get current queue size."""
        return len(self.queue)
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        return {
            'queue_size': len(self.queue),
            'visited_count': len(self.visited),
            'total_discovered': len(self.visited) + len(self.queue)
        }


class LegalSpider:
    """
    Main spider class that orchestrates all components for legal web crawling.
    """
    
    def __init__(self, config: SpiderConfig):
        self.config = config
        self.logger = setup_logging(config.log_level, config.log_file)
        
        # Initialize components
        self.safety_manager = SafetyManager(config)
        self.http_client = HTTPClient(config)
        self.url_queue = URLQueue(max_size=config.max_pages * 2)
        
        # Results storage
        self.crawl_results: Dict[str, Dict[str, Any]] = {}
        self.discovered_links: Dict[str, List[str]] = {}
        
        # Statistics
        self.stats = {
            'start_time': 0,
            'end_time': 0,
            'pages_crawled': 0,
            'pages_skipped': 0,
            'links_discovered': 0,
            'errors_encountered': 0,
            'total_content_size': 0,
        }
        
        self.logger.info(f"Legal Spider initialized for: {config.start_url}")
    
    def crawl(self) -> Dict[str, Any]:
        """
        Main crawling method that orchestrates the entire process.
        
        Returns:
            Comprehensive crawl results and statistics
        """
        self.stats['start_time'] = time.time()
        
        try:
            # Add initial URL to queue
            self.url_queue.add_url(self.config.start_url, depth=0, priority=10)
            self.logger.info(f"Starting crawl from: {self.config.start_url}")
            
            # Main crawling loop
            while not self.url_queue.is_empty() and self.stats['pages_crawled'] < self.config.max_pages:
                url_item = self.url_queue.get_next_url()
                if not url_item:
                    break
                
                try:
                    self._crawl_single_page(url_item)
                except Exception as e:
                    self.stats['errors_encountered'] += 1
                    self.logger.error(f"Error crawling {url_item.url}: {e}")
            
            self.stats['end_time'] = time.time()
            
            # Generate final report
            return self._generate_report()
            
        except KeyboardInterrupt:
            self.logger.info("Crawl interrupted by user")
            self.stats['end_time'] = time.time()
            return self._generate_report()
        
        except Exception as e:
            self.logger.error(f"Critical error during crawl: {e}")
            self.stats['end_time'] = time.time()
            raise SpiderError(f"Crawl failed: {e}")
        
        finally:
            self.http_client.close()
    
    def _crawl_single_page(self, url_item: URLItem) -> None:
        """
        Crawl a single page and extract links.
        
        Args:
            url_item: URL item to crawl
        """
        url = url_item.url
        
        # Pre-crawl safety check
        if not self.safety_manager.pre_crawl_check(url, url_item.depth):
            self.stats['pages_skipped'] += 1
            self.logger.debug(f"Skipped by safety check: {url}")
            return
        
        # Get robots.txt delay if available
        robots_delay = self.safety_manager.get_robots_delay(url)
        
        # Fetch the page
        with Timer(f"Fetch {url}") as timer:
            response = self.http_client.fetch(url, custom_delay=robots_delay)
        
        if not response:
            self.stats['pages_skipped'] += 1
            self.logger.warning(f"Failed to fetch: {url}")
            return
        
        # Check if it's HTML content
        if not response.is_html:
            self.stats['pages_skipped'] += 1
            # DEBUG: Use logger to show exactly what's happening
            self.logger.error(f"🔍 DEBUG spider.py: content_type='{response.content_type}'")
            self.logger.error(f"🔍 DEBUG spider.py: is_html={response.is_html}")
            self.logger.error(f"🔍 DEBUG spider.py: response type={type(response)}")
            self.logger.error(f"🔍 DEBUG spider.py: content preview='{response.content[:100]}...'")
            self.logger.debug(f"Non-HTML content skipped: {url}")
            return
        
        # Update statistics
        self.stats['pages_crawled'] += 1
        self.stats['total_content_size'] += len(response.content)
        
        self.logger.info(f"Crawled [{self.stats['pages_crawled']}/{self.config.max_pages}]: {url}")
        
        # Post-crawl safety analysis
        safety_analysis = self.safety_manager.post_crawl_analysis(url, response.content)
        
        # Extract links
        extracted_links = self._extract_links(response.content, url)
        self.discovered_links[url] = extracted_links
        self.stats['links_discovered'] += len(extracted_links)
        
        # Store results
        self.crawl_results[url] = {
            'url': url,
            'depth': url_item.depth,
            'parent_url': url_item.parent_url,
            'status_code': response.status_code,
            'content_type': response.content_type,
            'content_size': len(response.content),
            'response_time': response.elapsed_time,
            'links_found': len(extracted_links),
            'safety_analysis': safety_analysis,
            'crawled_at': time.time()
        }
        
        # Add discovered links to queue
        for link in extracted_links:
            if url_item.depth < self.config.max_depth:
                self.url_queue.add_url(
                    url=link,
                    depth=url_item.depth + 1,
                    parent=url,
                    priority=url_item.depth + 1
                )
    
    def _extract_links(self, html_content: str, base_url: str) -> List[str]:
        """
        Extract internal links from HTML content.
        
        Args:
            html_content: HTML content to parse
            base_url: Base URL for resolving relative links
            
        Returns:
            List of internal links found
        """
        if not HAS_BS4:
            self.logger.warning("BeautifulSoup not available - link extraction disabled")
            return []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            base_domain = extract_domain(base_url)
            
            # Find all anchor tags with href attributes
            for anchor in soup.find_all('a', href=True):
                href = anchor['href'].strip()
                
                # Skip empty hrefs and anchors
                if not href or href.startswith('#'):
                    continue
                
                # Convert to absolute URL
                absolute_url = urljoin(base_url, href)
                
                # Check if it's an internal link
                if is_same_domain(base_url, absolute_url):
                    normalized_url = normalize_url(absolute_url)
                    if normalized_url not in links:
                        links.append(normalized_url)
            
            return links
            
        except Exception as e:
            self.logger.error(f"Error extracting links from {base_url}: {e}")
            return []
    
    def _generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive crawl report.
        
        Returns:
            Dictionary containing all crawl data and statistics
        """
        duration = self.stats.get('end_time', time.time()) - self.stats['start_time']
        
        # Calculate rates
        pages_per_second = self.stats['pages_crawled'] / duration if duration > 0 else 0
        avg_response_time = 0
        if self.crawl_results:
            total_response_time = sum(r['response_time'] for r in self.crawl_results.values())
            avg_response_time = total_response_time / len(self.crawl_results)
        
        report = {
            'summary': {
                'start_url': self.config.start_url,
                'duration_seconds': duration,
                'pages_crawled': self.stats['pages_crawled'],
                'pages_skipped': self.stats['pages_skipped'],
                'links_discovered': self.stats['links_discovered'],
                'errors_encountered': self.stats['errors_encountered'],
                'total_content_size_mb': self.stats['total_content_size'] / (1024 * 1024),
                'pages_per_second': pages_per_second,
                'avg_response_time': avg_response_time,
            },
            'configuration': self.config.to_dict(),
            'crawl_results': self.crawl_results,
            'discovered_links': self.discovered_links,
            'queue_stats': self.url_queue.get_stats(),
            'safety_stats': self.safety_manager.get_safety_stats(),
            'http_stats': self.http_client.get_stats(),
            'generated_at': time.time()
        }
        
        # Log summary
        self._log_summary(report['summary'])
        
        return report
    
    def _log_summary(self, summary: Dict[str, Any]) -> None:
        """Log crawl summary."""
        self.logger.info("=== CRAWL SUMMARY ===")
        self.logger.info(f"Duration: {summary['duration_seconds']:.1f}s")
        self.logger.info(f"Pages crawled: {summary['pages_crawled']}")
        self.logger.info(f"Pages skipped: {summary['pages_skipped']}")
        self.logger.info(f"Links discovered: {summary['links_discovered']}")
        self.logger.info(f"Content downloaded: {summary['total_content_size_mb']:.2f} MB")
        self.logger.info(f"Average speed: {summary['pages_per_second']:.2f} pages/sec")
        self.logger.info(f"Average response time: {summary['avg_response_time']:.2f}s")
        if summary['errors_encountered'] > 0:
            self.logger.warning(f"Errors encountered: {summary['errors_encountered']}")


# === PUBLIC API ===

def create_spider(config_file: Optional[str] = None, **kwargs) -> LegalSpider:
    """
    Create a legal spider instance.
    
    Args:
        config_file: Optional configuration file path
        **kwargs: Configuration overrides
        
    Returns:
        Configured LegalSpider instance
    """
    config = load_config(config_file)
    
    # Apply any overrides
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    
    config.validate()
    return LegalSpider(config)


def quick_crawl(start_url: str, max_pages: int = 50, max_depth: int = 2) -> Dict[str, Any]:
    """
    Quick crawl with minimal configuration.
    
    Args:
        start_url: URL to start crawling from
        max_pages: Maximum pages to crawl
        max_depth: Maximum crawl depth
        
    Returns:
        Crawl results
    """
    spider = create_spider(
        start_url=start_url,
        max_pages=max_pages,
        max_depth=max_depth
    )
    return spider.crawl()


if __name__ == "__main__":
    # Demo and testing
    print("=== Legal Spider Main Module Demo ===")
    
    # Quick test crawl
    try:
        print("\n1. Testing quick crawl:")
        results = quick_crawl(
            start_url="https://example.com",
            max_pages=5,
            max_depth=1
        )
        
        summary = results['summary']
        print(f"   Crawled {summary['pages_crawled']} pages")
        print(f"   Found {summary['links_discovered']} links")
        print(f"   Duration: {summary['duration_seconds']:.1f}s")
        
    except Exception as e:
        print(f"   Demo error (expected in test environment): {e}")
    
    # Show configuration example
    print("\n2. Example configuration:")
    config = SpiderConfig(
        start_url="https://example.com",
        max_pages=100,
        max_depth=3,
        requests_per_second=2.0,
        respect_robots_txt=True
    )
    print(f"   Start URL: {config.start_url}")
    print(f"   Rate limit: {config.requests_per_second} req/sec")
    print(f"   Safety enabled: {config.respect_robots_txt}")
    
    print("\n✅ Legal Spider system ready!")
    print("\nUsage:")
    print("   from spider import quick_crawl")
    print("   results = quick_crawl('https://example.com', max_pages=100)")
    print("   print(results['summary'])")
