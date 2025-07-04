# Complete Spider Code Explanation and Function Guide

## Annotated Source Code

```python
#!/usr/bin/env python3
"""
Simple Website Spider - Core Functions Only

This script crawls a website recursively to map all internal links.
It respects a maximum depth limit and includes basic politeness delays.
"""

# ==============================================================================
# IMPORTS - External libraries needed for web scraping
# ==============================================================================

import requests          # HTTP library for making web requests
from bs4 import BeautifulSoup  # HTML parsing library
from urllib.parse import urljoin, urlparse  # URL manipulation utilities
import time             # Time utilities for delays

# ==============================================================================
# GLOBAL CONFIGURATION
# ==============================================================================

# Target website - change this URL to scan a different site
# Must include http:// or https:// protocol
TARGET_URL = "https://example.com"

# Global data structures to track crawling progress
visited = set()         # Set of URLs already crawled (prevents infinite loops)
internal_links = {}     # Dictionary mapping each page to its discovered links

# ==============================================================================
# CORE FUNCTIONS
# ==============================================================================

def is_internal(url):
    """
    Check if URL belongs to target domain
    
    Args:
        url (str): The URL to check
        
    Returns:
        bool: True if URL is internal to target domain, False otherwise
        
    How it works:
    1. Extract domain from TARGET_URL using urlparse()
    2. Extract domain from the given URL
    3. Compare domains - match means internal link
    4. Empty domain ('') also counts as internal (relative URLs)
    """
    target_domain = urlparse(TARGET_URL).netloc  # Get domain from target URL
    url_domain = urlparse(url).netloc            # Get domain from input URL
    
    # Return True if domains match OR if url_domain is empty (relative URL)
    return url_domain == target_domain or url_domain == ''

def get_links(url):
    """
    Extract all internal links from a page
    
    Args:
        url (str): The URL to fetch and parse
        
    Returns:
        list: List of internal URLs found on the page
        
    Process:
    1. Make HTTP GET request to the URL
    2. Check if response is successful (status 200)
    3. Parse HTML content with BeautifulSoup
    4. Find all <a> tags with href attributes
    5. Convert relative URLs to absolute URLs
    6. Filter for internal links only
    7. Return list of internal URLs
    """
    try:
        # Make HTTP request with 10-second timeout
        response = requests.get(url, timeout=10)
        
        # Only process successful responses (HTTP 200)
        if response.status_code != 200:
            return []  # Return empty list for failed requests
        
        # Parse HTML content using BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        links = []  # Initialize empty list for discovered links
        
        # Find all anchor tags (<a>) that have href attributes
        for tag in soup.find_all('a', href=True):
            # Get the href value from the tag
            href_value = tag['href']
            
            # Convert relative URLs to absolute URLs using urljoin()
            # urljoin handles cases like: "/page" -> "https://example.com/page"
            full_url = urljoin(url, href_value)
            
            # Only keep URLs that belong to our target domain
            if is_internal(full_url):
                links.append(full_url)
        
        return links  # Return list of internal links found
        
    except Exception:
        # If any error occurs (timeout, connection error, etc.)
        # return empty list instead of crashing
        return []

def spider(url, depth=0):
    """
    Recursively spider the website
    
    Args:
        url (str): The URL to crawl
        depth (int): Current crawling depth (starts at 0)
        
    Returns:
        None (modifies global variables)
        
    Crawling Logic:
    1. Check stopping conditions (max depth reached or URL already visited)
    2. Mark URL as visited to prevent infinite loops
    3. Fetch and extract links from the page
    4. Store the discovered links in global dictionary
    5. Recursively crawl each discovered link at depth+1
    6. Include politeness delay between requests
    """
    
    # STOPPING CONDITIONS - prevent infinite crawling
    if depth > 2:           # Stop if we've gone deeper than 2 levels
        return
    if url in visited:      # Stop if we've already crawled this URL
        return
    
    # Mark this URL as visited before processing
    # This prevents infinite loops in case of circular links
    visited.add(url)
    
    # Display progress to user
    print(f"[+] Crawling: {url}")
    
    # Extract all internal links from this page
    links = get_links(url)
    
    # Store the discovered links in our global mapping
    # Key: current URL, Value: list of links found on that page
    internal_links[url] = links
    
    # Recursively crawl each discovered link
    for link in links:
        # POLITENESS DELAY - be respectful to the server
        # Wait 0.5 seconds between requests to avoid overwhelming the server
        time.sleep(0.5)
        
        # Recursive call with increased depth
        spider(link, depth + 1)

def show_results():
    """
    Display the results in a formatted way
    
    Returns:
        None (prints to console)
        
    Output Format:
    - Header with title
    - For each crawled page:
      - Show the page URL
      - Show all links found on that page indented with arrows
    """
    
    # Print formatted header
    print("\n" + "="*50)  # Line of equals signs
    print("INTERNAL LINKS MAP")
    print("="*50)
    
    # Iterate through all crawled pages and their links
    for page, links in internal_links.items():
        # Print the page URL
        print(f"\n{page}")
        
        # Print each link found on this page, indented with arrow
        for link in links:
            print(f"  -> {link}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

# Run the spider only if this script is executed directly
# (not when imported as a module)
if __name__ == "__main__":
    print(f"Starting spider on: {TARGET_URL}")
    
    # Start crawling from the target URL at depth 0
    spider(TARGET_URL)
    
    # Display the results when crawling is complete
    show_results()
```

