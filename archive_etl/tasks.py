import logging
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from webscraper.celery import app
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from django.utils import timezone

from .models import ResearchRequest, Article, ScrapeSource
from .ai import perform_thematic_analysis
from .utils import check_url_compliance

# Reuse BOTH init_driver and _save_debug_snapshot from core scraper
from core.scraper import init_driver, _save_debug_snapshot

logger = logging.getLogger(__name__)

@app.task(bind=True)
def run_research_pipeline(self, request_id):
    req = ResearchRequest.objects.get(id=request_id)
    req.status = ResearchRequest.Status.RUNNING
    req.save()
    
    driver = None
    try:
        logger.info(f"Starting research pipeline for: {req.topic}")
        driver = init_driver(headless=True)
        
        logger.info(f"Navigating to target: {req.target_url}")
        driver.get(req.target_url)
        time.sleep(5)

        # --- HANDLER: Interactive Search (Plan B) ---
        if "AdvancedSearch" in driver.current_url and req.topic:
            try:
                input_selectors = ["input[name='txtSearch']", "input#txtSearch", "input[name='q']", "input.search-input", "input[type='text']"]
                search_input = None
                for sel in input_selectors:
                    try:
                        search_input = driver.find_element(By.CSS_SELECTOR, sel)
                        if search_input.is_displayed(): break
                    except: continue
                
                if search_input:
                    logger.info(f"Found search box. Typing: '{req.topic}'")
                    search_input.clear()
                    search_input.send_keys(req.topic)
                    search_input.send_keys(Keys.RETURN)
                    time.sleep(5)
                    logger.info(f"Search submitted. New URL: {driver.current_url}")
            except Exception as e:
                logger.warning(f"Could not interact with search form: {e}")
            
        # --- STEP 1: Extract Article Links ---
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        # Remove specific sidebars or "Most Read" sections to avoid unrelated links
        for unwanted in soup.select('.col-md-3, .sidebar, .most-read, .trending, footer, nav'):
            unwanted.decompose()
            
        article_links = set()
        
        target_selectors = [
            # Generic Headings
            'h1 a', 'h2 a', 'h3 a', 'h4 a',   
            
            # Ammon News English Specifics
            'a.nav-link.fw-bolder', 
            '.news-category-element a', 
            
            # Standard News Site Patterns
            '.news-item a', 'article a',      
            '.search-result a', '.search-item a',
            '.news-list a', '.media-body a', 
            '.entry-title a', 'div.col-md-8 a' 
        ]
        
        for selector in target_selectors:
            for a in soup.select(selector):
                href = a.get('href')
                if href and len(href) > 15: 
                    if href.startswith('/'):
                        href = urljoin(req.target_url, href)
                    
                    # --- STRICT FILTERING FOR AMMON NEWS ---
                    if 'ammonnews.net' in href:
                        if '/article/' not in href:
                            continue # Skip non-article pages
                    
                    # General filters
                    if 'search' not in href and 'contact' not in href and 'login' not in href:
                        article_links.add(href)
        
        logger.info(f"Found {len(article_links)} potential article links.")

        # --- STEP 2: Identify Source ---
        source_obj = None
        all_sources = ScrapeSource.objects.all()
        for source in all_sources:
            clean_domain = source.base_url.replace('https://', '').replace('http://', '').rstrip('/')
            if clean_domain in req.target_url:
                source_obj = source
                break
        
        # --- STEP 3: Scrape Individual Articles ---
        scraped_count = 0
        articles_for_ai = []

        # Apply User Limit
        limit = req.max_articles if req.max_articles > 0 else 10
        logger.info(f"User requested limit: {limit} articles.")
        links_to_scrape = list(article_links)[:limit]

        for i, url in enumerate(links_to_scrape): 
            if not check_url_compliance(url, source_obj.name if source_obj else "Unknown"):
                continue
            
            try:
                logger.info(f"Scraping ({i+1}/{len(links_to_scrape)}): {url}")
                driver.get(url)
                time.sleep(2)
                
                art_soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # 1. Clean Junk
                for junk in art_soup.select('nav, footer, header, .related, .share, .hidden, script, style'):
                    junk.decompose()

                # 2. Extract Title (Updated Selectors)
                title = "No Title"
                title_selectors = [
                    '.story-title', '.news-title', 
                    'h1.entry-title', 'h1.post-title', 
                    'h1.article-title', 'div.news-title h1', 'h1'
                ]
                for t_sel in title_selectors:
                    element = art_soup.select_one(t_sel)
                    if element and element.get_text(strip=True):
                        title = element.get_text(strip=True)
                        break
                
                if title == "No Title" and driver.title:
                    # Clean up common suffixes like " - Jordan News" or "Ammon News -"
                    clean_title = driver.title.split(' - ')[0] 
                    clean_title = clean_title.replace('Ammon News', '').strip()
                    
                    if len(clean_title) > 5:
                        title = clean_title
                        logger.info(f"   -> Recovered title from metadata: {title[:30]}...")
                
                # 3. Extract Text (Priority + Fallback)
                text_content = ""
                # Priority 1: Specific content containers
                body_container = art_soup.select_one(
                    '.story-body, #storyText, .news-body, .entry-content, div.content-area, .post-content'
                )
                
                if body_container:
                    text_content = body_container.get_text(separator="\n\n", strip=True)
                else:
                    # Priority 2: Fallback - Find the DIV with the most text
                    longest_div = None
                    max_len = 0
                    for div in art_soup.find_all('div'):
                        text = div.get_text(strip=True)
                        # Heuristic: lots of text, few links
                        if len(text) > max_len and len(div.find_all('a')) < 5:
                            max_len = len(text)
                            longest_div = div
                    
                    if longest_div and max_len > 200:
                        text_content = longest_div.get_text(separator="\n\n", strip=True)

                # 4. Save Data
                if text_content and len(text_content) > 100:
                    article, created = Article.objects.update_or_create(
                        url=url,
                        defaults={
                            'request': req,
                            'source': source_obj,
                            'title': title[:499],
                            'clean_text': text_content,
                            'scraped_at': timezone.now()
                        }
                    )
                    articles_for_ai.append(article)
                    scraped_count += 1
                    action_msg = "Created" if created else "Updated"
                    logger.info(f"   -> {action_msg} article: {title[:30]}...")
                else:
                    logger.warning(f"   -> Skipped (Text too short)")

            except Exception as e:
                logger.warning(f"Failed to scrape article {url}: {e}")
        logger.info(f"Successfully processed {scraped_count} articles.")

        # --- STEP 4: AI Analysis ---
        if scraped_count > 0:
            logger.info("Running AI Thematic Analysis...")
            analysis = perform_thematic_analysis(req.topic, articles_for_ai)
            req.thematic_analysis = analysis
        else:
            req.thematic_analysis = f"No articles scraped. (Found {len(article_links)} links)."

        req.status = ResearchRequest.Status.COMPLETED
        req.save()
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        req.status = ResearchRequest.Status.FAILED
        req.save()
        
    finally:
        if driver:
            driver.quit()
            logger.info("Driver closed.")