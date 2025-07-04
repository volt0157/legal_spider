# Modular Web Spider Architecture Guide

## Why Modularize? Current Problems vs. Solutions

### Current Monolithic Issues

- **Single file chaos** - Everything mixed together, hard to navigate
- **Tight coupling** - Changes in one area break other areas
- **Testing nightmare** - Can't unit test individual components
- **No reusability** - Can't use HTTP client in other projects
- **Scaling problems** - Can't optimize individual components
- **Team conflicts** - Multiple developers editing same file
- **Maintenance hell** - Bug fixes require understanding entire system

### Modular Benefits

- **Single Responsibility** - Each module has one clear job
- **Loose coupling** - Modules communicate through defined interfaces
- **Easy testing** - Unit test each module independently
- **Reusability** - HTTP client can be used in other projects
- **Independent scaling** - Optimize URL queue separately from HTTP client
- **Team productivity** - Different developers work on different modules
- **Maintainability** - Fix bugs in isolation without side effects

## Proposed Modular Architecture

```
spider_system/
├── core/
│   ├── __init__.py
│   ├── spider.py              # Main orchestrator
│   └── interfaces.py          # Abstract base classes
├── http/
│   ├── __init__.py
│   ├── client.py              # HTTP client with retries
│   ├── rate_limiter.py        # Token bucket, domain limits
│   └── session_manager.py     # Connection pooling
├── url_management/
│   ├── __init__.py
│   ├── queue.py               # Priority queue, deduplication
│   ├── filters.py             # URL filtering, validation
│   └── extractors.py          # Link extraction from HTML
├── safety/
│   ├── __init__.py
│   ├── robots_parser.py       # robots.txt compliance
│   ├── auth_detector.py       # Authentication detection
│   ├── form_detector.py       # Form detection and avoidance
│   └── content_analyzer.py    # Sensitive content detection
├── parsers/
│   ├── __init__.py
│   ├── html_parser.py         # BeautifulSoup wrapper
│   ├── link_extractor.py      # Extract different link types
│   └── metadata_extractor.py  # Page metadata extraction
├── storage/
│   ├── __init__.py
│   ├── results_storage.py     # Store crawl results
│   ├── cache_manager.py       # Response caching
│   └── exporters.py           # JSON, CSV, XML export
├── monitoring/
│   ├── __init__.py
│   ├── logger.py              # Structured logging
│   ├── metrics.py             # Performance metrics
│   └── health_checker.py      # System health monitoring
├── config/
│   ├── __init__.py
│   ├── settings.py            # Configuration management
│   └── validation.py          # Config validation
└── utils/
    ├── __init__.py
    ├── decorators.py          # Retry, timeout decorators
    ├── exceptions.py          # Custom exceptions
    └── helpers.py             # Utility functions
```

## Module Specifications

### 1. Core Module (`core/`)

**Purpose:** Main orchestration and interfaces

```python
# core/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

class URLQueue(ABC):
    @abstractmethod
    def add_url(self, url: str, depth: int, priority: int = 0) -> None: pass
    
    @abstractmethod
    def get_next_url(self) -> Optional['URLItem']: pass

class HTTPClient(ABC):
    @abstractmethod
    def fetch(self, url: str) -> Optional['Response']: pass

class SafetyChecker(ABC):
    @abstractmethod
    def is_safe_to_crawl(self, url: str) -> bool: pass

class ContentParser(ABC):
    @abstractmethod
    def extract_links(self, html: str, base_url: str) -> List[str]: pass

# core/spider.py
class ModularSpider:
    def __init__(self, 
                 url_queue: URLQueue,
                 http_client: HTTPClient, 
                 safety_checker: SafetyChecker,
                 content_parser: ContentParser,
                 config: SpiderConfig):
        self.url_queue = url_queue
        self.http_client = http_client
        self.safety_checker = safety_checker
        self.content_parser = content_parser
        self.config = config
```

### 2. HTTP Module (`http/`)

**Purpose:** All HTTP-related functionality