## Function Reference Guide

### Built-in Python Functions Used

#### `set()`

- **Purpose**: Creates an unordered collection of unique items
- **Usage**: `visited = set()` - prevents duplicate URL crawling
- **Why used**: Fast O(1) lookup to check if URL already visited

#### `dict()` / `{}`

- **Purpose**: Creates key-value mapping
- **Usage**: `internal_links = {}` - maps pages to their discovered links
- **Why used**: Efficient storage and retrieval of page-link relationships

#### `print()`

- **Purpose**: Display output to console
- **Usage**: `print(f"[+] Crawling: {url}")` - show progress
- **Why used**: User feedback during crawling process

#### `len()`

- **Purpose**: Get length/count of items
- **Usage**: Implicitly used in string operations
- **Why used**: String formatting and display

#### `enumerate()` / `range()`

- **Purpose**: Not directly used, but important for loops
- **Usage**: Could be used for progress tracking
- **Why used**: Iteration control

### External Library Functions

#### `requests.get(url, timeout=10)`

- **Library**: requests
- **Purpose**: Make HTTP GET request to fetch web page
- **Parameters**:
    - `url`: Target URL to fetch
    - `timeout`: Maximum seconds to wait for response
- **Returns**: Response object with status_code, text, headers
- **Why used**: Core function for downloading web pages

#### `BeautifulSoup(response.text, 'html.parser')`

- **Library**: bs4 (Beautiful Soup 4)
- **Purpose**: Parse HTML into navigable tree structure
- **Parameters**:
    - `response.text`: Raw HTML content
    - `'html.parser'`: Parser engine to use
- **Returns**: BeautifulSoup object for HTML navigation
- **Why used**: Extract links from HTML content

#### `soup.find_all('a', href=True)`

- **Library**: bs4
- **Purpose**: Find all HTML tags matching criteria
- **Parameters**:
    - `'a'`: Look for anchor tags
    - `href=True`: Only tags that have href attribute
- **Returns**: List of matching HTML tags
- **Why used**: Locate all clickable links on page

#### `urljoin(base_url, relative_url)`

- **Library**: urllib.parse
- **Purpose**: Combine base URL with relative URL to create absolute URL
- **Parameters**:
    - `base_url`: The current page URL
    - `relative_url`: Link found on page (may be relative)
- **Returns**: Complete absolute URL
- **Example**: `urljoin("https://example.com/page1", "../page2")` → `"https://example.com/page2"`
- **Why used**: Convert relative links to absolute URLs for crawling

#### `urlparse(url).netloc`

- **Library**: urllib.parse
- **Purpose**: Break URL into components and extract domain
- **Parameters**: `url` - URL to parse
- **Returns**: Domain portion of URL
- **Example**: `urlparse("https://example.com/path").netloc` → `"example.com"`
- **Why used**: Compare domains to determine if link is internal

#### `time.sleep(0.5)`

- **Library**: time
- **Purpose**: Pause execution for specified seconds
- **Parameters**: `0.5` - seconds to sleep
- **Returns**: None
- **Why used**: Politeness delay between requests to avoid overwhelming server

## Data Flow Diagram

```
1. START with TARGET_URL
   ↓
2. spider(TARGET_URL, depth=0)
   ↓
3. Check if URL already visited or depth > 2
   ↓ (if not)
4. Add URL to visited set
   ↓
5. get_links(url)
   ↓
6. requests.get() → fetch HTML
   ↓
7. BeautifulSoup() → parse HTML
   ↓
8. find_all('a') → find links
   ↓
9. urljoin() → make absolute URLs
   ↓
10. is_internal() → filter internal links
    ↓
11. Return list of internal links
    ↓
12. Store links in internal_links dict
    ↓
13. For each link: time.sleep() + spider(link, depth+1)
    ↓ (recursive)
14. show_results() → display findings
```

## Key Concepts Explained

### Recursion

- **What**: Function calls itself with modified parameters
- **Why**: Natural way to traverse tree-like website structure
- **Control**: Depth limit and visited set prevent infinite recursion

### Domain Filtering

- **What**: Only follow links within same domain
- **Why**: Prevents crawling the entire internet
- **How**: Extract and compare domain names using urlparse()

### Politeness

- **What**: Delays between requests
- **Why**: Avoid overwhelming target server
- **Implementation**: time.sleep() between each request

### Deduplication

- **What**: Track visited URLs to avoid repeats
- **Why**: Prevents infinite loops and duplicate work
- **Implementation**: Python set() for O(1) lookup performance

This spider demonstrates fundamental web crawling concepts in a simple, readable format while maintaining basic ethical crawling practices.