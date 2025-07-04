#!/usr/bin/env python3
"""
Legal Web Spider Safety Module

Comprehensive legal compliance and security checks to ensure ethical
web crawling that respects robots.txt, avoids authentication areas,
and follows cybersecurity best practices.
"""

import re
import time
import logging
from typing import Dict, List, Optional, Set, Tuple
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse, urljoin

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

from .config import SpiderConfig
from .utils import (
    extract_domain, has_excluded_extension, SafetyViolationError,
    RobotsError, setup_logging
)


class RobotsChecker:
    """
    Handles robots.txt compliance with caching and proper error handling.
    """
    
    def __init__(self, user_agent: str = "*"):
        self.user_agent = user_agent
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.fetch_errors: Set[str] = set()
        self.logger = logging.getLogger('LegalSpider.RobotsChecker')
    
    def can_fetch(self, url: str) -> bool:
        """
        Check if URL can be fetched according to robots.txt.
        
        Args:
            url: URL to check
            
        Returns:
            True if allowed, False if disallowed
            
        Raises:
            RobotsError: If robots.txt cannot be parsed
        """
        domain = extract_domain(url)
        if not domain:
            return False
        
        # Check cache first
        if domain in self.robots_cache:
            rp = self.robots_cache[domain]
            try:
                return rp.can_fetch(self.user_agent, url)
            except Exception as e:
                self.logger.warning(f"Error checking robots.txt for {url}: {e}")
                return True  # Default to allow if check fails
        
        # Skip if we've had errors with this domain
        if domain in self.fetch_errors:
            return True  # Default to allow
        
        # Fetch and cache robots.txt
        try:
            self._fetch_robots_txt(domain)
            return self.can_fetch(url)  # Recursive call with cached data
        except Exception as e:
            self.fetch_errors.add(domain)
            self.logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
            return True  # Default to allow
    
    def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get crawl delay specified in robots.txt."""
        domain = extract_domain(url)
        if domain not in self.robots_cache:
            return None
        
        try:
            rp = self.robots_cache[domain]
            delay = rp.crawl_delay(self.user_agent)
            return float(delay) if delay else None
        except Exception:
            return None
    
    def _fetch_robots_txt(self, domain: str) -> None:
        """Fetch and parse robots.txt for domain."""
        robots_url = f"https://{domain}/robots.txt"
        
        rp = RobotFileParser()
        rp.set_url(robots_url)
        
        try:
            rp.read()
            self.robots_cache[domain] = rp
            self.logger.info(f"Successfully loaded robots.txt for {domain}")
        except Exception as e:
            self.fetch_errors.add(domain)
            raise RobotsError(f"Failed to fetch robots.txt from {robots_url}: {e}")


class AuthDetector:
    """
    Detects authentication-protected pages and sensitive areas.
    """
    
    # URL patterns that likely indicate authentication areas
    AUTH_URL_PATTERNS = [
        r'(?i).*/login.*',
        r'(?i).*/signin.*',
        r'(?i).*/logon.*',
        r'(?i).*/auth.*',
        r'(?i).*/authentication.*',
        r'(?i).*/session.*',
        r'(?i).*/logout.*',
        r'(?i).*/signout.*',
    ]
    
    # Path patterns for admin and sensitive areas
    SENSITIVE_PATH_PATTERNS = [
        r'(?i).*/admin.*',
        r'(?i).*/administrator.*',
        r'(?i).*/webadmin.*',
        r'(?i).*/siteadmin.*',
        r'(?i).*/cpanel.*',
        r'(?i).*/phpmyadmin.*',
        r'(?i).*/wp-admin.*',
        r'(?i).*/manage.*',
        r'(?i).*/control.*',
        r'(?i).*/dashboard.*',
    ]
    
    # Content patterns that indicate authentication forms
    AUTH_CONTENT_PATTERNS = [
        r'(?i)<input[^>]*type=["\']password["\']',
        r'(?i)<input[^>]*name=["\']password["\']',
        r'(?i)<input[^>]*name=["\']username["\']',
        r'(?i)<input[^>]*name=["\']email["\'].*password',
        r'(?i)<form[^>]*action=[^>]*login',
        r'(?i)<form[^>]*action=[^>]*signin',
    ]
    
    def __init__(self):
        self.logger = logging.getLogger('LegalSpider.AuthDetector')
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile regex patterns for performance."""
        self.auth_url_regex = [re.compile(pattern) for pattern in self.AUTH_URL_PATTERNS]
        self.sensitive_path_regex = [re.compile(pattern) for pattern in self.SENSITIVE_PATH_PATTERNS]
        self.auth_content_regex = [re.compile(pattern) for pattern in self.AUTH_CONTENT_PATTERNS]
    
    def is_auth_protected(self, url: str, html_content: Optional[str] = None) -> bool:
        """
        Check if URL appears to be authentication-protected.
        
        Args:
            url: URL to check
            html_content: Optional HTML content to analyze
            
        Returns:
            True if likely auth-protected, False otherwise
        """
        # Check URL patterns
        if self._check_url_patterns(url):
            return True
        
        # Check HTML content if provided
        if html_content and self._check_content_patterns(html_content):
            return True
        
        return False
    
    def _check_url_patterns(self, url: str) -> bool:
        """Check URL against authentication patterns."""
        for pattern in self.auth_url_regex + self.sensitive_path_regex:
            if pattern.search(url):
                self.logger.info(f"Auth pattern detected in URL: {url}")
                return True
        return False
    
    def _check_content_patterns(self, html_content: str) -> bool:
        """Check HTML content for authentication forms."""
        for pattern in self.auth_content_regex:
            if pattern.search(html_content):
                self.logger.info("Authentication form detected in content")
                return True
        return False
    
    def detect_forms(self, html_content: str) -> List[str]:
        """
        Detect and analyze forms in HTML content.
        
        Returns:
            List of form types detected (e.g., ['login_form', 'search_form'])
        """
        if not HAS_BS4:
            return []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            forms = soup.find_all('form')
            form_types = []
            
            for form in forms:
                # Check for password fields
                if form.find('input', {'type': 'password'}):
                    form_types.append('login_form')
                
                # Check form action
                action = form.get('action', '').lower()
                if any(word in action for word in ['login', 'signin', 'auth']):
                    form_types.append('auth_form')
                elif any(word in action for word in ['search', 'query']):
                    form_types.append('search_form')
                elif any(word in action for word in ['contact', 'feedback']):
                    form_types.append('contact_form')
                else:
                    form_types.append('generic_form')
            
            return form_types
        except Exception as e:
            self.logger.warning(f"Error analyzing forms: {e}")
            return []


