import logging
from django.conf import settings
import google.generativeai as genai

logger = logging.getLogger(__name__)

# Configure Gemini
try:
    genai.configure(api_key=settings.GEMINI_API_KEY)
except Exception as e:
    logger.error(f"Gemini API key error: {e}")

def perform_thematic_analysis(topic, articles):
    """
    Sends article summaries to Gemini to extract common themes and narratives.
    """
    if not articles:
        return "No articles found to analyze."

    # Prepare a digest of the content (limit text to avoid token limits)
    # We send the title and the first 300 characters of each article
    content_digest = "\n\n".join([
        f"Title: {a.title}\nExcerpt: {a.clean_text[:300]}..." 
        for a in articles[:30] # Analyze top 30 articles to save tokens/time
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
        model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-09-2025")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"AI Analysis failed: {e}")
        return f"Error generating analysis: {e}"