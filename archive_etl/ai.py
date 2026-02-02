import logging
from django.conf import settings

# Use the new google.genai client
try:
    from google import genai as _genai
except Exception:
    _genai = None

logger = logging.getLogger(__name__)

def _init_client():
    """Initialize Google GenAI client."""
    if _genai is None:
        return None
    api_key = getattr(settings, 'CHATBOT_API_KEY', None)
    if not api_key:
        return None
    try:
        return _genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize GenAI client: {e}")
        return None

def perform_thematic_analysis(topic, articles):
    """
    Sends article summaries to Gemini to extract common themes and narratives.
    """
    if not articles:
        return "No articles found to analyze."

    # 1. Initialize the new SDK Client
    client = _init_client()
    if not client:
        return "AI Client initialization failed. Check your API key."

    # 2. Prepare digest
    content_digest = "\n\n".join([
        f"Title: {a.title}\nExcerpt: {a.clean_text[:300]}..." 
        for a in articles[:30] 
    ])

    prompt = f"""
    You are an expert academic researcher specializing in Media Analysis.
    I have collected news articles related to the topic: "{topic}".
    Here is a digest of the content:
    {content_digest}
    
    Please perform a Thematic Analysis on this data. Provide the output in Markdown:
    1. **Key Themes**: Identify the top 3 recurring themes.
    2. **Narrative Tone**: Is the coverage generally positive, negative, or neutral?
    3. **Key Entities**: Who are the main people/organizations mentioned?
    4. **Research Summary**: A 2-sentence abstract of these findings.
    """

    try:
        # 3. Use the new SDK syntax: client.models.generate_content
        response = client.models.generate_content(
            model="gemini-2.5-flash", # Updated to the latest stable model
            contents=prompt,
            config={
                'temperature': 0.3, # Lower temperature for analytical consistency
            }
        )
        
        if response.text:
            return response.text
        return "AI returned an empty analysis."

    except Exception as e:
        logger.error(f"AI Analysis failed: {e}")
        return f"Error generating analysis: {e}"