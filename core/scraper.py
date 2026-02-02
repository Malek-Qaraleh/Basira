import logging
import os
import time
import json
import re
from urllib.parse import urljoin
from django.conf import settings
from selenium import webdriver
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium_stealth import stealth

# --- Setup, Snapshot, and Helpers ---
logger = logging.getLogger(__name__)

DEBUG_SNAPSHOTS = True
SNAP_DIR = os.path.abspath("snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)

def _save_debug_snapshot(driver, name: str):
    if not DEBUG_SNAPSHOTS:
        return
    try:
        html_path = os.path.join(SNAP_DIR, f"{name}.html")
        png_path = os.path.join(SNAP_DIR, f"{name}.png")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        driver.save_screenshot(png_path)
        logger.info(f"Saved debug snapshot: {name}.png")
    except Exception as e:
        logger.warning(f"Failed to save debug snapshot: {e}")

def _abs(url, base):
    if not url: return ""
    if url.startswith("http"): return url
    if url.startswith("//"): return "http:" + url
    return urljoin(base, url)

def _parse_price(txt):
    if not txt: return None
    digits = "".join(ch for ch in txt if ch.isdigit() or ch in ".")
    try:
        return float(digits) if digits else None
    except (ValueError, TypeError):
        return None

def _guess_currency(txt):
    if not txt: return ""
    t = txt.lower()
    if "sar" in t or "﷼" in t: return "SAR"
    if "jod" in t or "jd" in t: return "JOD"
    if "aed" in t: return "AED"
    if "$" in t: return "USD"
    if "€" in t: return "EUR"
    if "£" in t: return "GBP"
    return ""

def _parse_rating_from_style(style_str):
    """Extracts '100' from 'width: 100%;' and converts to 5.0"""
    if not style_str:
        return None
    match = re.search(r'width:\s*([\d\.]+)%', style_str)
    if not match:
        return None
    try:
        percentage = float(match.group(1))
        # 100% width = 5 stars, 80% = 4 stars, etc.
        return round((percentage / 100) * 5, 1) 
    except Exception:
        return None

def _parse_review_count(txt):
    """Extracts '2' from '(2)'"""
    if not txt: return None
    digits = "".join(ch for ch in txt if ch.isdigit())
    try:
        return int(digits) if digits else None
    except (ValueError, TypeError):
        return None

def init_driver(headless=True):
    logger.info("Initializing LOCAL Selenium driver (STEALTH Mode)...")
    
    chrome_options = webdriver.ChromeOptions()
    if headless:
          chrome_options.add_argument("--headless=new")
    
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--lang=en-US")
    
    logger.info("Disabling image loading to save resources...")
    chrome_options.add_argument("--disable-images")
    chrome_options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
        "intl.accept_languages": "en,en_US"
    })
    
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        s = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=s, options=chrome_options)
        
        logger.info("Applying selenium-stealth patches...")
        stealth(driver,
              languages=["en-US", "en"],
              vendor="Google Inc.",
              platform="Win32",
              webgl_vendor="Intel Inc.",
              renderer="Intel Iris OpenGL Engine",
              fix_hairline=True,
              )
        
        driver.set_page_load_timeout(120) 
        driver.implicitly_wait(10)
        logger.info("✓ Local stealth driver initialized successfully.")
        return driver
    except Exception as e:
        logger.error(f" Failed to initialize local driver: {e}", exc_info=True)
        raise RuntimeError(f"Failed to start local Chrome: {e}") from e

def _handle_common_consent(driver):
    logger.info("Checking for consent/cookie popups...")
    logger.info(" (No consent popup found)")
    pass

def validate_title(title):
    """Ensure the title is not empty or a placeholder."""
    if not title or title.lower() in ["title", "placeholder"]:
        return None
    return title

def validate_url(url, base):
    """Ensure the URL is absolute and valid."""
    abs_url = _abs(url, base)
    if not abs_url or not abs_url.startswith("http"):
        return None
    return abs_url

def deduplicate_data(data):
    """Remove duplicate entries based on unique URLs."""
    seen = set()
    unique_data = []
    for entry in data:
        url = entry.get("url")
        if url not in seen:
            seen.add(url)
            unique_data.append(entry)
    return unique_data

# Example usage in scraping logic
def scrape_page(driver, base_url):
    """Scrape a single page and return structured data."""
    soup = BeautifulSoup(driver.page_source, "html.parser")
    items = []

    for element in soup.select(".item-selector"):  # Replace with actual selector
        title = validate_title(element.select_one(".title-selector").get_text(strip=True))
        url = validate_url(element.select_one("a")["href"], base_url)

        if title and url:
            items.append({"title": title, "url": url})

    # Deduplicate before returning
    return deduplicate_data(items)
