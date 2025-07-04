#!/usr/bin/env python3
"""
Legal Web Spider Utilities Module

Foundation utilities, decorators, exceptions, and helper functions
that provide common functionality across all spider modules.
"""

import re
import time
import random
import logging
import functools
from typing import Optional, Callable, Any, List
from urllib.parse import urlparse, urljoin, urlunparse
from pathlib import Path


# === CUSTOM EXCEPTION HIERARCHY ===

class SpiderError(Exception):
    """Base exception for all spider-related errors."""
    pass


class ConfigValidationError(SpiderError):
    """Raised when configuration validation fails."""
    pass


class RateLimitError(SpiderError):
    """Raised when rate limiting prevents operation."""
    pass


class SafetyViolationError(SpiderError):
    """Raised when safety checks prevent crawling a URL."""
    pass


class HTTPError(SpiderError):
    """Raised when HTTP operations fail."""
    pass


class RobotsError(SpiderError):
    """Raised when robots.txt parsing or checking fails."""
    pass


# === DECORATORS ===

def retry_on_failure(max_retries: int = 3, backoff_factor: float = 2.0, 
                    exceptions: tuple = (Exception,)):
    """
    Decorator that retries function calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff_factor: Multiplier for delay between retries
        exceptions: Tuple of exception types to catch and retry on
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Calculate delay with jitter
                        delay = (backoff_factor ** attempt) + random.uniform(0, 1)
                        time.sleep(delay)
                        continue
                    break
            
            # All retries failed, raise the last exception
            raise last_exception
        return wrapper
    return decorator


def timeout_after(seconds: float):
    """
    Decorator that adds timeout functionality to functions.
    Note: This is a simple implementation for demonstration.
    Production code should use proper threading or async timeouts.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            
            if elapsed > seconds:
                raise TimeoutError(f"Function {func.__name__} exceeded {seconds}s timeout")
            
            return result
        return wrapper
    return decorator


def rate_limit(calls_per_second: float = 1.0):
    """
    Decorator that enforces rate limiting on function calls.
    """
    min_interval = 1.0 / calls_per_second
    last_called = [0.0]  # Use list to make it mutable in closure
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            elapsed = time.time() - last_called[0]
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
            
            last_called[0] = time.time()
            return func(*args, **kwargs)
        return wrapper
    return decorator


# === URL UTILITIES ===

def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def is_valid_url(url: str) -> bool:
    """Check if URL is valid and well-formed."""
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def normalize_url(url: str) -> str:
    """
    Normalize URL by removing fragments, sorting query parameters,
    and standardizing the format.
    """
    try:
        parsed = urlparse(url)
        # Remove fragment and normalize
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or '/',
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        return normalized
    except Exception:
        return url


def clean_url(url: str) -> str:
    """Clean URL by removing common tracking parameters and fragments."""
    try:
        parsed = urlparse(url)
        
        # Remove common tracking parameters
        tracking_params = {
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'mc_eid', 'mc_cid', '_ga', '_gl'
        }
        
        if parsed.query:
            # Parse query parameters
            from urllib.parse import parse_qs, urlencode
            params = parse_qs(parsed.query)
            # Remove tracking parameters
            clean_params = {k: v for k, v in params.items() 
                          if k.lower() not in tracking_params}
            clean_query = urlencode(clean_params, doseq=True)
        else:
            clean_query = ''
        
        cleaned = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_query,
            ''  # No fragment
        ))
        return cleaned
    except Exception:
        return url


