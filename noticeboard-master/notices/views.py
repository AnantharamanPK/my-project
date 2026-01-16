from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Q
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from .models import Notice, User
from .forms import NewNoticeForm

# 1. MAIN LIST VIEW (Handles both normal view and the 'Search' button)
class NoticeListView(ListView):
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/home.html' # Make sure this file exists in your templates
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('q')
        if query:
            # Filters the main list when the Search button is clicked
            return Notice.objects.filter(
                Q(title__icontains=query) | 
                Q(message__icontains=query)
            ).distinct().order_by('-created_at')
        
        return Notice.objects.all().order_by('-created_at')

# 2. LIVE SEARCH FUNCTION (Handles typing suggestions)
def live_search(request):
    query = request.GET.get('q', '')
    if len(query) > 0:
        # Returns matching notices as JSON for the dropdown
        results = Notice.objects.filter(title__icontains=query)[:5]
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
        self.user = get_object_or_404(User, username=self.kwargs['user'])
        return Notice.objects.filter(created_by=self.user).order_by('-created_at')

# 4. FILTER BY TAGS
class TagView(LoginRequiredMixin, ListView):
    model = Notice
    context_object_name = 'notices'
    template_name = 'notices/tag.html'
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context_data = super().get_context_data(**kwargs)       
        context_data['tag'] = self.kwargs['tag']
        return context_data

    def get_queryset(self):
        return Notice.objects.filter(tags__icontains=self.kwargs['tag']+',').order_by('-created_at')

# 5. ALL TAGS LIST
@login_required
def TagListView(request):
    queryset = Notice.objects.filter(tags__isnull=False).values_list('tags', flat=True)
    tags = set(''.join(queryset).split(',')[:-1])
    return render(request, 'notices/tags.html', {'tags': tags})

# 6. SINGLE NOTICE DETAIL PAGE
@login_required
def NoticeView(request, notice_id):
    notice = get_object_or_404(Notice, id=notice_id)
    return render(request, 'notices/notice_page.html', {'notice': notice})

# 7. CREATE NEW NOTICE (Staff Only)
@staff_member_required
def NewNoticePage(request):
    if request.method == 'POST':
        form = NewNoticeForm(request.POST)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.created_by = request.user
            notice.save()
            return redirect('notices:notice_page', notice_id=notice.pk) 
    else:
        form = NewNoticeForm()
    return render(request, 'notices/new_notice.html', {'form': form})