from django.db import models
from django.contrib.auth.models import User
from django.utils.html import mark_safe
from markdown import markdown
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import os




class Notice(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    xpires_at = models.DateTimeField(null=True, blank=True) # ADD THIS LINE
    
    # 1. File Upload Field (Photos/PDFs)
    attachment = models.FileField(upload_to='notices/attachments/', null=True, blank=True)
    
    # 2. Existing Tags Field (Stored as a comma-separated string)
    tags = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # 3. Relationship to User (CASCADE means if user is deleted, notices are too)
    created_by = models.ForeignKey(User, related_name='notices', on_delete=models.CASCADE)

    def __str__(self):
        return self.title

    # Helper for rendering Markdown content
    def get_message_as_markdown(self):
        return mark_safe(markdown(self.message, safe_mode='escape'))       

    # Helper to convert "Important, General" string into a list for the frontend
    def get_tags_as_list(self):
        if self.tags:
            # Splits by comma and removes empty strings
            return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
        return []

    # Helper to detect if the attachment is an image for the template
    def is_image(self):
        if self.attachment:
            extension = os.path.splitext(self.attachment.name)[1].lower()
            return extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return False
    
    # ... your existing fields (title, message, etc.) ...
    expires_at = models.DateTimeField(null=True, blank=True) # ADD THIS LINE
    
    @property
    def is_active(self):
        if self.expires_at:
            return timezone.now() < self.expires_at
        return True
    
    status = models.CharField(
        max_length=10, 
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending'
    )
    # If you still want the checkbox, keep this line. 
    # If you removed it to use 'status' only, delete it from admin.py too.
    is_approved = models.BooleanField(default=False) 
    rejection_reason = models.TextField(blank=True, null=True)

class NoticeReadStatus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # The related_name MUST be 'read_statuses' to match your admin.py
    notice = models.ForeignKey(
        Notice, 
        on_delete=models.CASCADE, 
        related_name='read_statuses'
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'notice')
    
    # notices/models.py
from django.db import models
from django.contrib.auth.models import User

# ... your existing Notice and NoticeReadStatus models ...

class DirectMessage(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    notice_reference = models.ForeignKey('Notice', on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"To {self.student.username}: {self.message[:30]}..."
    
    