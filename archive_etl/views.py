import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
import markdown
from .models import ResearchRequest
from .forms import ResearchForm
from .tasks import run_research_pipeline

@login_required
def research_dashboard(request):
    """
    Lists all research requests and displays the form to create a new one.
    """
    if request.method == 'POST':
        form = ResearchForm(request.POST)
        if form.is_valid():
            # 1. Save the request but don't commit yet (need user)
            req = form.save(commit=False)
            req.user = request.user
            req.save()
            
            # 2. Trigger the Celery Task
            run_research_pipeline.delay(req.id)
            
            return redirect('research_dashboard')
        
    else:
        form = ResearchForm()
    
    # Show user's history
    requests_history = ResearchRequest.objects.filter(user=request.user).order_by('-created_at')
        
    return render(request, 'archive_etl/dashboard.html', {
        'form': form, 
        'requests': requests_history
    })

@login_required
def request_detail(request, pk):
    """
    Shows the AI analysis results and the list of scraped articles.
    """
    req = get_object_or_404(ResearchRequest, pk=pk, user=request.user)
    
    # Convert the Markdown text to HTML in the view
    # 'extra' handles tables and better lists
    # 'nl2br' handles new lines without needing double spaces
    if req.thematic_analysis:
        formatted_analysis = markdown.markdown(
            req.thematic_analysis, 
            extensions=['extra', 'nl2br']
        )
    else:
        formatted_analysis = "No analysis available yet."

    return render(request, 'archive_etl/detail.html', {
        'req': req,
        'formatted_analysis': formatted_analysis
    })

@login_required
def export_research_csv(request, pk):
    """
    Downloads the scraped research data as a CSV file.
    """
    req = get_object_or_404(ResearchRequest, pk=pk, user=request.user)
    articles = req.articles.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="research_{pk}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Title', 'URL', 'Clean Text', 'Source', 'Scraped At'])
    
    for art in articles:
        writer.writerow([
            art.title, 
            art.url, 
            art.clean_text[:1000], # Truncate for CSV readability
            art.source.name if art.source else "Unknown",
            art.scraped_at
        ])
        
    return response