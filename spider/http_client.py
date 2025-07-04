#!/usr/bin/env python3
"""
Legal Web Spider HTTP Client Module

Robust HTTP handling with domain-specific rate limiting, exponential backoff,
status code-specific retry logic, and connection management that respects
server resources while maintaining high reliability.
"""

import time
import random
import logging
import threading
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Dict, Optional, Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .config import SpiderConfig
from .utils import extract_domain, HTTPError, RateLimitError, Timer


@dataclass
class HTTPResponse:
    """
    Wrapper for HTTP response with additional metadata.
    """
    url: str
    status_code: int
    content: str
    headers: Dict[str, str]
    elapsed_time: float
    final_url: str = ""
    content_type: str = ""
    encoding: str = "utf-8"
    
    def __post_init__(self):
        """Extract additional metadata from headers."""
        # Case-insensitive header lookup
        content_type = ''
        for key, value in self.headers.items():
            if key.lower() == 'content-type':
                content_type = value
                break
        self.content_type = content_type.lower()
        if not self.final_url:
            self.final_url = self.url
    
    @property
    def is_html(self) -> bool:
        """Check if response contains HTML content."""
        ct = self.content_type.lower()
        return any(html_type in ct for html_type in ['text/html', 'html', 'application/xhtml'])
    
    @property
    def is_binary(self) -> bool:
        """Check if response contains binary content."""
        binary_types = ['application/octet-stream', 'image/', 'video/', 'audio/']
        return any(bt in self.content_type for bt in binary_types)
    
    @property
    def size_mb(self) -> float:
        """Get content size in MB."""
        return len(self.content.encode('utf-8')) / (1024 * 1024)


class TokenBucket:
    """
    Thread-safe token bucket for rate limiting.
    """
    
    def __init__(self, capacity: int = 10, refill_rate: float = 1.0):
        """
        Initialize token bucket.
        
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens from bucket.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False otherwise
        """
        with self.lock:
            now = time.time()
            
            # Add tokens based on elapsed time
            elapsed = now - self.last_refill
            tokens_to_add = elapsed * self.refill_rate
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            self.last_refill = now
            
            # Try to consume tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time needed for tokens."""
        with self.lock:
            if self.tokens >= tokens:
                return 0.0
            needed_tokens = tokens - self.tokens
            return needed_tokens / self.refill_rate


class DomainRateLimiter:
    """
    Manages rate limiting across multiple domains.
    """
    
    def __init__(self, requests_per_second: float = 1.0, burst_capacity: int = 5):
        """
        Initialize domain rate limiter.
        
        Args:
            requests_per_second: Default rate limit per domain
            burst_capacity: Maximum burst requests allowed
        """
        self.default_rate = requests_per_second
        self.burst_capacity = burst_capacity
        self.domain_buckets: Dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(
                capacity=self.burst_capacity,
                refill_rate=self.default_rate
            )
        )
        self.logger = logging.getLogger('LegalSpider.RateLimiter')
    
    def wait_if_needed(self, domain: str, custom_delay: Optional[float] = None) -> None:
        """
        Wait if needed to respect rate limits.
        
        Args:
            domain: Domain to rate limit
            custom_delay: Optional custom delay (e.g., from robots.txt)
        """
        bucket = self.domain_buckets[domain]
        
        # Use custom delay if provided (e.g., from robots.txt)
        if custom_delay:
            time.sleep(custom_delay)
            return
        
        # Try to consume token
        while not bucket.consume():
            wait_time = bucket.wait_time()
            self.logger.debug(f"Rate limiting {domain}, waiting {wait_time:.2f}s")
            time.sleep(min(wait_time, 1.0))  # Cap wait time at 1 second
    
    def set_domain_rate(self, domain: str, requests_per_second: float) -> None:
        """Set custom rate limit for specific domain."""
        self.domain_buckets[domain] = TokenBucket(
            capacity=self.burst_capacity,
            refill_rate=requests_per_second
        )


