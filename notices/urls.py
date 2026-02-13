from django.urls import path
from . import views

app_name = 'notices'

urlpatterns = [
    # Main Home Page
    path('', views.NoticeListView.as_view(), name='home'),
    
    # AJAX Live Search
    path('live-search/', views.live_search, name='live_search'),
    
    # Notice Detail
    path('view/<int:notice_id>/', views.NoticeView, name='notice_page'),
    
    # Create Notice
    path('new/', views.NewNoticePage, name='new_notice'),
    
    # Filtering and Explorer
    path('tags/', views.TagView.as_view(), name='tags'),
    path('tags/<str:tag>/', views.TagView.as_view(), name='tag'),
    path('user/<str:user>/', views.UserNoticeListView.as_view(), name='user_notices'),
    
    # Editing & Interaction
    path('edit/<int:notice_id>/', views.edit_notice, name='edit_notice'),
    path('mark-as-read/<int:notice_id>/', views.mark_as_read, name='mark_as_read'),
    path('mark-all-as-read/', views.mark_all_as_read, name='mark_all_as_read'),
    
    # Direct Messages
    path('message/dismiss/<int:message_id>/', views.dismiss_direct_message, name='dismiss_message'),

    # Notifications (Added this line here)
    path('notifications/clear/', views.clear_notifications, name='clear_notifications'),
]