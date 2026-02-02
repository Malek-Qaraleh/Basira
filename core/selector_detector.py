import asyncio
import json
import re
import logging
import os
from typing import Dict, Optional, List
from urllib.parse import urlparse
import random
from pathlib import Path
from bs4 import BeautifulSoup
import urllib.robotparser
from django.conf import settings

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    async_playwright = None

logger = logging.getLogger(__name__)

class AISelelectorDetector:
    def __init__(self, api_key=None):
        from google import genai as _genai_new
        self.client = None
        self.model_name = 'gemini-2.5-flash'
        key = api_key or os.getenv('GOOGLE_API_KEY')
        if key and _genai_new:
            try:
                self.client = _genai_new.Client(api_key=key)
            except Exception:
                self.client = None
        self.selector_cache = {}

    def _is_garbage_title(self, text: str) -> bool:
        """Filters out non-title text like delivery badges or months."""
        if not text: return True
        garbage_patterns = [
            r'delivery', r'within \d+', r'hours', r'shipping', 
            r'jod', r'out of stock', r'add to cart', r'save \d+', 
            r'view product', r'sunday', r'monday', r'tuesday', r'wednesday',
            r'thursday', r'friday', r'saturday', r'january', r'february'
        ]
        text_lower = text.lower().strip()
        if len(text_lower) < 4: return True
        return any(re.search(p, text_lower) for p in garbage_patterns)

    async def get_selectors_from_gemini(self, html: str, url: str) -> Dict:
        domain = urlparse(url).netloc
        if domain in self.selector_cache:
            return self.selector_cache[domain]
        
        soup = BeautifulSoup(html, 'html.parser')
        for s in soup(['script', 'style', 'svg', 'path', 'footer', 'nav', 'header']):
            s.decompose()
        clean_html = soup.prettify()[:40000]

        prompt = f"Return ONLY a JSON object with CSS selectors for product_container, title, price, image, and product_url for e-commerce page {url}. HTML: {clean_html}"
        
        try:
            if self.client:
                resp = self.client.models.generate_content(model=self.model_name, contents=prompt)
                json_match = re.search(r'\{.*\}', resp.text, re.DOTALL)
                if json_match:
                    selectors = json.loads(json_match.group())
                    self.selector_cache[domain] = selectors
                    return selectors
        except Exception as e:
            logger.error(f"Gemini API Error: {e}")
        
        return {"product_container": ".product-item, .product-card, .item", "confidence": "low"}

    def extract_with_selectors(self, html: str, selectors: Dict, page_url: str, fields: List[str] = None) -> List[Dict]:
        products = []
        soup = BeautifulSoup(html, 'html.parser')
        
        allowed = [f.replace('image_url', 'image') for f in (fields or ['title', 'price', 'image', 'product_url'])]
        
        container_sel = selectors.get('product_container', '.product-item')
        containers = soup.select(container_sel)
        
        if len(containers) < 2:
            for fb in ['.product-item', '.product-card', '.item', 'li.item', 'article']:
                containers = soup.select(fb)
                if len(containers) >= 2: break

        for container in containers:
            try:
                item = {}
                if 'title' in allowed:
                    title = None
                    if selectors.get('title'):
                        el = container.select_one(selectors.get('title'))
                        if el and not self._is_garbage_title(el.get_text()):
                            title = el.get_text(strip=True)
                    if not title:
                        for link in container.find_all('a'):
                            txt = link.get_text(strip=True)
                            if txt and len(txt) > 8 and not self._is_garbage_title(txt):
                                title = txt
                                break
                    item['title'] = title

                if 'price' in allowed:
                    price_el = container.select_one(".price, [class*='price'], .amount, b")
                    item['price'] = price_el.get_text(strip=True) if price_el else None

                if 'image' in allowed:
                    img_el = container.select_one("img")
                    item['image'] = img_el.get('data-src') or img_el.get('src') if img_el else None

                url_el = container.select_one("a[href]")
                href = url_el.get('href') if url_el else ""
                item['product_url'] = self._fix_url(href, page_url)

                if item.get('title') or item.get('product_url'):
                    products.append(item)
            except: continue
        return products

    def _fix_url(self, href, base):
        if not href or href.startswith('http'): return href
        p = urlparse(base)
        return f"{p.scheme}://{p.netloc}/{href.lstrip('/')}"

