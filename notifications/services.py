from .models import Notification
from .broadcast import broadcast_to_user


def create_notification(recipient, message, notif_type, actor=None, link=''):
    """
    Creates a persisted Notification record and pushes it live to the
    recipient via WebSocket if they're currently connected.

    This is the single function all other parts of the app call to
    create notifications — sharing views, Celery tasks (Phase 9), etc.

    Args:
        recipient:   User who receives the notification
        message:     Human-readable notification text
        notif_type:  One of Notification.TYPE_* constants
        actor:       User who triggered the event (optional)
        link:        URL to navigate to when notification is clicked (optional)
    """
    notif = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notif_type=notif_type,
        message=message,
        link=link,
    )

    # Push live to recipient's open WebSocket connections
    # If they're offline this silently does nothing —
    # the notification is already persisted and will appear on next login
    _safe_broadcast(recipient.id, 'notification', {
        'id': notif.id,
        'message': message,
        'notif_type': _ui_type(notif_type),
        'link': link,
        'created_at': notif.created_at.strftime('%b %d, %H:%M'),
    })

    return notif


def _ui_type(notif_type):
    """Maps DB notif_type to frontend toast style."""
    return {
        Notification.TYPE_SHARE: 'info',
        Notification.TYPE_PERMISSION: 'info',
        Notification.TYPE_REVOKE: 'error',
        Notification.TYPE_SCHEDULED_DELETE: 'warning',
    }.get(notif_type, 'info')


def _safe_broadcast(user_id, event_type, data):
    try:
        broadcast_to_user(user_id, event_type, data)
    except Exception:
        pass