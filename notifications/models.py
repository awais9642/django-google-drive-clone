from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    Persisted notification record. Created server-side on share/permission/
    scheduled-deletion events. Delivered live via WebSocket if the recipient
    is online; visible in the bell dropdown whether they were online or not.
    """

    TYPE_SHARE = 'share'
    TYPE_PERMISSION = 'permission'
    TYPE_REVOKE = 'revoke'
    TYPE_SCHEDULED_DELETE = 'scheduled_delete'

    TYPE_CHOICES = [
        (TYPE_SHARE, 'File/folder shared with you'),
        (TYPE_PERMISSION, 'Permission changed'),
        (TYPE_REVOKE, 'Access revoked'),
        (TYPE_SCHEDULED_DELETE, 'Scheduled deletion reminder'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sent_notifications',
    )
    notif_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional link — where clicking the notification should take the user
    link = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'→ {self.recipient.username}: {self.message[:50]}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])