import logging
import json
from django.conf import settings

# Use the new google.genai client
genai_client = None

try:
    from google import genai as _genai_new
except Exception:
    _genai_new = None

logger = logging.getLogger(__name__)

def _init_client():
    """Initialize Google GenAI client using the new library."""
    global genai_client
    api_key = getattr(settings, 'GOOGLE_API_KEY', None)
    if not api_key:
        return None
    try:
        if _genai_new:
            genai_client = _genai_new.Client(api_key=api_key)
            logger.info("google.genai client initialized.")
        else:
            logger.error("google-genai is not installed. Install it with `pip install google-genai`." )
    except Exception as e:
        logger.error(f"Failed to initialize GenAI client: {e}")
        genai_client = None
    return genai_client

def _generate_summary(prompt: str, model: str) -> str:
    """Generate content with the google.genai client."""
    if genai_client is None:
        _init_client()
    if genai_client is None:
        raise RuntimeError("GenAI client not initialized")

    resp = genai_client.models.generate_content(model=model, contents=prompt)
    try:
        return resp.text.strip()
    except Exception:
        try:
            parts = []
            cand = resp.candidates[0]
            for p in getattr(cand, 'content', {}).parts:
                if getattr(p, 'text', None):
                    parts.append(p.text)
            return "\n".join(parts).strip() if parts else ""
        except Exception:
            return ""

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
    
    dot = "\u2022"

    prompt = f"""
            You are a concise e-commerce data analyst. 
            A user has scraped a website for the query "{query}".
            Here is a JSON object of the results:
            
            {stats_json}
            
            Provide a 3-bullet-point summary using a simple circular dot (•) for each point.
            DO NOT use asterisks (*), bold text, or special characters other than the bullet point.
            
            Example format:
            {dot} Point one regarding inventory.
            {dot} Point two regarding pricing.
            {dot} Point three regarding market position.
            
            Now, provide the summary for the data above.
            """ 
    return prompt

def summarize_batch(stats, query, sites):
    if not stats or stats.get("count", 0) == 0:
        return "No products found to summarize."

    # Force a summary even if prices are missing
    prompt = _build_prompt(stats, query, sites)
    model_name = getattr(settings, 'GENAI_SUMMARY_MODEL', "gemini-2.5-flash")
    
    try:
        summary_text = _generate_summary(prompt, model=model_name)
        return summary_text.replace("•", "-")
    except Exception as e:
        return f"Summary generation failed, but {stats.get('count')} items were processed."