```python
# http/client.py
class HTTPClient:
    def __init__(self, rate_limiter, session_manager, config):
        self.rate_limiter = rate_limiter
        self.session_manager = session_manager
        self.config = config
    
    def fetch(self, url: str) -> Optional[Response]:
        # Wait for rate limit
        domain = urlparse(url).netloc
        self.rate_limiter.wait_for_domain(domain)
        
        # Get session for domain
        session = self.session_manager.get_session(domain)
        
        # Fetch with retries
        return self._fetch_with_retry(session, url)

# http/rate_limiter.py
class DomainRateLimiter:
    def __init__(self):
        self.domain_buckets = defaultdict(lambda: TokenBucket())
    
    def wait_for_domain(self, domain: str) -> None:
        bucket = self.domain_buckets[domain]
        while not bucket.consume():
            time.sleep(0.1)
```

### 3. URL Management (`url_management/`)

**Purpose:** URL queuing, filtering, and extraction

```python
# url_management/queue.py
class PriorityURLQueue:
    def __init__(self, deduplication_strategy='bloom_filter'):
        self.queue = []
        self.visited = BloomFilter() if deduplication_strategy == 'bloom_filter' else set()
        self.stats = {'added': 0, 'processed': 0, 'duplicates': 0}

# url_management/filters.py
class URLFilter:
    def __init__(self, config):
        self.excluded_extensions = config.excluded_extensions
        self.excluded_patterns = config.excluded_patterns
    
    def is_valid_url(self, url: str) -> bool:
        # Multiple validation checks
        return all([
            self._check_extension(url),
            self._check_patterns(url),
            self._check_length(url)
        ])
```

### 4. Safety Module (`safety/`)

**Purpose:** All safety and compliance checks

```python
# safety/robots_parser.py
class RobotsChecker:
    def __init__(self, user_agent='*'):
        self.user_agent = user_agent
        self.robots_cache = {}
    
    def can_fetch(self, url: str) -> bool:
        domain = urlparse(url).netloc
        if domain not in self.robots_cache:
            self.robots_cache[domain] = self._fetch_robots_txt(domain)
        return self.robots_cache[domain].can_fetch(self.user_agent, url)

# safety/auth_detector.py
class AuthenticationDetector:
    AUTH_PATTERNS = [...]
    SENSITIVE_PATHS = [...]
    
    def is_auth_protected(self, url: str, html_content: str = None) -> bool:
        return any([
            self._check_url_patterns(url),
            self._check_html_content(html_content) if html_content else False
        ])
```

### 5. Configuration Module (`config/`)

**Purpose:** Centralized configuration management

```python
# config/settings.py
@dataclass
class SpiderConfig:
    # HTTP Settings
    timeout_connect: float = 5.0
    timeout_read: float = 30.0
    max_retries: int = 3
    user_agent: str = "ModularSpider/1.0"
    
    # Crawling Settings
    max_depth: int = 3
    max_pages: int = 1000
    rate_limit_per_domain: float = 2.0
    
    # Safety Settings
    respect_robots_txt: bool = True
    avoid_auth_pages: bool = True
    excluded_extensions: List[str] = field(default_factory=lambda: ['.pdf', '.zip'])
    
    # Storage Settings
    output_format: str = 'json'
    output_file: Optional[str] = None
    
    @classmethod
    def from_file(cls, config_path: str) -> 'SpiderConfig':
        # Load from JSON/YAML file
        pass
    
    def validate(self) -> None:
        # Validate configuration values
        pass
```

## Module Communication Patterns

### 1. Dependency Injection Pattern

```python
# main.py - Composition root
def create_spider(config: SpiderConfig) -> ModularSpider:
    # Create all components
    rate_limiter = DomainRateLimiter(config.rate_limit_per_domain)
    session_manager = SessionManager(config.max_connections)
    http_client = HTTPClient(rate_limiter, session_manager, config)
    
    url_queue = PriorityURLQueue(config.deduplication_strategy)
    url_filter = URLFilter(config)
    
    robots_checker = RobotsChecker(config.user_agent)
    auth_detector = AuthenticationDetector()
    safety_checker = CompositeSafetyChecker([robots_checker, auth_detector])
    
    html_parser = HTMLParser()
    link_extractor = LinkExtractor(url_filter)
    content_parser = CompositeContentParser([html_parser, link_extractor])
    
    # Inject dependencies
    return ModularSpider(url_queue, http_client, safety_checker, content_parser, config)
```