class SessionManager:
    """
    Manages HTTP sessions with connection pooling and proper configuration.
    """
    
    def __init__(self, config: SpiderConfig):
        self.config = config
        self.sessions: Dict[str, requests.Session] = {}
        self.logger = logging.getLogger('LegalSpider.SessionManager')
    
    def get_session(self, domain: str) -> requests.Session:
        """
        Get or create session for domain.
        
        Args:
            domain: Domain to get session for
            
        Returns:
            Configured requests session
        """
        if domain not in self.sessions:
            self.sessions[domain] = self._create_session()
        
        return self.sessions[domain]
    
    def _create_session(self) -> requests.Session:
        """Create properly configured session."""
        session = requests.Session()
        
        # Set user agent
        session.headers.update({
            'User-Agent': self.config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Configure retries at adapter level
        retry_strategy = Retry(
            total=0,  # We handle retries manually
            backoff_factor=0,
            status_forcelist=[]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def close_all(self) -> None:
        """Close all sessions."""
        for session in self.sessions.values():
            session.close()
        self.sessions.clear()


class HTTPClient:
    """
    Main HTTP client with comprehensive error handling and rate limiting.
    """
    
    def __init__(self, config: SpiderConfig):
        self.config = config
        self.rate_limiter = DomainRateLimiter(config.requests_per_second)
        self.session_manager = SessionManager(config)
        self.logger = logging.getLogger('LegalSpider.HTTPClient')
        
        # Statistics
        self.stats = {
            'requests_made': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retries_performed': 0,
            'rate_limited_requests': 0,
            'total_bytes_downloaded': 0,
        }
    
    def fetch(self, url: str, custom_delay: Optional[float] = None) -> Optional[HTTPResponse]:
        """
        Fetch URL with comprehensive error handling and retries.
        
        Args:
            url: URL to fetch
            custom_delay: Optional custom delay (e.g., from robots.txt)
            
        Returns:
            HTTPResponse object or None if failed
        """
        domain = extract_domain(url)
        if not domain:
            self.logger.error(f"Invalid URL: {url}")
            return None
        
        # Apply rate limiting
        self.rate_limiter.wait_if_needed(domain, custom_delay)
        
        # Perform request with retries
        return self._fetch_with_retry(url)
    
    def _fetch_with_retry(self, url: str) -> Optional[HTTPResponse]:
        """
        Fetch URL with exponential backoff retry logic.
        """
        domain = extract_domain(url)
        session = self.session_manager.get_session(domain)
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                with Timer(f"HTTP request to {url}") as timer:
                    response = session.get(
                        url,
                        timeout=(self.config.timeout_connect, self.config.timeout_read),
                        allow_redirects=True,
                        stream=False
                    )
                
                self.stats['requests_made'] += 1
                
                # Handle different status codes
                should_retry, delay = self._handle_status_code(response, attempt)
                
                if not should_retry:
                    if response.status_code == 200:
                        self.stats['successful_requests'] += 1
                        return self._create_response(response, timer.elapsed)
                    else:
                        self.stats['failed_requests'] += 1
                        self.logger.warning(f"HTTP {response.status_code} for {url}")
                        return None
                
                # Handle retry with delay
                if attempt < self.config.max_retries:
                    self.stats['retries_performed'] += 1
                    self.logger.info(f"Retrying {url} in {delay:.1f}s (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                self.logger.warning(f"Timeout for {url}: {e}")
                
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                self.logger.warning(f"Connection error for {url}: {e}")
                
            except requests.exceptions.RequestException as e:
                last_exception = e
                self.logger.error(f"Request error for {url}: {e}")
                break  # Don't retry on request exceptions
            
            except Exception as e:
                last_exception = e
                self.logger.error(f"Unexpected error for {url}: {e}")
                break
            
            # Calculate retry delay
            if attempt < self.config.max_retries:
                delay = self._calculate_retry_delay(attempt)
                self.stats['retries_performed'] += 1
                time.sleep(delay)
        
        # All retries failed
        self.stats['failed_requests'] += 1
        self.logger.error(f"Failed to fetch {url} after {self.config.max_retries} retries")
        
        if last_exception:
            raise HTTPError(f"Failed to fetch {url}: {last_exception}")
        
        return None
    
    def _handle_status_code(self, response: requests.Response, attempt: int) -> tuple:
        """
        Handle different HTTP status codes.
        
        Returns:
            Tuple of (should_retry, delay)
        """
        status_code = response.status_code
        
        # Success
        if status_code == 200:
            return False, 0
        
        # Rate limiting
        if status_code == 429:
            self.stats['rate_limited_requests'] += 1
            retry_after = int(response.headers.get('Retry-After', 60))
            delay = min(retry_after, 300)  # Cap at 5 minutes
            self.logger.warning(f"Rate limited, waiting {delay}s")
            return True, delay
        
        # Server errors (retry)
        if status_code in [500, 502, 503, 504]:
            delay = self._calculate_retry_delay(attempt)
            return True, delay
        
        # Client errors (don't retry)
        if 400 <= status_code < 500:
            return False, 0
        
        # Other errors (retry)
        delay = self._calculate_retry_delay(attempt)
        return True, delay
    
    def _calculate_retry_delay(self, attempt: int) -> float:
        """Calculate retry delay with exponential backoff and jitter."""
        base_delay = 2.0 ** attempt
        jitter = random.uniform(0, 1)
        return base_delay + jitter
    
    def _create_response(self, response: requests.Response, elapsed_time: float) -> HTTPResponse:
        """Create HTTPResponse object from requests.Response."""
        # Handle encoding
        if response.encoding is None:
            response.encoding = 'utf-8'
        
        # Get content with size limit
        max_size = 50 * 1024 * 1024  # 50MB limit
        content = response.text
        
        if len(content.encode('utf-8')) > max_size:
            self.logger.warning(f"Large content size, truncating: {response.url}")
            content = content[:max_size]
        
        self.stats['total_bytes_downloaded'] += len(content.encode('utf-8'))
        
        return HTTPResponse(
            url=response.url,
            status_code=response.status_code,
            content=content,
            headers=dict(response.headers),
            elapsed_time=elapsed_time,
            final_url=response.url,
            encoding=response.encoding or 'utf-8'
        )
    
    def set_domain_rate(self, domain: str, requests_per_second: float) -> None:
        """Set custom rate limit for domain."""
        self.rate_limiter.set_domain_rate(domain, requests_per_second)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get HTTP client statistics."""
        stats = self.stats.copy()
        if stats['requests_made'] > 0:
            stats['success_rate'] = stats['successful_requests'] / stats['requests_made']
        else:
            stats['success_rate'] = 0.0
        
        stats['total_mb_downloaded'] = stats['total_bytes_downloaded'] / (1024 * 1024)
        return stats
    
    def close(self) -> None:
        """Close all sessions and cleanup."""
        self.session_manager.close_all()


if __name__ == "__main__":
    # Demo and testing
    print("=== Legal Spider HTTP Client Demo ===")
    
    from .config import SpiderConfig
    
    # Create test configuration
    config = SpiderConfig(
        start_url="https://httpbin.org",
        timeout_connect=5.0,
        timeout_read=10.0,
        max_retries=2,
        requests_per_second=2.0
    )
    
    # Initialize HTTP client
    client = HTTPClient(config)
    
    # Test URLs
    test_urls = [
        "https://httpbin.org/get",
        "https://httpbin.org/status/200",
        "https://httpbin.org/delay/1",
    ]
    
    print("\n1. Testing HTTP requests:")
    for url in test_urls:
        try:
            print(f"   Fetching: {url}")
            response = client.fetch(url)
            if response:
                print(f"   ✅ Status: {response.status_code}, Size: {len(response.content)} bytes")
                print(f"   ⏱️  Time: {response.elapsed_time:.2f}s, Type: {response.content_type}")
            else:
                print(f"   ❌ Failed to fetch")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print()  # Space between tests
    
    # Test rate limiting
    print("2. Testing rate limiting:")
    start_time = time.time()
    for i in range(3):
        response = client.fetch("https://httpbin.org/get")
        elapsed = time.time() - start_time
        print(f"   Request {i+1} at {elapsed:.1f}s")
    
    # Show statistics
    print("\n3. HTTP Client Statistics:")
    stats = client.get_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.3f}")
        else:
            print(f"   {key}: {value}")
    
    # Cleanup
    client.close()
    print("\n✅ HTTP client working correctly!")
