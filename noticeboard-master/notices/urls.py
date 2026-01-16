from django.urls import path
from . import views

app_name = 'notices'

urlpatterns = [
    # Main Home Page (Handles the Search results too)
    path('', views.NoticeListView.as_view(), name='home'),
    
    # AJAX Live Search (For the 'type-as-you-go' suggestions)
    path('live-search/', views.live_search, name='live_search'),
    
    # Notice Detail
    path('notices/<int:notice_id>/', views.NoticeView, name='notice_page'),
    
    # Create Notice
    path('notice/new/', views.NewNoticePage, name='new_notice'),
    
    # Filtering by Tags and Users
    path('tag/<str:tag>/', views.TagView.as_view(), name='tag'),
    path('tags/', views.TagListView, name='tags'),
    path('u/<str:user>/', views.UserNoticeListView.as_view(), name='user_notices'),
]