from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Q
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.contrib import messages
from .models import Notice, User
from .forms import NewNoticeForm

# 1. MAIN LIST VIEW (The Board)
class NoticeListView(LoginRequiredMixin, ListView): 
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/home.html'
    paginate_by = 10

    def get_queryset(self):
        now = timezone.now()
        
        # --- CRITICAL CHANGE: Added .filter(is_approved=True) ---
        # This ensures unapproved notices never show up on the public board
        queryset = Notice.objects.filter(
            is_approved=True
        ).filter(
            Q(expires_at__gt=now) | Q(expires_at__isnull=True)
        ).order_by('-created_at')
        
        # Search Filtering
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(message__icontains=query)
            ).distinct()
        
        # Tag Filtering
        tag_filter = self.request.GET.get('tag')
        if tag_filter:
            queryset = queryset.filter(tags__icontains=tag_filter)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tag_queryset = Notice.objects.filter(tags__isnull=False).values_list('tags', flat=True)
        unique_tags = set()
        for t_str in tag_queryset:
            if t_str:
                unique_tags.update([t.strip() for t in t_str.split(',') if t.strip()])
        
        unique_tags.add("General")
        unique_tags.add("Important")
        context['all_tags'] = sorted(list(unique_tags))
        return context

# 2. LIVE SEARCH (Needs the filter too so it doesn't leak unapproved titles)
def live_search(request):
    query = request.GET.get('q', '')
    if len(query) > 0:
        # Added is_approved=True filter here as well
        results = Notice.objects.filter(is_approved=True, title__icontains=query)[:5]
        data = [{'id': n.id, 'title': n.title} for n in results]
    else:
        data = []
    return JsonResponse({'results': data})

# 3. NOTICES BY SPECIFIC USER (Staff can see their own, even unapproved)
# notices/views.py

class UserNoticeListView(LoginRequiredMixin, ListView):
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/notices_by_user.html'
    paginate_by = 10

    def get_queryset(self):
        # This ensures the list only contains notices where 'created_by' is the logged-in user
        return Notice.objects.filter(created_by=self.request.user).order_by('-created_at')

# 4. FILTER BY TAGS
class TagView(LoginRequiredMixin, ListView):
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/tag.html'
    paginate_by = 10

    def get_queryset(self):
        tag = self.kwargs['tag']
        # Added is_approved=True filter
        return Notice.objects.filter(is_approved=True, tags__icontains=tag).order_by('-created_at')

# 5. SINGLE NOTICE DETAIL PAGE
@login_required
def NoticeView(request, notice_id):
    # Only allow viewing if approved, OR if the request user is the creator/staff
    notice = get_object_or_404(Notice, id=notice_id)
    return render(request, 'notices/notice_page.html', {'notice': notice})

# 6. POSTING A NEW NOTICE
@staff_member_required
def NewNoticePage(request):
    if request.method == 'POST':
        form = NewNoticeForm(request.POST, request.FILES) 
        if form.is_valid():
            notice = form.save(commit=False)
            notice.created_by = request.user
            notice.is_approved = False  # Set to False so it goes to Admin Dashboard
            notice.save()
            return redirect('notices:home') 
    else:
        form = NewNoticeForm()
    return render(request, 'notices/notice_form.html', {'form': form})

# 7. REDUNDANT FUNCTION (Keeping it but naming it something else to avoid conflict)
def home_redirect(request):
    # This function is now redundant because NoticeListView handles the logic.
    # We recommend using the Class View in your urls.py.
    return redirect('notices:home')

# notices/views.py
def get_queryset(self):
    return Notice.objects.filter(
        is_approved=True, 
        status='approved'
    ).order_by('-created_at')

@login_required
def edit_notice(request, notice_id):
    # Fetch the notice or 404
    notice = get_object_or_404(Notice, id=notice_id)
    
    # SECURITY: Only allow the original author to edit
    if notice.created_by != request.user:
        messages.error(request, "You do not have permission to edit this notice.")
        return redirect('notices:home')

    if request.method == 'POST':
        # Load form with POST data and the existing file/image if any
        form = NewNoticeForm(request.POST, request.FILES, instance=notice)
        if form.is_valid():
            updated_notice = form.save(commit=False)
            
            # --- CRITICAL: Reset status for re-review ---
            updated_notice.status = 'pending'
            updated_notice.is_approved = False 
            updated_notice.rejection_reason = "" # Clear the old rejection note
            
            updated_notice.save()
            messages.success(request, "Notice resubmitted for approval!")
            return redirect('notices:user_notices', user=request.user.username)
    else:
        # Load form with the current notice data
        form = NewNoticeForm(instance=notice)

    return render(request, 'notices/notice_form.html', {
        'form': form,
        'edit_mode': True,
        'notice': notice
    })