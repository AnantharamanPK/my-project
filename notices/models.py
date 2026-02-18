from django.db import models
from django.contrib.auth.models import User
from django.utils.html import mark_safe
from markdown import markdown
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from datetime import timedelta
import os

# ==========================================
# 1. NEW: User Profile (To store Department)
# ==========================================
class Profile(models.Model):
    DEPARTMENT_CHOICES = [
        ('MCA', 'MCA'),
        ('BTech', 'BTech'),
        ('MBA', 'MBA'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    department = models.CharField(max_length=10, choices=DEPARTMENT_CHOICES, default='MCA')

    def __str__(self):
        return f"{self.user.username} ({self.department})"

# Signal to ensure every User has a Profile automatically
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

# ==========================================
# 2. The Notice Model
# ==========================================
class Notice(models.Model):
    title = models.CharField(max_length=200)
    message = models.TextField()
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Target specific departments
    DEPARTMENT_TARGETS = [
        ('All', 'All Departments'),
        ('MCA', 'MCA'),
        ('BTech', 'BTech'),
        ('MBA', 'MBA'),
    ]
    target_department = models.CharField(
        max_length=10, 
        choices=DEPARTMENT_TARGETS, 
        default='All'
    )

    attachment = models.FileField(upload_to='notices/attachments/', null=True, blank=True)
    tags = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='notices', on_delete=models.CASCADE)

    notifications_sent = models.BooleanField(default=False)

    status = models.CharField(
        max_length=10, 
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending'
    )
    is_approved = models.BooleanField(default=False) 
    rejection_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title

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

    @property
    def is_archived(self):
        if self.expires_at:
            return timezone.now() >= self.expires_at
        return False

    @property
    def is_urgent(self):
        if self.expires_at:
            now = timezone.now()
            return now < self.expires_at <= now + timedelta(hours=24)
        return False

# ==========================================
# 3. Acknowledgement & Messages
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
    notice_reference = models.ForeignKey('Notice', on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

# ==========================================
# 4. The Notification System
# ==========================================
class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    related_notice = models.ForeignKey(Notice, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

# ==========================================
# 5. Multi-Step Notification Signal
# ==========================================
@receiver(post_save, sender=Notice)
def create_notice_notification(sender, instance, created, **kwargs):
    if created:
        # STAFF -> ADMIN
        admins = User.objects.filter(is_superuser=True)
        notifications = [
            Notification(
                recipient=admin,
                message=f"Approval Required: {instance.title} by @{instance.created_by.username}",
                related_notice=instance
            ) for admin in admins
        ]
        Notification.objects.bulk_create(notifications)

    elif instance.status == 'approved' and not instance.notifications_sent:
        # ADMIN -> STUDENTS (FILTERED BY DEPARTMENT)
        students = User.objects.filter(is_staff=False, is_superuser=False)
        
        # Only notify students in the target department
        if instance.target_department != 'All':
            students = students.filter(profile__department=instance.target_department)
        
        deadline_info = ""
        if instance.expires_at:
            deadline_info = f" | Deadline: {instance.expires_at.strftime('%d %b, %H:%M')}"
        
        notifications = [
            Notification(
                recipient=student,
                message=f"[{instance.target_department}] New Notice: {instance.title}{deadline_info}",
                related_notice=instance
            ) for student in students
        ]
        Notification.objects.bulk_create(notifications)
        
        # Use update to avoid re-triggering signals
        Notice.objects.filter(id=instance.id).update(notifications_sent=True)