#!/usr/bin/env python3
"""
Legal Web Spider Configuration Module

Centralized configuration management with validation, environment variable support,
and cybersecurity-focused defaults that ensure legal and ethical web crawling.
"""

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse


@dataclass
class SpiderConfig:
    """
    Comprehensive configuration for legal web spider operations.
    
    All settings default to safe, legal, and ethical values that respect
    server resources and comply with common web crawling best practices.
    """
    
    # === TARGET SETTINGS ===
    start_url: str = ""
    max_depth: int = 2
    max_pages: int = 100
    
    # === HTTP SETTINGS ===
    user_agent: str = "LegalSpider/1.0 (+https://github.com/legal-spider/info)"
    timeout_connect: float = 5.0
    timeout_read: float = 30.0
    max_retries: int = 3
    
    # === RATE LIMITING (Conservative defaults) ===
    delay_min: float = 1.0
    delay_max: float = 2.0
    requests_per_second: float = 1.0  # Very conservative
    max_concurrent_requests: int = 1  # Single-threaded by default
    
    # === SAFETY SETTINGS (Legal compliance) ===
    respect_robots_txt: bool = True
    avoid_auth_pages: bool = True
    avoid_forms: bool = True
    skip_sensitive_paths: bool = True
    
    # === URL FILTERING ===
    excluded_extensions: List[str] = field(default_factory=lambda: [
        '.pdf', '.zip', '.rar', '.tar', '.gz', '.exe', '.dmg', '.iso',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico',
        '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv',
        '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
    ])
    
    excluded_paths: List[str] = field(default_factory=lambda: [
        '/admin/', '/administrator/', '/webadmin/', '/siteadmin/',
        '/cpanel/', '/phpmyadmin/', '/wp-admin/', '/login/',
        '/auth/', '/authentication/', '/signin/', '/signup/',
        '/register/', '/account/', '/user/', '/member/',
        '/logout/', '/logoff/', '/delete/', '/remove/',
        '/api/', '/webhook/', '/callback/'
    ])
    
    # === OUTPUT SETTINGS ===
    output_file: Optional[str] = None
    output_format: str = "json"  # json, csv, txt
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # === DOCKER/ENVIRONMENT SETTINGS ===
    config_file: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'SpiderConfig':
        """
        Create configuration from environment variables.
        Perfect for Docker containers and CI/CD pipelines.
        """
        return cls(
            # Target settings
            start_url=os.getenv('SPIDER_START_URL', ''),
            max_depth=int(os.getenv('SPIDER_MAX_DEPTH', '2')),
            max_pages=int(os.getenv('SPIDER_MAX_PAGES', '100')),
            
            # HTTP settings
            user_agent=os.getenv('SPIDER_USER_AGENT', 'LegalSpider/1.0 (+https://github.com/legal-spider/info)'),
            timeout_connect=float(os.getenv('SPIDER_TIMEOUT_CONNECT', '5.0')),
            timeout_read=float(os.getenv('SPIDER_TIMEOUT_READ', '30.0')),
            max_retries=int(os.getenv('SPIDER_MAX_RETRIES', '3')),
            
            # Rate limiting
            delay_min=float(os.getenv('SPIDER_DELAY_MIN', '1.0')),
            delay_max=float(os.getenv('SPIDER_DELAY_MAX', '2.0')),
            requests_per_second=float(os.getenv('SPIDER_REQUESTS_PER_SECOND', '1.0')),
            
            # Safety settings
            respect_robots_txt=os.getenv('SPIDER_RESPECT_ROBOTS', 'true').lower() == 'true',
            avoid_auth_pages=os.getenv('SPIDER_AVOID_AUTH', 'true').lower() == 'true',
            avoid_forms=os.getenv('SPIDER_AVOID_FORMS', 'true').lower() == 'true',
            
            # Output settings
            output_file=os.getenv('SPIDER_OUTPUT_FILE'),
            output_format=os.getenv('SPIDER_OUTPUT_FORMAT', 'json'),
            log_level=os.getenv('SPIDER_LOG_LEVEL', 'INFO'),
            log_file=os.getenv('SPIDER_LOG_FILE'),
        )
    
    @classmethod
    def from_file(cls, config_path: str) -> 'SpiderConfig':
        """
        Load configuration from JSON file.
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Create instance with loaded data
            config = cls()
            for key, value in config_data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
            
            return config
            
        except FileNotFoundError:
            raise ConfigValidationError(f"Configuration file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ConfigValidationError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigValidationError(f"Error loading config file: {e}")
    
    def validate(self) -> None:
        """
        Validate configuration values and raise detailed errors.
        """
        errors = []
        
        # Validate start_url
        if not self.start_url:
            errors.append("start_url is required")
        elif not self._is_valid_url(self.start_url):
            errors.append(f"start_url is not a valid URL: {self.start_url}")
        
        # Validate numeric ranges
        if self.max_depth < 0:
            errors.append("max_depth must be >= 0")
        if self.max_depth > 10:
            errors.append("max_depth > 10 is not recommended (too deep)")
            
        if self.max_pages < 1:
            errors.append("max_pages must be >= 1")
        if self.max_pages > 10000:
            errors.append("max_pages > 10000 may cause performance issues")
        
        # Validate timeouts
        if self.timeout_connect <= 0:
            errors.append("timeout_connect must be > 0")
        if self.timeout_read <= 0:
            errors.append("timeout_read must be > 0")
        if self.timeout_connect > 60:
            errors.append("timeout_connect > 60 seconds is not recommended")
        
        # Validate rate limiting
        if self.requests_per_second <= 0:
            errors.append("requests_per_second must be > 0")
        if self.requests_per_second > 10:
            errors.append("requests_per_second > 10 may overwhelm servers")
        
        if self.delay_min < 0:
            errors.append("delay_min must be >= 0")
        if self.delay_max < self.delay_min:
            errors.append("delay_max must be >= delay_min")
        
        # Validate output format
        valid_formats = ['json', 'csv', 'txt']
        if self.output_format not in valid_formats:
            errors.append(f"output_format must be one of: {valid_formats}")
        
        # Validate log level
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level not in valid_levels:
            errors.append(f"log_level must be one of: {valid_levels}")
        
        # Safety warnings (not errors, but important)
        warnings = []
        if not self.respect_robots_txt:
            warnings.append("respect_robots_txt=False may violate website policies")
        if not self.avoid_auth_pages:
            warnings.append("avoid_auth_pages=False may attempt to access protected areas")
        if self.requests_per_second > 5:
            warnings.append(f"requests_per_second={self.requests_per_second} is aggressive")
        
        # Raise errors if any
        if errors:
            raise ConfigValidationError(f"Configuration errors: {'; '.join(errors)}")
        
        # Log warnings
        if warnings:
            print(f"Configuration warnings: {'; '.join(warnings)}")
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and has required components."""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def get_domain(self) -> str:
        """Extract domain from start_url."""
        return urlparse(self.start_url).netloc
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            'start_url': self.start_url,
            'max_depth': self.max_depth,
            'max_pages': self.max_pages,
            'user_agent': self.user_agent,
            'timeout_connect': self.timeout_connect,
            'timeout_read': self.timeout_read,
            'max_retries': self.max_retries,
            'delay_min': self.delay_min,
            'delay_max': self.delay_max,
            'requests_per_second': self.requests_per_second,
            'respect_robots_txt': self.respect_robots_txt,
            'avoid_auth_pages': self.avoid_auth_pages,
            'avoid_forms': self.avoid_forms,
            'excluded_extensions': self.excluded_extensions,
            'excluded_paths': self.excluded_paths,
            'output_file': self.output_file,
            'output_format': self.output_format,
            'log_level': self.log_level,
        }
    
    def save_to_file(self, file_path: str) -> None:
        """Save configuration to JSON file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


# === CONVENIENCE FUNCTIONS ===

def load_config(config_file: Optional[str] = None) -> SpiderConfig:
    """
    Load configuration with fallback priority:
    1. Specified config file
    2. Environment variables
    3. Default values
    """
    if config_file and os.path.exists(config_file):
        config = SpiderConfig.from_file(config_file)
    else:
        config = SpiderConfig.from_env()
    
    config.validate()
    return config


def create_example_config(file_path: str = "spider_config.json") -> None:
    """Create an example configuration file."""
    example_config = SpiderConfig(
        start_url="https://example.com",
        max_depth=2,
        max_pages=50,
        requests_per_second=2.0,
        output_file="spider_results.json"
    )
    example_config.save_to_file(file_path)
    print(f"Example configuration saved to: {file_path}")


if __name__ == "__main__":
    # Demo and testing
    print("=== Legal Spider Configuration Demo ===")
    
    # Create example config
    create_example_config()
    
    # Test environment loading
    print("\n1. Testing environment variable loading...")
    os.environ['SPIDER_START_URL'] = 'https://example.com'
    os.environ['SPIDER_MAX_PAGES'] = '25'
    
    config = SpiderConfig.from_env()
    print(f"Loaded from env: {config.start_url} (max_pages: {config.max_pages})")
    
    # Test validation
    print("\n2. Testing validation...")
    try:
        config.validate()
        print("✅ Configuration is valid")
    except ConfigValidationError as e:
        print(f"❌ Configuration error: {e}")
    
    # Show safety defaults
    print(f"\n3. Safety settings:")
    print(f"   Respect robots.txt: {config.respect_robots_txt}")
    print(f"   Avoid auth pages: {config.avoid_auth_pages}")
    print(f"   Rate limit: {config.requests_per_second} req/sec")
    print(f"   Excluded paths: {len(config.excluded_paths)} patterns")