class PlaywrightScraper:
    def __init__(self, api_key=None):
        self.detector = AISelelectorDetector(api_key=api_key)
        self.user_data_dir_base = Path.cwd() / "user_data"
        self.user_agent = "MyEcommerceBot/1.0"
        
        self.excluded_sites = [
            "dumyah.com",
            "matalan.me",
            "zain.jo",
            "eshop.jo.zain.com" 
        ]

    def can_scrape(self, url: str) -> bool:
        if not getattr(settings, 'SAFE_SCRAPING_ENFORCED', True):
            logger.info("Global robots.txt enforcement is DISABLED. Proceeding...")
            return True

        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if any(site in domain for site in self.excluded_sites):
            logger.info(f" robots.txt checked for trusted site: {domain}")
            return True

        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        
        try:
            logger.info(f"Checking robots.txt for: {domain}...")
            rp.set_url(robots_url)
            rp.read() 
            allowed = rp.can_fetch(self.user_agent, url)
            if not allowed:
                logger.warning(f" Robots.txt policy explicitly DISALLOWS scraping {url}")
            return allowed
        except Exception as e:
            logger.warning(f" Could not access robots.txt for {domain} ({e}). Defaulting to ALLOWED.")
            return True

    async def scrape(self, url: str, pagination_type: str = 'auto', max_pages: int = 1, max_items: int = 0, fields: List[str] = None) -> List[Dict]:
        if not self.can_scrape(url):
            logger.error(f" Scraping blocked by robots.txt policy for {url}")
            raise PermissionError("Access Denied: This website's robots.txt policy disallows automated scraping.")

        collected_products = {} 

        async with async_playwright() as p:
            domain = urlparse(url).netloc
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir_base / domain),
                headless=False,
                args=['--disable-blink-features=AutomationControlled'],
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            await page.set_extra_http_headers({"User-Agent": self.user_agent})
            
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="load", timeout=90000)
            
            current_page = 1
            while True:
                logger.info(f" Processing Page {current_page}...")
                
                try:
                    await page.wait_for_selector(".product-item, .item, .product-card", timeout=15000)
                except: 
                    logger.warning("Timed out waiting for product selectors.")

                await page.wait_for_timeout(3000)
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(1500)

                html = await page.content()
                selectors = await self.detector.get_selectors_from_gemini(html, page.url)
                batch = self.detector.extract_with_selectors(html, selectors, page.url, fields)
                
                for item in batch:
                    p_url = item.get('product_url')
                    if p_url and p_url not in collected_products:
                        collected_products[p_url] = item

                logger.info(f" Batch: {len(batch)} | Total unique: {len(collected_products)}")

                if (max_items > 0 and len(collected_products) >= max_items) or current_page >= max_pages:
                    break

                # Handle Targeted Pagination using .pagination-next from your inspector
                next_btn = await page.query_selector(".pagination-next")

                if next_btn and await next_btn.is_visible():
                    old_url = page.url
                    # Explicitly evaluate the BEFORE state inside the browser
                    first_item_before = await page.evaluate(
                        "() => document.querySelector('.product-item a, .item a, .product-card a')?.href"
                    )

                    await next_btn.scroll_into_view_if_needed()
                    await page.wait_for_timeout(1500)
                    
                    # Direct JS click to bypass potential overlays
                    await next_btn.evaluate("el => el.click()")
                    logger.info(f"Clicked Next. Waiting for content refresh (Page {current_page} -> {current_page + 1})")
                    
                    try:
                        # Monitor DOM state: wait for the first product link to NOT equal the old one
                        await page.wait_for_function(
                            """(oldItem) => {
                                const firstProd = document.querySelector('.product-item a, .item a, .product-card a');
                                const currentFirstUrl = firstProd ? firstProd.href : null;
                                return currentFirstUrl !== oldItem;
                            }""", 
                            first_item_before, 
                            timeout=20000 
                        )
                        # Settle time for AJAX hydration
                        await page.wait_for_timeout(4000)
                        await page.wait_for_load_state("networkidle")
                    except Exception:
                        if page.url != old_url:
                            logger.info("URL changed but content signature remained static. Continuing.")
                        else:
                            logger.warning("No URL or content change detected after 20s. Breaking pagination.")
                            break
                    current_page += 1
                else:
                    logger.info("No visible 'Next' button found.")
                    break

            await context.close()
            final_data = list(collected_products.values())
            return final_data[:max_items] if max_items > 0 else final_data

def scrape_sync(url, api_key, pagination_type='auto', max_pages=1, max_items=0, fields=None):
    async def _run():
        s = PlaywrightScraper(api_key=api_key)
        return await s.scrape(url, pagination_type, max_pages, max_items, fields)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try: return loop.run_until_complete(_run())
    finally: loop.close()