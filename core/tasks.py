import logging
import os
import re
import unicodedata
import time  
from urllib.parse import urljoin
from django.utils import timezone
from webscraper.celery import app

# App-specific imports
from core.models import ScrapeBatch, ScrapeJob, Product
from core.ai import summarize_batch
from core.analytics import compute_batch_stats
from core.selector_detector import scrape_sync

logger = logging.getLogger(__name__)

@app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_ai_scrape_job(self, job_id: int):
    start_time = time.time()  
    job = None
    try:
        # 1. Initialize Job
        job = ScrapeJob.objects.select_related('batch').get(id=job_id)
        job.status = ScrapeJob.Status.RUNNING
        job.note = "Initializing scraper & checking policies..."
        job.save(update_fields=["status", "note"])
        
        if job.batch:
            job.batch.save()
        
        api_key = os.getenv('GOOGLE_API_KEY')
        job_fields = getattr(job, 'fields', ['title', 'price', 'image', 'product_url'])

        # 2. Execute Scrape
        products_data = scrape_sync(
            url=job.category_url,
            api_key=api_key,
            pagination_type=getattr(job, 'pagination_type', 'auto'),
            max_pages=getattr(job, 'max_pages', 1) or 1,
            max_items=job.max_items,
            fields=job_fields
        )
        
        # 3. Save Products to Database
        created_count = 0
        base_url = job.category_url

        for item in products_data:
            if job.max_items > 0 and created_count >= job.max_items:
                break
            if not isinstance(item, dict): continue
            
            raw_price = item.get('price')
            price_val = None
            if raw_price:
                num_match = re.search(r'(\d+[\d,.]*)', str(raw_price))
                if num_match:
                    try:
                        price_val = float(num_match.group(1).replace(',', ''))
                    except: price_val = None

            Product.objects.create(
                job=job,
                title=unicodedata.normalize('NFKC', str(item.get('title', 'No Title'))).strip(),
                price=price_val,
                currency=item.get('currency', 'JOD'),
                image_url=urljoin(base_url, str(item.get('image', '')).strip())[:500],
                product_url=urljoin(base_url, str(item.get('product_url', '')).strip())[:500],
                rating=item.get('rating'),
                site=job.site,
                scraped_at=timezone.now()
            )
            created_count += 1
        
        # 4. Market Analysis Phase - FIXED LOGIC
        if created_count > 0 and job.batch:
            job.note = "Generating AI Market Analysis..."
            job.save(update_fields=["note"])
            
            batch_products = Product.objects.filter(job__batch=job.batch)
            stats = compute_batch_stats(batch_products)
            active_sites = list(batch_products.values_list('site', flat=True).distinct())
            
            analysis_text = summarize_batch(stats, job.batch.query, active_sites)
            
            #Assign to the object in memory 
            job.batch.ai_summary = analysis_text

        # 5. Finalize
        job.status = ScrapeJob.Status.DONE
        job.note = f" Success! Saved {created_count} products."
        job.save(update_fields=["status", "note"])

        # Calculate execution time
        execution_time = time.time() - start_time
        
        if job.batch:
            job.batch.duration = execution_time
            # This save now commits BOTH the duration AND the ai_summary safely
            job.batch.save()

        return {'status': 'success', 'job_id': job_id, 'products_count': created_count, 'duration': execution_time}

    except PermissionError as e:
        execution_time = time.time() - start_time
        logger.warning(f"Shielded: {e}")
        if job:
            job.status = ScrapeJob.Status.ERROR
            job.note = f"Policy Block: {str(e)}"
            job.save(update_fields=["status", "note"])
            if job.batch:
                job.batch.duration = execution_time
                job.batch.save()
        return {'status': 'blocked', 'reason': str(e)}

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Job {job_id} failed: {e}")
        if job:
            job.status = ScrapeJob.Status.ERROR
            job.note = f"Error: {str(e)[:200]}"
            job.save(update_fields=["status", "note"])
            if job.batch:
                job.batch.duration = execution_time
                job.batch.save()
        raise e