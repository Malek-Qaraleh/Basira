import logging
from urllib.parse import urljoin, urlparse
import requests
import time

logger = logging.getLogger(__name__)

def check_url_compliance(url: str, source_name: str) -> bool:
    """
    Checks if a URL violates the robots.txt restrictions for known sources.
    This is the critical step for compliance with the Ammon News rules.
    """
    # 1. Generic compliance check (always necessary)
    if not url or not url.startswith('http'):
        return False
    
    # 2. Specific checks based on the Source
    if source_name and 'Ammon News' in source_name:
        # Ammon News requires skipping index.php, admin/, core/, etc.
        disallowed_keywords = ['index.php', 'admin', 'demo', 'core', 'v1', 'v2', 'backup_admin', 'print']
        
        parsed_path = urlparse(url).path.lower()
        if any(keyword in parsed_path for keyword in disallowed_keywords):
            logger.warning(f"Compliance Check: Skipping URL due to Ammon News Disallow rule: {url}")
            return False
            
    return True

def fetch_article_html(url: str) -> str | None:
    """
    Fetches the raw HTML content of a single article URL using requests.
    We use requests here because news articles are mostly static (pre-rendered).
    """
    try:
        # Use the same honest User-Agent
        headers = {'User-Agent': 'Basira Research Archive Bot'}
        
        # Apply politeness delay
        time.sleep(2) 

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status() 

        # We will return the text content for processing later
        return response.text

    except requests.exceptions.RequestException as e:
        logger.warning(f"Skipping article {url} due to request error: {e}")
        return None