from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Q
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.contrib import messages
from .models import Notice, User, NoticeReadStatus, DirectMessage # Added DirectMessage
from .forms import NewNoticeForm
from django.db import transaction
# In notices/views.py

from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from .models import Notification


def clear_notifications(request):
    # Delete all notifications for the current user
    Notification.objects.filter(recipient=request.user).delete()
    # Reload the page the user was currently on
    return redirect(request.META.get('HTTP_REFERER', 'notices:home'))

# 1. MAIN LIST VIEW (The Board)
class NoticeListView(LoginRequiredMixin, ListView): 
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/home.html'
    paginate_by = 10

    def get_queryset(self):
        now = timezone.now()
        queryset = Notice.objects.filter(
            is_approved=True
        ).filter(
            Q(expires_at__gt=now) | Q(expires_at__isnull=True)
        ).order_by('-created_at')
        
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query) | 
                Q(message__icontains=query)
            ).distinct()
        
        tag_filter = self.request.GET.get('tag')
        if tag_filter:
            queryset = queryset.filter(tags__icontains=tag_filter)
            
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # --- CRITICAL FIX FOR YOUR BUTTONS ---
        if user.is_authenticated:
            # 1. Get IDs of notices the student HAS already read
            context['read_notice_ids'] = NoticeReadStatus.objects.filter(
                user=user
            ).values_list('notice_id', flat=True)
            
            # 2. Get unread Direct Messages from Admin
            context['direct_messages'] = DirectMessage.objects.filter(
                student=user, 
                is_read=False
            )
        
        # Tag logic
        tag_queryset = Notice.objects.filter(tags__isnull=False).values_list('tags', flat=True)
        unique_tags = set()
        for t_str in tag_queryset:
            if t_str:
                unique_tags.update([t.strip() for t in t_str.split(',') if t.strip()])
        
        unique_tags.add("General")
        unique_tags.add("Important")
        context['all_tags'] = sorted(list(unique_tags))
        return context

# 2. LIVE SEARCH
def live_search(request):
    query = request.GET.get('q', '')
    if len(query) > 0:
        results = Notice.objects.filter(is_approved=True, title__icontains=query)[:5]
        data = [{'id': n.id, 'title': n.title} for n in results]
    else:
        data = []
    return JsonResponse({'results': data})

# 3. NOTICES BY SPECIFIC USER
class UserNoticeListView(LoginRequiredMixin, ListView):
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/notices_by_user.html'
    paginate_by = 10

    def get_queryset(self):
        return Notice.objects.filter(created_by=self.request.user).order_by('-created_at')

# 4. FILTER BY TAGS
class TagView(LoginRequiredMixin, ListView):
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/tag.html'
    paginate_by = 10

    def get_queryset(self):
        tag = self.kwargs['tag']
        return Notice.objects.filter(is_approved=True, tags__icontains=tag).order_by('-created_at')

# 5. SINGLE NOTICE DETAIL PAGE
@login_required
def NoticeView(request, notice_id):
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
            notice.is_approved = False 
            notice.save()
            return redirect('notices:home') 
    else:
        form = NewNoticeForm()
    return render(request, 'notices/notice_form.html', {'form': form})

# 7. REDUNDANT REDIRECT
def home_redirect(request):
    return redirect('notices:home')

# 8. EDIT NOTICE
@login_required
def edit_notice(request, notice_id):
    notice = get_object_or_404(Notice, id=notice_id)
    if notice.created_by != request.user:
        messages.error(request, "You do not have permission to edit this notice.")
        return redirect('notices:home')

    if request.method == 'POST':
        form = NewNoticeForm(request.POST, request.FILES, instance=notice)
        if form.is_valid():
            updated_notice = form.save(commit=False)
            updated_notice.status = 'pending'
            updated_notice.is_approved = False 
            updated_notice.rejection_reason = "" 
            updated_notice.save()
            messages.success(request, "Notice resubmitted for approval!")
            return redirect('notices:home')
    else:
        form = NewNoticeForm(instance=notice)
    return render(request, 'notices/notice_form.html', {'form': form, 'edit_mode': True, 'notice': notice})

# 9. MARK AS READ (Single)
@login_required
def mark_as_read(request, notice_id):
    if request.method == 'POST':
        notice = get_object_or_404(Notice, id=notice_id)
        NoticeReadStatus.objects.get_or_create(user=request.user, notice=notice)
    return redirect('notices:home')

# 10. MARK ALL AS READ (Bulk)
@login_required
def mark_all_as_read(request):
    if request.method == 'POST':
        all_notices = Notice.objects.filter(is_approved=True)
        read_notice_ids = NoticeReadStatus.objects.filter(
            user=request.user
        ).values_list('notice_id', flat=True)
        
        unread_notices = all_notices.exclude(id__in=read_notice_ids)
        
        with transaction.atomic():
            for notice in unread_notices:
                NoticeReadStatus.objects.get_or_create(user=request.user, notice=notice)
    return redirect('notices:home')

# notices/views.py

@login_required
def dismiss_direct_message(request, message_id):
    if request.method == 'POST':
        # Find the message meant for THIS student
        msg = get_object_or_404(DirectMessage, id=message_id, student=request.user)
        msg.is_read = True
        msg.save()
    return redirect('notices:home')