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
        logger.info(f"📸 Saved debug snapshot: {name}.png")
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
    if "aed" in t: return "AED" # <-- Added for Matalan
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
    logger.info("🚀 Initializing LOCAL Selenium driver (STEALTH Mode)...")
    
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
        
        logger.info("🤖 Applying selenium-stealth patches...")
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
        logger.error(f"❌ Failed to initialize local driver: {e}", exc_info=True)
        raise RuntimeError(f"Failed to start local Chrome: {e}") from e

def _handle_common_consent(driver):
    logger.info("🍪 Checking for consent/cookie popups...")
    logger.info(" (No consent popup found)")
    pass


# --- Parser V1 (Dumyah) ---
def extract_with_manual_parser_v1(soup, base_url, containers):
    logger.info("Using parser V1 (product-card)...")
    products = []
    logger.info(f"Found {len(containers)} product containers using 'div.product-card'")
    
    for item in containers:
        def get_text(element):
            if not element: return ""
            text = element.get_text(strip=True)
            try: return text.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError): return text
        
        title_element = item.select_one("div.product-title")
        price_element = item.select_one("span.current-price")
        img_element = item.select_one("img.product-image")
        url_element = title_element.find_parent('a') if title_element else None
        rating_element = item.select_one("span.stars-img.black-fill")
        
        title = get_text(title_element)
        price_str = get_text(price_element)
        product_url = _abs(url_element.get('href'), base_url) if url_element else ""
        image_url = _abs(img_element.get('data-src') or img_element.get('src'), base_url)
        rating_style = rating_element.get('style') if rating_element else ""
        rating = _parse_rating_from_style(rating_style)
        
        if not title and not product_url: continue
        products.append({
            "title": title, "price": _parse_price(price_str),
            "currency": _guess_currency(price_str) or "JOD",
            "product_url": product_url, "image_url": image_url,
            "rating": rating,
        })
    return products

# --- Parser V2 (Dumyah) ---
def extract_with_manual_parser_v2(soup, base_url, containers):
    logger.info("Using parser V2 (product-wrapper)...")
    products = []
    logger.info(f"Found {len(containers)} product containers using 'div.product-wrapper'")
    
    selectors = {
        "title": "div.name", "price": "div.price",
        "product_url": "div.image > a", "image_url": "img.first-image",
        "rating_span": "span.stars-img.black-fill",
    }
    
    for item in containers:
        def get_text(element):
            if not element: return ""
            text = element.get_text(strip=True)
            try: return text.encode('latin-1').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError): return text

        title_element = item.select_one(selectors["title"])
        price_element = item.select_one(selectors["price"])
        url_element = item.select_one(selectors["product_url"])
        img_element = item.select_one(selectors["image_url"])
        rating_element = item.select_one(selectors["rating_span"])

        title = get_text(title_element)
        price_str = get_text(price_element)
        product_url = _abs(url_element.get('href'), base_url) if url_element else ""
        
        image_url = ""
        if img_element:
            image_url = _abs(img_element.get('data-src') or img_element.get('src'), base_url)
        
        rating_style = rating_element.get('style') if rating_element else ""
        rating = _parse_rating_from_style(rating_style)
        
        if not title and not product_url: continue
        products.append({
            "title": title, "price": _parse_price(price_str),
            "currency": _guess_currency(price_str) or "JOD",
            "product_url": product_url, "image_url": image_url,
            "rating": rating
        })
    return products

# --- V3 Parser (for Matalan) ---
def extract_with_manual_parser_v3(soup, base_url, containers):
    """
    Parser for the "div.productItem_product_item__OL0G5" layout (e.g., Matalan).
    """
    logger.info("Using parser V3 (productItem)...")
    products = []
    logger.info(f"Found {len(containers)} product containers")
    
    for item in containers:
        def get_text(element):
            return element.get_text(strip=True) if element else ""

        # Selectors based on the new HTML
        url_element = item.select_one("a")
        title_element = item.select_one("h4.productItem_product_name__tj_VU")
        price_element = item.select_one("span.product_price")
        img_element = item.select_one("figure.productItem_img_container__usjWD img")

        title = get_text(title_element)
        price_str = get_text(price_element)
        product_url = _abs(url_element.get('href'), base_url) if url_element else ""
        
        image_url = ""
        if img_element:
            # This site uses 'srcset', let's grab the 'src' fallback
            image_url = _abs(img_element.get('src'), base_url)
        
        if not title and not product_url:
            continue
            
        products.append({
            "title": title,
            "price": _parse_price(price_str),
            "currency": _guess_currency(price_str) or "AED",
            "product_url": product_url,
            "image_url": image_url,
        })
    return products


# --- Master extract_data function ---
def extract_data(html_content, base_url):
    """
    Master function to analyze HTML and choose the correct parser.
    """
    logger.info("⚡ Detecting page layout...")
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check which layout is dominant
        v1_cards = soup.select("div.product-card")
        v2_cards = soup.select("div.product-wrapper")
        v3_cards = soup.select("div.productItem_product_item__OL0G5") 
        
        if len(v1_cards) > len(v2_cards) and len(v1_cards) > len(v3_cards):
            return extract_with_manual_parser_v1(soup, base_url, v1_cards)
        elif len(v2_cards) > len(v1_cards) and len(v2_cards) > len(v3_cards):
            return extract_with_manual_parser_v2(soup, base_url, v2_cards)
        elif len(v3_cards) > 0:
            return extract_with_manual_parser_v3(soup, base_url, v3_cards)
        else:
            logger.warning("No known product containers found. 0 products.")
            return []
            
    except Exception as e:
        logger.error(f"❌ BeautifulSoup extraction failed: {e}", exc_info=True)
        return []