import json, re
import google.generativeai as genai
import markdown
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import ChatSession, ChatMessage, ChatDocument
from PyPDF2 import PdfReader # pip install PyPDF2

genai.configure(api_key=settings.CHATBOT_API_KEY)

def clean_markdown(text):
    """
    1. Pre-processes text to ensure lists render correctly by adding a blank line before asterisks.
    2. Converts Markdown syntax into safe HTML tags.
    """
    # Fix 'tight list' issue: Add double newline before bullet points if missing
    text = re.sub(r'(?<!\n)\n(\*|-)\s', r'\n\n\1 ', text)
    
    # Convert using standard extensions for tables, code blocks, and extra spacing
    return markdown.markdown(text, extensions=['extra', 'nl2br', 'codehilite'])

@login_required
def chat_interface(request, session_id=None):
    sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
    current_session = None
    chat_log = [] 
    documents = []
    
    if session_id:
        current_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        # Fetch only the messages for this session
        chat_log = current_session.messages.all().order_by('created_at')
        for msg in chat_log:
            if msg.role == 'model':
                msg.content = clean_markdown(msg.content)
        documents = current_session.documents.all().order_by('-created_at')

    return render(request, 'chatbot/room.html', {
        'sessions': sessions,
        'current_session': current_session,
        'chat_log': chat_log, 
        'documents': documents
    })

@csrf_exempt
@login_required
def send_message(request):
    """
    Handles AI consultation by managing sessions, extracting document context,
    and generating a Markdown-cleaned AI response.
    """
    if request.method == 'POST':
        user_text = request.POST.get('message')
        session_id = request.POST.get('session_id')
        
        if not user_text:
            return JsonResponse({'error': 'Empty message'}, status=400)

        try:
            # FIX: Handle empty session_id to prevent ValueError
            if session_id and session_id.strip():
                chat_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
            else:
                # Create a new session if starting fresh
                title = user_text[:30] + "..." if len(user_text) > 30 else user_text
                chat_session = ChatSession.objects.create(user=request.user, title=title)

            # Save the user's message to history
            ChatMessage.objects.create(session=chat_session, role='user', content=user_text)

            # 1. GATHER CONTEXT: Pull text from all PDFs linked to this session
            docs = ChatDocument.objects.filter(session=chat_session)
            context_text = "\n".join([d.content for d in docs if d.content])

            # 2. CONSTRUCT PROMPT: Prioritize the extracted text
            system_instruction = (
                "You are Basira AI, a senior Marketing Strategist and Digital Transformation Expert "
                "specializing in the Middle Eastern market. Your mission is to assist marketing companies "
                "and research firms in streamlining their research through AI-driven insights and automation. "
                
                "Key Areas of Expertise: "
                "1. Market Research: Analyze the provided document context to identify consumer behavior patterns, "
                "specifically focusing on student motivation and online learning trends in the MENA region. "
                "2. Strategic Frameworks: Help users develop marketing strategies using frameworks like "
                "STP (Segmentation, Targeting, Positioning), SWOT, and Customer Journey Maps. "
                "3. Process Optimization: Offer guidance on using web scraping and data extraction to "
                "automate competitive analysis and market mapping. "

                "Response Guidelines: "
                "- Always prioritize the provided 'Document Context' for specific data points. "
                "- Maintain a professional, insightful, and strategic tone. "
                "- Ground creative marketing ideas in data-driven research. "
                
                f"\n\nDocument Context:\n{context_text}"
                )
            
            # Use gemini-2.5-flash for speed and context handling
            model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_instruction)
            
            # 3. GENERATE RESPONSE
            response = model.generate_content(user_text)
            ai_text = response.text
            
            # Save AI response to DB
            ChatMessage.objects.create(session=chat_session, role='model', content=ai_text)
            
            # Return cleaned HTML for proper list/bold rendering
            return JsonResponse({
                'response': clean_markdown(ai_text),
                'session_id': chat_session.id
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@login_required
def upload_document(request):
    if request.method == 'POST' and request.FILES.get('file'):
        session_id = request.POST.get('session_id')
        uploaded_file = request.FILES['file']
        
        try:
            # FIX: If session_id is empty or invalid, create a new one
            if session_id and str(session_id).isdigit():
                session = get_object_or_404(ChatSession, id=session_id, user=request.user)
            else:
                session = ChatSession.objects.create(
                    user=request.user, 
                    title=f"Doc: {uploaded_file.name[:20]}"
                )

            # Extract text using PyPDF2
            reader = PdfReader(uploaded_file)
            text = "".join([page.extract_text() for page in reader.pages])

            # Save the document
            doc = ChatDocument.objects.create(
                session=session, 
                file_name=uploaded_file.name, 
                content=text
            )
            
            # Return the new session_id so the frontend can redirect
            return JsonResponse({
                'status': 'success', 
                'session_id': session.id
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
@login_required
def delete_chat_session(request, session_id):
    get_object_or_404(ChatSession, id=session_id, user=request.user).delete()
    return JsonResponse({'success': True})

@csrf_exempt
@login_required
def delete_document(request, doc_id):
    get_object_or_404(ChatDocument, id=doc_id, session__user=request.user).delete()
    return JsonResponse({'success': True})