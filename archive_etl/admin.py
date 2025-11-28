from django.contrib import admin
from .models import ScrapeSource, Article

@admin.register(ScrapeSource)
class ScrapeSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "is_active", "language_code")
    list_filter = ("is_active", "language_code")
    search_fields = ("name", "base_url")
    ordering = ("name",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "pub_date", "scraped_at")
    list_filter = ("source", "source__language_code", "pub_date")
    search_fields = ("title", "clean_text", "source_url", "author_name")
    date_hierarchy = "pub_date"
    readonly_fields = ('scraped_at',)

    def language_code(self, obj):
        return obj.source.language_code
    language_code.short_description = "Lang"

    fieldsets = (
        (None, {
            'fields': ('title', 'clean_text', 'pub_date')
        }),
        ('Source & Provenance', {
            'fields': ('source', 'source_url', 'author_name', 'scraped_at')
        }),
    )