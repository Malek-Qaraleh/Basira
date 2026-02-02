import logging
import os
from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

def _init_client():
    """Initialize Google GenAI client using the dedicated Chatbot key."""
    # Prioritize CHATBOT_API_KEY for isolated quota management
    api_key = getattr(settings, 'CHATBOT_API_KEY', getattr(settings, 'CHATBOT_API_KEY', None))
    
    if not api_key:
        logger.warning("No API key configured for Basira AI")
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize GenAI client: {e}")
        return None

def get_chat_response(session, user_message):
    client = _init_client()
    if not client:
        return "GenAI client not available."

    # We define the persona and the instructions to prioritize tools.
    system_text = """
    You are Basira Insights, an expert consultant in Data Analysis, Digital Marketing, and Financial Research.
    
    IMPORTANT: You have direct access to the user's uploaded documents via a high-performance File Search tool. 
    
    Rules for Document Handling:
    - When a user asks a question, you MUST prioritize information found in the uploaded documents over your general training data.
    - If the answer is found in a document, base your response primarily on that content.
    - Mention the title of the document you are referencing in your answer.
    - If no relevant information is found in the documents, specify that before providing a general expert opinion.

    Formatting Guidelines:
    - Use Markdown for formatting (bold, lists, headers).
    - Always separate lists from paragraphs with a blank line.
    - Be data-driven, actionable, and concise.
    """

    # --- RAG TOOL CONFIGURATION ---
    # This activates the 'Document Reading' capability.
    tools = []
    if hasattr(session, 'file_search_store_id') and session.file_search_store_id:
        tools.append(types.Tool(
            file_search=types.FileSearch(
                file_search_store_names=[session.file_search_store_id]
            )
        ))
    else:
        system_text += "\nNote: No documents have been indexed for this session yet."

    # --- CONSTRUCT HISTORY ---
    history = []
    recent_messages = session.messages.order_by('-created_at')[:10]
    for msg in reversed(recent_messages):
        history.append({
            "role": "user" if msg.role == 'user' else "model", 
            "parts": [{"text": msg.content}]
        })

    try:
        # --- GENERATE GROUNDED CONTENT ---
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction={'parts': [{'text': system_text}]},
                tools=tools, # This is the "Reading" engine
                temperature=0.2, # Lower temperature ensures higher factual accuracy
                max_output_tokens=1000,
            )
        )
        
        return response.text if response.text else "I couldn't find specific data in your documents to answer this."
        
    except Exception as e:
        logger.error(f"Basira Insights Error: {e}")
        return "I encountered an error while analyzing your data."