import logging
import time
import re
from django.db import transaction
from webscraper.celery import app
from core.models import ScrapeBatch, ScrapeJob, Product, BatchInsight
from .ai import summarize_batch
from .analytics import compute_batch_stats

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException 

from .scraper import (
    init_driver, 
    _save_debug_snapshot,
    _handle_common_consent,
    extract_data
)

logger = logging.getLogger(__name__)

# NOTE: This function is likely called from inside extract_data()
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


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_ai_scrape_job(self, job_id: int, headless: bool = True):
    job = None
    driver = None
    all_items = []
    page_count = 1
    
    try:
        job = ScrapeJob.objects.select_related('batch').get(id=job_id)
        batch = job.batch
        
        # --- This is the new "brain" ---
        # We check the site to decide which strategy to use
        is_infinite_scroll = "matalanme.com" in job.site
        
        job.status = ScrapeJob.Status.RUNNING
        job.note = "Scraper agent starting..."
        job.save(update_fields=["status", "note"])
        
        try:
            driver = init_driver(headless=headless) 
            logger.info(f"📄 Loading page 1: {job.category_url}")
            driver.get(job.category_url)

            # --- Wait for ANY product to load ---
            WAIT_TIME = 20
            PRODUCT_SELECTOR = "div.product-card, div.product-wrapper, div.product-grid-item, div.productItem_product_item__OL0G5"
            try:
                logger.info(f"Waiting up to {WAIT_TIME}s for products to load...")
                WebDriverWait(driver, WAIT_TIME).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, PRODUCT_SELECTOR))
                )
                logger.info("✅ Products have loaded.")
            except TimeoutException as e:
                logger.warning(f"Wait for products failed: {e}. Trying to continue...")
                _save_debug_snapshot(driver, f"job_{job.id}_WAIT_FAILED")
            
            
            # --- MODIFICATION: Choose Strategy ---
            
            if is_infinite_scroll:
                # --- STRATEGY 2: INFINITE SCROLL (for Matalan) ---
                logger.info("Using INFINITE SCROLL strategy.")
                logger.info("Starting scroll loop...")
                last_height = driver.execute_script("return document.body.scrollHeight")
                scroll_attempts = 0 # To prevent false stops
                
                while True:
                    # 1. Check page limit
                    # (We count each scroll that loads content as a "page")
                    if job.max_pages > 0 and page_count >= job.max_pages:
                        logger.info(f"✅ Reached user-defined page limit of {job.max_pages}. Stopping.")
                        break # Exit scroll loop
                        
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    logger.info(f"Scrolling page {page_count}...")
                    time.sleep(3) # Wait for new products to load
                    
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    
                    if new_height == last_height:
                        scroll_attempts += 1
                        if scroll_attempts >= 3: # Try 3 times
                            logger.info("✅ Reached bottom of site (height did not change).")
                            break # Exit scroll loop
                    else:
                        last_height = new_height
                        scroll_attempts = 0 # Reset on success
                        page_count += 1
                
                # 2. Scrape all items at once
                logger.info("Fetching final page source...")
                page_source = driver.page_source
                _save_debug_snapshot(driver, f"job_{job.id}_final_page")
                all_items = extract_data(page_source, job.category_url)
                
            else:
                # --- STRATEGY 1: PAGINATION (for Dumyah) ---
                logger.info("Using PAGINATION strategy.")
                while True:
                    logger.info(f"--- Scraping Page {page_count} ---")
                    
                    # 1. Scroll this page to load lazy images
                    last_height = driver.execute_script("return document.body.scrollHeight")
                    for _ in range(10): # Scroll 10x max
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        new_height = driver.execute_script("return document.body.scrollHeight")
                        if new_height == last_height:
                            break
                        last_height = new_height
                    
                    # --- VULNERABILITY FIX: Wait for Rating Attributes ---
                    RATING_STYLE_SELECTOR = 'div.product-rating [style*="width:"]'
                    try:
                        # Wait up to 5 seconds for at least one rating element to load its style.
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, RATING_STYLE_SELECTOR))
                        )
                        logger.info("✅ Ratings style attributes found. Proceeding to scrape.")
                    except TimeoutException:
                        logger.warning("Timed out waiting for rating style to load (5s). Proceeding with available data.")
                    
                    # 2. Scrape the page
                    page_source = driver.page_source
                    _save_debug_snapshot(driver, f"job_{job.id}_page_{page_count}")
                    items = extract_data(page_source, job.category_url)
                    all_items.extend(items)
                    logger.info(f"Found {len(items)} items on this page. Total items: {len(all_items)}")

                    # 3. Check item limit
                    if job.max_items > 0 and len(all_items) >= job.max_items:
                        logger.info(f"✅ Reached user-defined item limit of {job.max_items}. Stopping.")
                        break

                    # 4. Find "Next" button
                    next_button_selectors = [
                        'a.pagination-next',
                        'div[onclick="handleNextPage()"]' 
                    ]
                    next_button = None
                    for selector in next_button_selectors:
                        try:
                            WebDriverWait(driver, 2).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                            next_button = driver.find_element(By.CSS_SELECTOR, selector)
                            logger.info(f"✅ Found 'Next' button ({selector}).")
                            break 
                        except (NoSuchElementException, TimeoutException):
                            continue 
                    
                    # 5. Decide whether to continue
                    if next_button:
                        if job.max_pages > 0 and page_count >= job.max_pages:
                            logger.info(f"✅ Reached user-defined page limit of {job.max_pages}. Stopping.")
                            break 
                        try:
                            next_button.click()
                            page_count += 1
                            logger.info("Clicked 'Next' page. Waiting for page to load...")
                            # NOTE: The fixed WebDriverWait for ratings partially covers the wait needed here
                            time.sleep(5) 
                        except Exception as e:
                            logger.warning(f"Could not click 'Next' button: {e}")
                            break 
                    else:
                        logger.info("✅ No 'Next' button found. Scraping complete.")
                        break
            # --- END OF STRATEGIES ---

        finally:
            if driver:
                driver.quit()
                logger.info("🔒 Local driver closed.")
        
        if not all_items:
            raise RuntimeError("No products found on any page.")

        logger.info(f"--- Total of {len(all_items)} items found from {page_count} pages ---")
        
        # Apply max_items limit
        if job.max_items > 0:
            all_items = all_items[:job.max_items] 
        
        # --- Save Products (Unchanged) ---
        bulk = []
        urls_seen = set()
        for it in all_items: 
            product_url = it.get("product_url", "") or ""
            if not it.get("title") and not product_url:
                continue
            
            if product_url and product_url in urls_seen:
                continue
            if product_url:
                urls_seen.add(product_url)
            
            bulk.append(Product(
                job=job,
                site=job.site,
                title=(it.get("title", "Untitled")[:499]),
                price=it.get("price"),
                currency=(it.get("currency", "") or "JOD").upper(),
                product_url=product_url,
                image_url=it.get("image_url", ""),
                search_query=job.category_url,
                rating=it.get("rating"), 
            ))
        
        if bulk:
            Product.objects.bulk_create(bulk, batch_size=200)
            logger.info(f"Saved {len(bulk)} new products to database.")
        else:
            logger.info("No products found or saved.")

        # --- Finalize Job (Unchanged) ---
        job.status = ScrapeJob.Status.DONE
        job.note = f"{len(bulk)} items found from {page_count} pages."
        job.save(update_fields=["status", "note"])
        
        all_products = Product.objects.filter(job__batch=batch)
        stats = compute_batch_stats(all_products)
        summary = summarize_batch(stats, batch.query, [j.site for j in batch.scrapejob_set.all()])
        
        BatchInsight.objects.update_or_create(
            batch=batch, 
            defaults={"summary": summary}
        )
        logger.info(f"Generated AI insight for batch {batch.id}")
        
        return {"ok": True, "count": len(bulk)}

    except Exception as e:
        logger.exception(f"Scrape job {job_id} failed")
        try:
            if job:
                job.status = ScrapeJob.Status.ERROR
                job.note = str(e)
                job.save(update_fields=["status", "note"])
            
            logger.warning(f"Retrying task, attempt {self.request.retries + 1}/{self.max_retries}")
            raise self.retry(exc=e)
            
        except Exception as e2:
            logger.error(f"Failed to save error or retry: {e2}")
            return {"ok": False, "error": str(e)}