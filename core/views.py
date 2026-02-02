import logging
import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.db.models import Count

from .forms import RegisterForm
from .models import ScrapeBatch, ScrapeJob, Product, Site
from .analytics import compute_batch_stats
from .tasks import run_ai_scrape_job

logger = logging.getLogger(__name__)

# --- Auth Views ---

def home(request):
    return render(request, 'home.html') 

def register_view(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            login(request, user)
            return redirect('home')
    else:
        form = RegisterForm() 
    return render(request, 'register.html', {'form': form})

# --- App Views ---

@login_required
def scrape(request):
    if request.method == "POST":
        category_url = request.POST.get("category_url", "").strip()
        
        # --- NEW: Robots.txt Compliance Validation ---
        from .selector_detector import PlaywrightScraper  # Import your scraper class
        scraper_tool = PlaywrightScraper()
        
        if category_url and not scraper_tool.can_scrape(category_url):
            pagination_choices = [
                ('single', 'Single Page Only'),
                ('next', 'Next Button Pagination'),
                ('infinite', 'Infinite Scroll'),
                ('auto', 'Auto-Detect (Recommended)'),
            ]
            return render(request, "core/scrape.html", {
                "error": "Access Denied: This website does not allow automated scraping (robots.txt restriction).",
                "defaults": {"max_items": 50, "max_pages": 1},
                "pagination_choices": pagination_choices
            })
        # --- End of Compliance Check ---

        chosen_fields = request.POST.getlist('fields')
        
        # Default fallback fields
        if not chosen_fields:
            chosen_fields = ["title", "price", "image_url", "product_url"]
        
        # Mapping Django field names to Scraper logic names
        scraper_fields = [f.replace('image_url', 'image') for f in chosen_fields]
        
        # Ensure product_url is included for deduplication
        if 'product_url' not in scraper_fields:
            scraper_fields.append('product_url')

        pagination_type = request.POST.get("pagination_type", "auto")
        
        try:
            max_items = int(request.POST.get("max_items", "50"))
            max_items = max(0, min(max_items, 1000)) 
        except (ValueError, TypeError):
            max_items = 50
        
        try:
            max_pages = int(request.POST.get("max_pages", "1"))
            if max_pages < 0: max_pages = 0
            if max_pages > 200: max_pages = 200
        except (ValueError, TypeError):
            max_pages = 1
            
        if not category_url:
            return render(request, "core/scrape.html", {"error": "Category URL is required"})

        site = Site.DUMYAH if "dumyah.com" in category_url else Site.OTHER
        
        # Create Batch and Job
        batch = ScrapeBatch.objects.create(user=request.user, query=category_url) 
        job = ScrapeJob.objects.create(
            batch=batch,
            site=site,
            status=ScrapeJob.Status.PENDING,
            category_url=category_url,
            fields=scraper_fields,
            max_items=max_items,
            max_pages=max_pages,
            pagination_type=pagination_type 
        )

        # Enqueue the background task
        run_ai_scrape_job.delay(job.id)
        logger.info(f"Job {job.id} enqueued for Batch {batch.id}")

        return redirect("dashboard", batch_id=batch.id)

    pagination_choices = [
        ('single', 'Single Page Only'),
        ('next', 'Next Button Pagination'),
        ('infinite', 'Infinite Scroll'),
        ('auto', 'Auto-Detect (Recommended)'),
    ]
    
    return render(request, "core/scrape.html", {
        "defaults": {"max_items": 50, "max_pages": 1},
        "pagination_choices": pagination_choices
    })

@login_required
def history(request):
    # Fetch batches fresh and ensure 'duration' is included
    batches = ScrapeBatch.objects.filter(user=request.user).order_by("-created_at")[:30]
    
    # Annotate and Prefetch as you were doing
    batches = batches.annotate(
        count=Count('scrapejob_set__products')
    ).prefetch_related('scrapejob_set')
    
    return render(request, "core/history.html", {"batches": batches})

@login_required
def dashboard(request, batch_id):
    try:
        # Fetch the batch and its products
        batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
        products = Product.objects.filter(job__batch=batch).order_by('-scraped_at')
        
        # Compute analytics
        stats = compute_batch_stats(products)
        
        # Chart Data Preparation
        chart_products = list(products[:50])
        chart_labels = [p.title[:15] + "..." if p.title else "No Title" for p in chart_products]
        chart_prices = [float(p.price) if p.price else 0 for p in chart_products]

        # Price Range Buckets
        price_ranges = {
            'Budget (< 20)': 0,
            'Mid-Range (20-50)': 0,
            'Premium (50-100)': 0,
            'Luxury (100+)': 0
        }

        for p in chart_products:
            if p.price:
                try:
                    price_val = float(p.price)
                    if price_val < 20: price_ranges['Budget (< 20)'] += 1
                    elif price_val < 50: price_ranges['Mid-Range (20-50)'] += 1
                    elif price_val < 100: price_ranges['Premium (50-100)'] += 1
                    else: price_ranges['Luxury (100+)'] += 1
                except (ValueError, TypeError): continue
        
        return render(request, "core/dashboard.html", {
            "batch": batch,  # Template now accesses batch.ai_summary
            "stats": stats,
            "products": chart_products,
            "chart_labels": json.dumps(chart_labels),
            "chart_prices": json.dumps(chart_prices),
            "range_labels": json.dumps(list(price_ranges.keys())),
            "range_data": json.dumps(list(price_ranges.values())),
        })
    except Exception as e:
        logger.error(f"Dashboard error for batch {batch_id}: {e}", exc_info=True)
        return render(request, "core/dashboard.html", {"error": str(e)})

@login_required
def job_status(request, batch_id):
    batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
    # Fetch all jobs for this batch, latest first
    jobs = list(ScrapeJob.objects.filter(batch=batch).order_by('-id').values(
        "id", "status", "note"
    ))
    return JsonResponse({"jobs": jobs})

# --- Export Views ---

@login_required
def export_csv(request, batch_id):
    # Fetch the batch once
    batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
    
    # Fetch products associated with this batch
    products = Product.objects.filter(job__batch=batch).order_by("site", "title")
    
    # Define columns for the CSV
    potential_fields = ["title", "price", "currency", "product_url", "image_url", "site", "search_query", "scraped_at"]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="basira_batch_{batch_id}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(potential_fields)
    
    # Cache the query from the batch object
    actual_query = getattr(batch, 'query', 'N/A')

    for p in products:
        row = []
        for field in potential_fields:
            if field == "search_query":
                # Use the value from the batch object directly
                row.append(actual_query)
            else:
                # Use getattr for fields that exist on the Product model
                row.append(getattr(p, field, "N/A"))
        writer.writerow(row)
        
    return response

@login_required
def export_json(request, batch_id):
    batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
    products = Product.objects.filter(job__batch=batch)
    
    potential_fields = ["title", "price", "currency", "product_url", "image_url", "site", "search_query", "rating", "scraped_at"]
    active_fields = [f for f in potential_fields if products.exclude(**{f"{f}__isnull": True}).exists()]
    
    items = list(products.values(*active_fields))
    return JsonResponse(items, safe=False)