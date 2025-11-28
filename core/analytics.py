import logging
from django.db.models import Avg, Min, Max, Count, Sum

logger = logging.getLogger(__name__)

def compute_batch_stats(product_queryset):
    """
    Computes analytics for a queryset of products.
    Calculates median manually for Django 5.0.
    Includes stats for ratings and review counts.
    """
    try:
        count = product_queryset.count()
        if count == 0:
            return {"count": 0, "has_price": False, "has_rating": False}

        # --- Base Querysets ---
        products_with_price = product_queryset.filter(price__isnull=False, price__gt=0)
        products_with_rating = product_queryset.filter(rating__isnull=False)

        stats = {
            "count": count,
            "has_price": products_with_price.exists(),
            "has_rating": products_with_rating.exists(),
            "avg": 0, "min": 0, "max": 0, "median": 0,
            "avg_rating": 0, "min_rating": 0, "max_rating": 0, "median_rating": 0, "review_total": 0,
        }

        # --- Price Statistics ---
        if stats["has_price"]:
            price_agg = products_with_price.aggregate(
                avg=Avg('price'),
                min=Min('price'),
                max=Max('price')
            )
            stats.update({
                "avg": round(float(price_agg['avg']), 2) if price_agg['avg'] else 0,
                "min": round(float(price_agg['min']), 2) if price_agg['min'] else 0,
                "max": round(float(price_agg['max']), 2) if price_agg['max'] else 0,
            })

        # --- Rating Statistics ---
        if stats["has_rating"]:
            rating_agg = products_with_rating.aggregate(
                avg_rating=Avg('rating'),
                min_rating=Min('rating'),
                max_rating=Max('rating'),
            )
            stats.update({
                "avg_rating": round(float(rating_agg['avg_rating']), 2) if rating_agg['avg_rating'] else 0,
                "min_rating": round(float(rating_agg['min_rating']), 1) if rating_agg['min_rating'] else 0,
                "max_rating": round(float(rating_agg['max_rating']), 1) if rating_agg['max_rating'] else 0,
            })

        # --- Get count per site ---
        site_counts = product_queryset.values('site').annotate(count=Count('id')).order_by('-count')
        stats['site_counts'] = {item['site']: item['count'] for item in site_counts}

        # --- Get median price per site (MANUAL CALCULATION) ---
        site_medians = {}
        for site in stats['site_counts']:
            site_products = products_with_price.filter(site=site).order_by('price')
            count = site_products.count()
            if count > 0:
                median_index = count // 2
                if count % 2 == 0: # Even number of items
                    p1 = site_products[median_index - 1].price
                    p2 = site_products[median_index].price
                    site_medians[site] = round(float((p1 + p2) / 2), 2)
                else: # Odd number of items
                    median_product = site_products[median_index]
                    site_medians[site] = round(float(median_product.price), 2)
        
        stats['site_medians'] = site_medians
        # Use median from the first site as the overall median
        if site_medians:
            stats['median'] = site_medians.get(list(site_medians.keys())[0])

        logger.info(f"Computed stats: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Failed to compute stats: {e}", exc_info=True)
        return {"count": 0, "has_price": False, "has_rating": False, "error": str(e)}