class URLFilter:
    """
    Filters URLs based on safety and configuration rules.
    """
    
    def __init__(self, config: SpiderConfig):
        self.config = config
        self.logger = logging.getLogger('LegalSpider.URLFilter')
    
    def is_safe_url(self, url: str) -> bool:
        """
        Check if URL is safe to crawl based on all filters.
        
        Args:
            url: URL to check
            
        Returns:
            True if safe, False otherwise
        """
        try:
            # Basic URL validation
            if not url or not url.startswith(('http://', 'https://')):
                return False
            
            # Check file extensions
            if has_excluded_extension(url, self.config.excluded_extensions):
                self.logger.debug(f"Excluded extension: {url}")
                return False
            
            # Check excluded paths
            if self._has_excluded_path(url):
                self.logger.debug(f"Excluded path: {url}")
                return False
            
            # Check URL length (prevent extremely long URLs)
            if len(url) > 2048:
                self.logger.debug(f"URL too long: {url}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error filtering URL {url}: {e}")
            return False
    
    def _has_excluded_path(self, url: str) -> bool:
        """Check if URL path matches excluded patterns."""
        try:
            path = urlparse(url).path.lower()
            return any(excluded in path for excluded in self.config.excluded_paths)
        except Exception:
            return False
    
    def should_crawl(self, url: str, depth: int) -> Tuple[bool, str]:
        """
        Comprehensive check if URL should be crawled.
        
        Returns:
            Tuple of (should_crawl, reason)
        """
        # Check depth limit
        if depth > self.config.max_depth:
            return False, f"Depth limit exceeded: {depth} > {self.config.max_depth}"
        
        # Check if URL is safe
        if not self.is_safe_url(url):
            return False, "URL failed safety checks"
        
        return True, "URL approved for crawling"