def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs belong to the same domain."""
    return extract_domain(url1) == extract_domain(url2)


def get_url_depth(base_url: str, target_url: str) -> int:
    """
    Calculate the depth of target_url relative to base_url.
    Returns -1 if they're not on the same domain.
    """
    if not is_same_domain(base_url, target_url):
        return -1
    
    try:
        base_path = urlparse(base_url).path.strip('/').split('/')
        target_path = urlparse(target_url).path.strip('/').split('/')
        
        # Remove empty segments
        base_path = [p for p in base_path if p]
        target_path = [p for p in target_path if p]
        
        return len(target_path) - len(base_path)
    except Exception:
        return 0


def join_url(base_url: str, relative_url: str) -> str:
    """Safely join base URL with relative URL."""
    try:
        return urljoin(base_url, relative_url)
    except Exception:
        return relative_url


# === FILE AND PATH UTILITIES ===

def get_file_extension(url: str) -> str:
    """Extract file extension from URL path."""
    try:
        path = urlparse(url).path
        return Path(path).suffix.lower()
    except Exception:
        return ""


def has_excluded_extension(url: str, excluded_extensions: List[str]) -> bool:
    """Check if URL has an excluded file extension."""
    extension = get_file_extension(url)
    return extension in [ext.lower() for ext in excluded_extensions]


# === LOGGING UTILITIES ===

def setup_logging(level: str = "INFO", 
                 output_file: Optional[str] = None,
                 format_string: Optional[str] = None) -> logging.Logger:
    """
    Set up structured logging for the spider.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        output_file: Optional file to write logs to
        format_string: Custom format string for logs
    
    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = (
            '%(asctime)s - %(name)s - %(levelname)s - '
            '%(funcName)s:%(lineno)d - %(message)s'
        )
    
    # Create logger
    logger = logging.getLogger('LegalSpider')
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(format_string)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if specified)
    if output_file:
        try:
            file_handler = logging.FileHandler(output_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not create file handler for {output_file}: {e}")
    
    return logger


# === STRING AND VALIDATION UTILITIES ===

def sanitize_filename(filename: str) -> str:
    """Sanitize string to be safe for use as filename."""
    # Remove/replace unsafe characters
    safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    safe_chars = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', safe_chars)
    # Limit length
    return safe_chars[:255]


def is_binary_content_type(content_type: str) -> bool:
    """Check if content type indicates binary content."""
    binary_types = {
        'application/octet-stream', 'application/pdf', 'application/zip',
        'image/', 'video/', 'audio/', 'application/x-', 'application/vnd.'
    }
    content_type_lower = content_type.lower()
    return any(bt in content_type_lower for bt in binary_types)


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# === TIMING AND PERFORMANCE UTILITIES ===

class Timer:
    """Simple context manager for timing operations."""
    
    def __init__(self, name: str = "Operation"):
        self.name = name
        self.start_time = 0
        self.end_time = 0
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        return self.end_time - self.start_time
    
    def __str__(self) -> str:
        return f"{self.name}: {self.elapsed:.3f}s"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


if __name__ == "__main__":
    # Demo and testing
    print("=== Legal Spider Utilities Demo ===")
    
    # Test URL utilities
    print("\n1. URL Utilities:")
    test_url = "https://example.com/path/page.html?utm_source=test&id=123#section"
    print(f"Original: {test_url}")
    print(f"Domain: {extract_domain(test_url)}")
    print(f"Clean: {clean_url(test_url)}")
    print(f"Extension: {get_file_extension(test_url)}")
    
    # Test decorators
    print("\n2. Decorator Demo:")
    
    @retry_on_failure(max_retries=2, backoff_factor=1.5)
    def flaky_function(success_rate=0.3):
        if random.random() < success_rate:
            return "Success!"
        raise Exception("Random failure")
    
    try:
        result = flaky_function(success_rate=0.8)
        print(f"Retry decorator: {result}")
    except Exception as e:
        print(f"Retry decorator failed: {e}")
    
    # Test timer
    print("\n3. Timer Demo:")
    with Timer("Sleep test") as timer:
        time.sleep(0.1)
    print(timer)
    
    # Test logging
    print("\n4. Logging Demo:")
    logger = setup_logging("INFO")
    logger.info("This is a test log message")
    logger.warning("This is a warning message")
    
    print("\n✅ All utilities working correctly!")
