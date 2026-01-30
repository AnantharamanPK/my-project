# notices/admin.py
from django.contrib import admin
from .models import Notice

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

@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    # Update this list to match exactly what is in your models.py
    list_display = ('title', 'created_by', 'status', 'is_approved', 'created_at') 
    list_filter = ('status', 'is_approved', 'created_at')
    search_fields = ('title', 'message')
    # This allows you to edit the status and reason directly in the detail view
    fields = ('title', 'message', 'created_by', 'tags', 'status', 'is_approved', 'rejection_reason', 'expires_at')