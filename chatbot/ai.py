import logging
import google.generativeai as genai
from django.conf import settings
from core.models import Product, ScrapeBatch
from archive_etl.models import Article, ResearchRequest

logger = logging.getLogger(__name__)
genai.configure(api_key=settings.GEMINI_API_KEY)

def get_chat_response(session, user_message):
    
    # 2. Construct System Prompt
    system_instruction = """
    You are Basira AI, a specialized consultant for Data Analysis, Digital Marketing, and Academic Research.
    
    Your capabilities:
    1. Explain complex data analysis techniques and statistical methods.
    2. Suggest marketing strategies (SEO, content, social media growth).
    3. Advise on research methodologies and academic writing.
    
    You do NOT have access to the user's private database or scraped content. 
    Answer based on your general expert knowledge. 
    Be professional, concise, and actionable.
    """

    # 3. Build History
    history = []
    # Fetch all messages to maintain conversation flow
    for msg in session.messages.order_by('created_at'):
        history.append({
            "role": "user" if msg.role == 'user' else "model", 
            "parts": [msg.content]
        })
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash-preview-09-2025", 
            system_instruction=system_instruction
        )
        
        # Start chat session with history
        chat = model.start_chat(history=history)
        response = chat.send_message(user_message)
        return response.text
        
    except Exception as e:
        logger.error(f"Gemini Chat Error: {e}")
        return "I apologize, but I am currently unable to process your request. Please try again later."