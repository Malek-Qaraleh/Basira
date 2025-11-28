from django.contrib import admin
from .models import ScrapeBatch, ScrapeJob, Product, BatchInsight

@admin.register(ScrapeBatch)
class ScrapeBatchAdmin(admin.ModelAdmin):
    # ScrapeBatch has: user, query, sites (JSON), created_at
    list_display = ("id", "query", "created_at")
    search_fields = ("query", "user__username")

@admin.register(ScrapeJob)
class ScrapeJobAdmin(admin.ModelAdmin):
    # ScrapeJob has: batch (FK), site (singular), status, created_at
    list_display = ("id", "batch", "site", "status", "created_at")
    list_filter = ("site", "status", "created_at") 

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "site", "title", "price", "currency", "rating", "scraped_at", "job_id")
    search_fields = ("title", "product_url", "search_query")
    list_filter = ("site", "currency", "scraped_at", "rating")

@admin.register(BatchInsight)
class BatchInsightAdmin(admin.ModelAdmin):
    list_display = ("batch", "created_at")
