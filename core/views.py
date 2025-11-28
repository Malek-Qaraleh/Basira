import logging
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.db.models import Count
from .forms import RegisterForm # Assuming your forms file has RegisterForm
from .models import ScrapeBatch, ScrapeJob, Product, Site, BatchInsight
from .analytics import compute_batch_stats
import json

from .tasks import run_ai_scrape_job

logger = logging.getLogger(__name__)

#Auth Views

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

#App views

@login_required
def scrape(request):
    if request.method == "POST":
        # 1-Get data from the form
        category_url = request.POST.get("category_url", "").strip()
        fields = request.POST.getlist('fields') or ["title","price","image_url","product_url","currency"]
        
        try:
            max_items = int(request.POST.get("max_items", "50"))
            max_items = max(0, min(max_items, 1000)) 
        except (ValueError, TypeError):
            max_items = 50
        
        try:
            max_pages = int(request.POST.get("max_pages", "0"))
            max_pages = max(0, max_pages) 
        except (ValueError, TypeError):
            max_pages = 0
            
        
        # 2- Basic Validation
        if not category_url:
            return render(request, "core/scrape.html", {"error": "Category URL is required"})

        # 3- Auto-detect site from URL
        site = Site.OTHER
        if "shein.com" in category_url:
            site = Site.SHEIN
        elif "temu.com" in category_url:
            site = Site.TEMU
        elif"dumyah.com" in category_url:
            site = Site.DUMYAH
        
        # 4- Create the batch and job
        # This is the line that was crashing. It is now correct.
        batch = ScrapeBatch.objects.create(user=request.user, query=category_url) 
        job = ScrapeJob.objects.create(
            batch=batch,
            site=site,
            status=ScrapeJob.Status.PENDING,
            category_url=category_url,
            fields=fields,
            max_items=max_items,
            max_pages=max_pages # Save the new field
        )

        # 5- Enqueue the background job
        run_ai_scrape_job.delay(job.id)
        logger.info(f"Job {job.id} enqueued to Celery.")

        # This is your desired redirect
        return redirect("dashboard", batch_id=batch.id)

    # GET request: just show the form
    return render(request, "core/scrape.html",{ "defaults": {"max_items":50}})


@login_required
def history(request):
    batches = ScrapeBatch.objects.filter(user=request.user).order_by("-created_at")[:30]
    batches = batches.annotate(
        count = Count('scrapejob_set__products')
    ).prefetch_related(
        'scrapejob_set', 'insight'
    )

    return render(request, "core/history.html", {"batches": batches})


@login_required
def dashboard(request, batch_id):
    # This is your results page
    batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
    products = Product.objects.filter(job__batch=batch)
    stats = compute_batch_stats(products)
    
    try:
        insight = batch.insight
    except BatchInsight.DoesNotExist:
        insight = None
    
    # Limit to top 50 for readability
    chart_products = products[:50]
    chart_labels = [p.title[:15] + "..." for p in chart_products]
    chart_prices = [float(p.price) if p.price else 0 for p in chart_products]

    # --- 2. Prepare Price Range Data (Replaces Ratings) ---
    # Bucket all products into price ranges to see distribution
    price_ranges = {
        'Budget (< 20)': 0,
        'Mid-Range (20-50)': 0,
        'Premium (50-100)': 0,
        'Luxury (100+)': 0
    }

    for p in products:
        if p.price:
            try:
                price_val = float(p.price)
                if price_val < 20:
                    price_ranges['Budget (< 20)'] += 1
                elif price_val < 50:
                    price_ranges['Mid-Range (20-50)'] += 1
                elif price_val < 100:
                    price_ranges['Premium (50-100)'] += 1
                else:
                    price_ranges['Luxury (100+)'] += 1
            except (ValueError, TypeError):
                continue
    return render(request, "core/dashboard.html", {
        "batch": batch,
        "stats": stats,
        "insight": insight,
        "products": products[:50],
        
        # Pass JSON data to template
        "chart_labels": json.dumps(chart_labels),
        "chart_prices": json.dumps(chart_prices),
        
        # New Data Variables for the Price Range Chart
        "range_labels": json.dumps(list(price_ranges.keys())),
        "range_data": json.dumps(list(price_ranges.values())),
    })


@login_required
def job_status(request, batch_id):
    batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
    jobs = list(ScrapeJob.objects.filter(batch=batch).values("id","site","status","note","created_at"))
    return JsonResponse({"batch_id":batch_id, "jobs": jobs})

@login_required
def export_csv(request, batch_id):
    batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
    products = Product.objects.filter(job__batch=batch).order_by("site", "title")
    
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="batch_{batch_id}.csv"'
    
    writer = csv.writer(response)
    
    # Check if ANY product in this batch has a rating
    has_ratings = products.filter(rating__isnull=False).exists()
    
    # Define headers dynamically
    headers = ["title", "price", "currency", "product_url", "image_url", "site", "query", "scraped_at"]
    if has_ratings:
        headers.insert(6, "rating") # Insert rating before query if it exists

    writer.writerow(headers)
    
    for p in products:
        row = [
            p.title,
            p.price,
            p.currency,
            p.product_url,
            p.image_url,
            p.site,
            p.search_query,
            p.scraped_at
        ]
        if has_ratings:
            # Insert the rating value at the same index as the header
            row.insert(6, p.rating)
            
        writer.writerow(row)
        
    return response

@login_required
def export_json(request, batch_id):
    batch = get_object_or_404(ScrapeBatch, id=batch_id, user=request.user)
    products = Product.objects.filter(job__batch=batch)
    items = list(products.values(
        "title","price","currency","product_url","image_url","site","search_query","scraped_at"
    ))
    return JsonResponse(items, safe=False)