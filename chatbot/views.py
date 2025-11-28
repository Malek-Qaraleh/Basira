from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
from .models import ChatSession, ChatMessage
from .ai import get_chat_response

@login_required
def chat_redirect(request):
    # Redirect to the most recent chat, or create a new one if none exist
    last_session = ChatSession.objects.filter(user=request.user).order_by('-created_at').first()
    if last_session:
        return redirect('chat_room', session_id=last_session.id)
    else:
        return redirect('create_session')

@login_required
def chat_room(request, session_id):
    # Get the requested session (securely)
    current_session = get_object_or_404(ChatSession, id=session_id, user=request.user)
    
    # Get ALL sessions for the sidebar history
    sessions = ChatSession.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'chatbot/room.html', {
        'current_session': current_session,
        'sessions': sessions
    })

@login_required
def create_session(request):
    # Simply create a new blank session for consultation
    session = ChatSession.objects.create(
        user=request.user, 
        title="New Consultation",
    )
    return redirect('chat_room', session_id=session.id)

@csrf_exempt
@login_required
def send_message(request, session_id):
    if request.method == 'POST':
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)
        try:
            data = json.loads(request.body)
            user_text = data.get('message')
            
            if not user_text:
                return JsonResponse({'error': 'Empty message'}, status=400)
            
            # 1. Save User Message
            ChatMessage.objects.create(session=session, role='user', content=user_text)
            
            # 2. Get AI Response (Consultant Mode)
            ai_text = get_chat_response(session, user_text)
            
            # 3. Save AI Message
            ChatMessage.objects.create(session=session, role='model', content=ai_text)
            
            # 4. Auto-Update title for better history
            if session.messages.count() <= 2 and session.title == "New Consultation":
                # Use first 5 words of user message as title
                new_title = " ".join(user_text.split()[:5]) + "..."
                session.title = new_title
                session.save()
            
            return JsonResponse({'response': ai_text})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)