### 2. Event-Driven Communication

```python
# monitoring/events.py
class SpiderEvent:
    PAGE_CRAWLED = "page_crawled"
    ERROR_OCCURRED = "error_occurred"
    RATE_LIMITED = "rate_limited"

class EventBus:
    def __init__(self):
        self.listeners = defaultdict(list)
    
    def subscribe(self, event_type: str, listener: callable):
        self.listeners[event_type].append(listener)
    
    def publish(self, event_type: str, data: dict):
        for listener in self.listeners[event_type]:
            listener(data)

# Usage in modules
event_bus.publish(SpiderEvent.PAGE_CRAWLED, {
    'url': url,
    'status_code': response.status_code,
    'timestamp': time.time()
})
```

## Testing Strategy for Modular Architecture

### 1. Unit Testing Individual Modules

```python
# tests/test_http_client.py
class TestHTTPClient:
    def test_fetch_success(self):
        # Mock dependencies
        rate_limiter = Mock()
        session_manager = Mock()
        config = SpiderConfig()
        
        client = HTTPClient(rate_limiter, session_manager, config)
        # Test specific functionality
        
    def test_retry_logic(self):
        # Test retry behavior in isolation
        pass

# tests/test_url_queue.py  
class TestURLQueue:
    def test_priority_ordering(self):
        queue = PriorityURLQueue()
        # Test queue behavior
        pass
```

### 2. Integration Testing

```python
# tests/test_integration.py
class TestSpiderIntegration:
    def test_full_crawl_workflow(self):
        # Test modules working together
        spider = create_spider(test_config)
        result = spider.crawl_single_page("http://example.com")
        assert result.success
```

## Benefits of This Modular Approach

### Development Benefits

- **Parallel Development:** Teams can work on HTTP client while others work on URL queue
- **Easier Debugging:** Issues isolated to specific modules
- **Code Reuse:** HTTP client can be used in other projects
- **Testing:** Each module can be unit tested independently

### Operational Benefits

- **Performance Tuning:** Optimize URL queue without touching HTTP client
- **Monitoring:** Module-specific metrics and health checks
- **Configuration:** Fine-grained control over each component
- **Scaling:** Different modules can have different resource requirements

### Maintenance Benefits

- **Bug Isolation:** Rate limiting bug doesn't require touching content parser
- **Feature Addition:** Add new parsers without modifying core logic
- **Dependency Management:** Each module manages its own dependencies
- **Documentation:** Each module can have focused documentation

## Implementation Roadmap

### Phase 1: Core Architecture (Week 1-2)

1. Create module structure and interfaces
2. Implement basic HTTP client module
3. Create simple URL queue module
4. Basic spider orchestrator

### Phase 2: Safety Modules (Week 3-4)

1. Robots.txt checker module
2. Authentication detector module
3. URL filter module
4. Composite safety checker

### Phase 3: Advanced Features (Week 5-6)

1. Rate limiting module
2. Content parser modules
3. Storage and export modules
4. Monitoring and logging modules

### Phase 4: Integration & Testing (Week 7-8)

1. Comprehensive integration testing
2. Performance testing of modular system
3. Documentation and examples
4. Configuration management refinement

## Migration Strategy from Current Script

### Step 1: Extract HTTP functionality

```python
# Move HTTP logic to http/client.py
# Keep same interface initially
```

### Step 2: Extract URL management

```python
# Move queue logic to url_management/queue.py
# Maintain backward compatibility
```

### Step 3: Gradual refactoring

```python
# Replace monolithic functions with module calls
# Test each migration step
```

This modular architecture transforms your spider from a simple script into a professional, maintainable, and scalable web scanning system that follows modern software engineering principles.