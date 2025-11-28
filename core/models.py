from django.db import models
from django.conf import settings

# This file defines your database tables.

class Site(models.TextChoices):
    # This is the enum your view is trying to import
    SHEIN = "shein", "Shein"
    TEMU = "temu", "Temu"
    DUMYAH = "dumyah", "DUMYAH"
    OTHER = "other", "Other"

class ScrapeBatch(models.Model):
    """ A 'Batch' is one click of the 'Scrape' button. It groups jobs. """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) # This is required
    query = models.CharField(max_length=200, blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Batch {self.id} ({self.query})"

class ScrapeJob(models.Model):
    """ A 'Job' is one specific scrape (e.g., scrape 'temu' for 'dresses'). """
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        RUNNING = 'RUNNING', 'Running'
        DONE = 'DONE', 'Done'
        ERROR = 'ERROR', 'Error'

    batch = models.ForeignKey(ScrapeBatch, on_delete=models.CASCADE, related_name="scrapejob_set")
    site = models.CharField(max_length=32, choices=Site.choices, default=Site.OTHER)
    
    category_url = models.URLField(max_length=1024, default="")
    fields = models.JSONField(default=list) 
    
    max_items = models.PositiveIntegerField(
        default=50,
        help_text="Max items to scrape. 0 for no limit."
    )
    
    # This is the new field you wanted
    max_pages = models.PositiveIntegerField(
        default=0, # 0 means no limit
        help_text="Max pages to scrape. 0 for no limit."
    )
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    note = models.TextField(blank=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    selectors = models.JSONField(default=dict, blank=True)

class Product(models.Model):
    """ One product found during a scrape. """
    
    job = models.ForeignKey(ScrapeJob, on_delete=models.CASCADE, related_name='products')
    
    site = models.CharField(max_length=32, choices=Site.choices)
    title = models.CharField(max_length=500)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True)
    product_url = models.URLField(max_length=2048, blank=True, db_index=True)
    image_url = models.URLField(max_length=2048, blank=True)
    search_query = models.CharField(max_length=1024, blank=True) 
    rating = models.FloatField(null=True, blank=True)
    scraped_at = models.DateTimeField(auto_now_add=True)

class BatchInsight(models.Model):
    """ Stores the AI-generated summary for a batch. """
    batch = models.OneToOneField(ScrapeBatch, on_delete=models.CASCADE, related_name='insight')
    summary = models.TextField() 
    created_at = models.DateTimeField(auto_now_add=True)