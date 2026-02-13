from django.contrib import admin
from django.utils import timezone
from django.contrib.auth import get_user_model 
from .models import Notice, NoticeReadStatus, DirectMessage, Notification

# ==========================================
# 1. Custom Filters & Inlines (Preserved)
# ==========================================
class PendingApprovalFilter(admin.SimpleListFilter):
    title = 'Approval Status'
    parameter_name = 'is_approved'

    def lookups(self, request, model_admin):
        return (
            ('pending', '⏳ Needs Review'),
            ('approved', '✅ Published'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'pending':
            return queryset.filter(is_approved=False)
        if self.value() == 'approved':
            return queryset.filter(is_approved=True)

class NoticeReadInline(admin.TabularInline):
    model = NoticeReadStatus
    extra = 0
    can_delete = False
    readonly_fields = ('user', 'read_at')
    verbose_name = "Read Receipt"
    verbose_name_plural = "Student Read Receipts"


# ==========================================
# 2. Notice Admin (Updated with Approval)
# ==========================================
@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    # Added 'notifications_sent' to list_display
    list_display = ('title', 'created_by', 'status', 'is_approved', 'notifications_sent', 'get_read_count', 'deadline_status', 'created_at') 
    
    list_filter = (PendingApprovalFilter, 'status', 'is_approved', 'notifications_sent', 'expires_at', 'created_at')
    search_fields = ('title', 'message')
    
    # Added 'notifications_sent' to readonly_fields so you can see it but not break it
    fields = ('title', 'message', 'attachment', 'created_by', 'tags', 'status', 'is_approved', 'notifications_sent', 'rejection_reason', 'expires_at', 'who_has_read', 'who_has_not_read')
    readonly_fields = ('notifications_sent', 'who_has_read', 'who_has_not_read')

    inlines = [NoticeReadInline]
    
    # --- NEW ACTION: Approve Button ---
    actions = ['approve_notices']

    def approve_notices(self, request, queryset):
        # 1. Update status in database
        queryset.update(is_approved=True, status='approved')
        
        # 2. Trigger save() individually to fire the Notification Signal
        for notice in queryset:
            notice.save()
            
    approve_notices.short_description = "✅ Approve selected notices (Send Notifications)"
    # ----------------------------------

    def get_read_count(self, obj):
        return obj.read_statuses.count()
    get_read_count.short_description = 'Read By'

    def who_has_read(self, obj):
        students = obj.read_statuses.select_related('user').all()
        if not students:
            return "No students have read this yet."
        return ", ".join([s.user.username for s in students])
    who_has_read.short_description = 'Acknowledged Students'

    def who_has_not_read(self, obj):
        User = get_user_model()
        # Filter for strictly students (staff=False)
        all_students = User.objects.filter(is_staff=False)
        read_ids = obj.read_statuses.values_list('user_id', flat=True)
        unread_students = all_students.exclude(id__in=read_ids)

        if not unread_students.exists():
            return "✅ All students have seen this notice."
        
        return ", ".join([u.username for u in unread_students])
    who_has_not_read.short_description = 'Students Who Did Not See The Notice'

    def deadline_status(self, obj):
        if obj.expires_at:
            if obj.expires_at < timezone.now():
                return "⚠️ Date Passed"
            return "✅ Active"
        return "Permanent"
    deadline_status.short_description = 'Status'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('read_statuses')


# ==========================================
# 3. Notification Admin (New)
# ==========================================
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('recipient__username', 'message')


# ==========================================
# 4. Direct Message Admin (Preserved)
# ==========================================
@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ('student', 'admin', 'created_at', 'is_read')
    list_filter = ('is_read', 'created_at')
    search_fields = ('student__username', 'message')
    
    exclude = ('admin',)

    def render_change_form(self, request, context, *args, **kwargs):
        # Filter 'Student' dropdown to show ONLY students
        if 'adminform' in context:
             context['adminform'].form.fields['student'].queryset = get_user_model().objects.filter(is_staff=False)
        return super().render_change_form(request, context, *args, **kwargs)

    def save_model(self, request, obj, form, change):
        # Automatically set the Admin to the logged-in user
        if not obj.pk: 
            obj.admin = request.user
        super().save_model(request, obj, form, change)