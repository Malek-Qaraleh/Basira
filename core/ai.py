import logging
import json
from django.conf import settings
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini
try:
    genai.configure(api_key=settings.GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gemini API key not configured or invalid: {e}")

def _build_prompt(stats, query, sites):
    # Create a simple JSON of the stats to pass to the model
    stats_json = json.dumps({
        "query": query,
        "sites": sites,
        "total_items": stats.get("count"),
        "average_price": stats.get("avg"),
        "median_price": stats.get("median"),
        "price_range": f"${stats.get('min')} to ${stats.get('max')}" if stats.get("has_price") else "N/A",
        "items_per_site": stats.get("site_counts"),
    }, indent=2)
    
    prompt = f"""
    You are a concise e-commerce data analyst. 
    A user has scraped a website for the query "{query}".
    Here is a JSON object of the results:
    
    {stats_json}
    
    Please provide a 3-bullet-point summary of the findings.
    Be insightful. Don't just list the numbers. What do they mean?
    
    Example:
    - The scrape for "dresses" found 50 items, with an average price of $29.99.
    - The price range is quite wide ($10 to $150), suggesting a mix of sale and luxury items.
    - Shein had the most products (40), but Temu had a slightly lower median price ($25 vs $28).
    
    Now, provide the summary for the data above.
    """
    return prompt

def summarize_batch(stats, query, sites):
    """
    Uses Gemini to generate a text summary of the scrape stats.
    """
    if not stats or stats.get("count", 0) == 0:
        return "No products found to summarize."

    # Fallback for when no API key is set
    if not settings.GEMINI_API_KEY or "your-google" in settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Using fallback summary.")
        return f"Found {stats.get('count', 0)} items. Average price: ${stats.get('avg', 0)}."

    try:
        model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-09-2025")
        prompt = _build_prompt(stats, query, sites)
        response = model.generate_content(prompt)
        
        summary_text = response.text.strip()
        # Clean up the markdown-style bullets
        summary_text = summary_text.replace("•", "-").replace("*", "-")
        
        logger.info("Generated AI summary.")
        return summary_text

    except Exception as e:
        logger.error(f"Gemini summary failed: {e}")
        return f"Found {stats.get('count', 0)} items. Summary generation failed."