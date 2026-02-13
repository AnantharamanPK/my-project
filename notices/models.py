from django.db import models
from django.contrib.auth.models import User
from django.utils.html import mark_safe
from markdown import markdown
from django.utils import timezone
from datetime import timedelta  # <--- CRITICAL IMPORT FOR 24H CHECK
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
import os

# ==========================================
# 1. NOTICE MODEL
# ==========================================
class Notice(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # File Uploads
    attachment = models.FileField(upload_to='notices/attachments/', null=True, blank=True)
    
    # Tags
    tags = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='notices', on_delete=models.CASCADE)
    
    # Deadline / Expiry
    expires_at = models.DateTimeField(null=True, blank=True)

    # --- APPROVAL & STATUS FIELDS ---
    STATUS_CHOICES = [
        ('pending', 'Pending'), 
        ('approved', 'Approved'), 
        ('rejected', 'Rejected')
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    is_approved = models.BooleanField(default=False)  # Master switch for visibility
    rejection_reason = models.TextField(blank=True, null=True)
    
    # Prevents double notifications
    notifications_sent = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} ({self.status})"

    def get_message_as_markdown(self):
        return mark_safe(markdown(self.message, safe_mode='escape'))       

    def get_tags_as_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
        return []

    def is_image(self):
        if self.attachment:
            extension = os.path.splitext(self.attachment.name)[1].lower()
            return extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return False

    @property
    def is_active(self):
        if self.expires_at:
            return timezone.now() < self.expires_at
        return True

    # --- NEW HELPER: Check if deadline is within 24 hours ---
    @property
    def is_urgent(self):
        """
        Returns True if the deadline is active AND is less than 24 hours away.
        """
        if not self.expires_at:
            return False
        now = timezone.now()
        # Logic: Current time < Deadline <= Current time + 24 hours
        return now < self.expires_at <= now + timedelta(hours=24)


# ==========================================
# 2. NOTIFICATION MODEL
# ==========================================
class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_notice = models.ForeignKey(Notice, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.message}"


# ==========================================
# 3. READ STATUS & MESSAGES
# ==========================================
class NoticeReadStatus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notice = models.ForeignKey(Notice, on_delete=models.CASCADE, related_name='read_statuses')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'notice')

class DirectMessage(models.Model):
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    notice_reference = models.ForeignKey(Notice, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"To {self.student.username}: {self.message[:30]}..."


# ==========================================
# 4. SIGNALS (Automation Logic)
# ==========================================
@receiver(post_save, sender=Notice)
def handle_notice_notifications(sender, instance, created, **kwargs):
    
    # CASE 1: Staff creates a notice (Pending) -> Notify Admin
    if created and not instance.is_approved:
        # Find all Superusers (Admins)
        admins = User.objects.filter(is_superuser=True)
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                message=f"APPROVAL NEEDED: '{instance.title}' by {instance.created_by.username}",
                related_notice=instance
            )

    # CASE 2: Admin approves notice -> Notify Students
    if instance.is_approved and not instance.notifications_sent:
        
        # Send to all users except the creator and admins
        recipients = User.objects.exclude(id=instance.created_by.id).exclude(is_superuser=True)
        
        notifications_to_create = []
        for user in recipients:
            notifications_to_create.append(
                Notification(
                    recipient=user,
                    message=f"New Notice: {instance.title}",
                    related_notice=instance
                )
            )
        Notification.objects.bulk_create(notifications_to_create)

        # Mark as sent so we don't spam students if you edit the notice later
        Notice.objects.filter(pk=instance.pk).update(notifications_sent=True)