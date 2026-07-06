from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET

from .models import Notification


@login_required
@require_GET
def notification_list(request):
    """
    Returns the 20 most recent notifications for the current user.
    Called when the bell dropdown opens.
    """
    notifications = Notification.objects.filter(
        recipient=request.user
    ).select_related('actor')[:20]

    return JsonResponse({
        'notifications': [
            {
                'id': n.id,
                'message': n.message,
                'notif_type': n.notif_type,
                'is_read': n.is_read,
                'link': n.link,
                'created_at': n.created_at.strftime('%b %d, %H:%M'),
            }
            for n in notifications
        ]
    })


@login_required
@require_GET
def unread_count(request):
    """
    Returns the count of unread notifications.
    Called on page load to initialize the badge.
    """
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return JsonResponse({'count': count})


@login_required
@require_POST
def mark_read(request, notif_id):
    """Marks a single notification as read."""
    try:
        notif = Notification.objects.get(pk=notif_id, recipient=request.user)
        notif.mark_read()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found.'}, status=404)


@login_required
@require_POST
def mark_all_read(request):
    """Marks all unread notifications as read."""
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)
    return JsonResponse({'success': True})