class SafetyManager:
    """
    Main safety coordination class that orchestrates all safety checks.
    """
    
    def __init__(self, config: SpiderConfig):
        self.config = config
        self.robots_checker = RobotsChecker(config.user_agent) if config.respect_robots_txt else None
        self.auth_detector = AuthDetector() if config.avoid_auth_pages else None
        self.url_filter = URLFilter(config)
        self.logger = logging.getLogger('LegalSpider.SafetyManager')
        
        # Statistics
        self.stats = {
            'urls_checked': 0,
            'urls_blocked': 0,
            'robots_blocks': 0,
            'auth_blocks': 0,
            'filter_blocks': 0,
        }
    
    def pre_crawl_check(self, url: str, depth: int = 0) -> bool:
        """
        Comprehensive pre-crawl safety check.
        
        Args:
            url: URL to check
            depth: Current crawl depth
            
        Returns:
            True if safe to crawl, False otherwise
            
        Raises:
            SafetyViolationError: If safety check fails
        """
        self.stats['urls_checked'] += 1
        
        try:
            # URL filter check
            should_crawl, reason = self.url_filter.should_crawl(url, depth)
            if not should_crawl:
                self.stats['urls_blocked'] += 1
                self.stats['filter_blocks'] += 1
                self.logger.info(f"Blocked by filter: {url} - {reason}")
                return False
            
            # Robots.txt check
            if self.robots_checker and not self.robots_checker.can_fetch(url):
                self.stats['urls_blocked'] += 1
                self.stats['robots_blocks'] += 1
                self.logger.info(f"Blocked by robots.txt: {url}")
                return False
            
            # Authentication check (URL only)
            if self.auth_detector and self.auth_detector.is_auth_protected(url):
                self.stats['urls_blocked'] += 1
                self.stats['auth_blocks'] += 1
                self.logger.info(f"Blocked - auth protected: {url}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Safety check error for {url}: {e}")
            return False
    
    def post_crawl_analysis(self, url: str, html_content: str) -> Dict[str, any]:
        """
        Analyze crawled content for safety insights.
        
        Args:
            url: URL that was crawled
            html_content: HTML content retrieved
            
        Returns:
            Dictionary with analysis results
        """
        analysis = {
            'url': url,
            'timestamp': time.time(),
            'has_forms': False,
            'form_types': [],
            'auth_detected': False,
            'warnings': []
        }
        
        try:
            # Form detection
            if self.auth_detector:
                form_types = self.auth_detector.detect_forms(html_content)
                analysis['form_types'] = form_types
                analysis['has_forms'] = len(form_types) > 0
                
                # Check for auth content
                if self.auth_detector.is_auth_protected(url, html_content):
                    analysis['auth_detected'] = True
                    analysis['warnings'].append("Authentication content detected")
            
            # Content size check
            content_size = len(html_content)
            if content_size > 10 * 1024 * 1024:  # 10MB
                analysis['warnings'].append(f"Large content size: {content_size} bytes")
            
        except Exception as e:
            analysis['warnings'].append(f"Analysis error: {e}")
            self.logger.warning(f"Post-crawl analysis error for {url}: {e}")
        
        return analysis
    
    def get_robots_delay(self, url: str) -> Optional[float]:
        """Get crawl delay from robots.txt if available."""
        if self.robots_checker:
            return self.robots_checker.get_crawl_delay(url)
        return None
    
    def get_safety_stats(self) -> Dict[str, any]:
        """Get safety statistics."""
        stats = self.stats.copy()
        if stats['urls_checked'] > 0:
            stats['block_rate'] = stats['urls_blocked'] / stats['urls_checked']
        else:
            stats['block_rate'] = 0.0
        return stats


if __name__ == "__main__":
    # Demo and testing
    print("=== Legal Spider Safety Module Demo ===")
    
    from .config import SpiderConfig
    
    # Create test configuration
    config = SpiderConfig(
        start_url="https://example.com",
        respect_robots_txt=True,
        avoid_auth_pages=True,
        avoid_forms=True
    )
    
    # Initialize safety manager
    safety_manager = SafetyManager(config)
    
    # Test URLs
    test_urls = [
        "https://example.com/",
        "https://example.com/admin/",
        "https://example.com/login.php",
        "https://example.com/page.html",
        "https://example.com/document.pdf",
    ]
    
    print("\n1. Pre-crawl Safety Checks:")
    for url in test_urls:
        is_safe = safety_manager.pre_crawl_check(url)
        status = "✅ SAFE" if is_safe else "❌ BLOCKED"
        print(f"   {status}: {url}")
    
    # Test auth detection
    print("\n2. Authentication Detection:")
    auth_detector = AuthDetector()
    
    sample_html = '''
    <form action="/login" method="post">
        <input type="text" name="username">
        <input type="password" name="password">
        <input type="submit" value="Login">
    </form>
    '''
    
    if HAS_BS4:
        forms = auth_detector.detect_forms(sample_html)
        print(f"   Forms detected: {forms}")
    else:
        print("   BeautifulSoup not available - forms detection disabled")
    
    # Show statistics
    print("\n3. Safety Statistics:")
    stats = safety_manager.get_safety_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    print("\n✅ Safety module working correctly!")
