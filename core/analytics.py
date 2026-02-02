import logging
from django.db.models import Avg, Min, Max, Count, Sum

logger = logging.getLogger(__name__)

def compute_batch_stats(product_queryset):
    try:
        count = product_queryset.count()
        if count == 0:
            return {"count": 0, "has_price": False}

        # Filter for products that actually have a price
        products_with_price = product_queryset.filter(price__isnull=False, price__gt=0)
        
        stats = {
            "count": count,
            "has_price": products_with_price.exists(),
            "avg": 0, "min": 0, "max": 0, "median": 0,
        }

        if stats["has_price"]:
            # Standard Aggregations
            price_agg = products_with_price.aggregate(
                avg=Avg('price'), min=Min('price'), max=Max('price')
            )
            stats.update({
                "avg": round(float(price_agg['avg'] or 0), 2),
                "min": round(float(price_agg['min'] or 0), 2),
                "max": round(float(price_agg['max'] or 0), 2),
            })

            # --- Manual Median Calculation ---
            # Extract values, convert to float, and sort
            prices = sorted([float(p) for p in products_with_price.values_list('price', flat=True)])
            n = len(prices)
            if n > 0:
                mid = n // 2
                if n % 2 == 0:
                    # Even number of items: average of the two middle values
                    stats['median'] = round((prices[mid - 1] + prices[mid]) / 2, 2)
                else:
                    # Odd number of items: the middle value
                    stats['median'] = round(prices[mid], 2)

        # Site Counts
        site_counts = product_queryset.values('site').annotate(c=Count('id'))
        stats['site_counts'] = {item['site']: item['c'] for item in site_counts}
        
        return stats
    except Exception as e:
        logger.error(f"Stats error: {e}", exc_info=True)
        return {"count": 0, "error": str(e)}