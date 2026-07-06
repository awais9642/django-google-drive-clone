from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from drive.models import File, Folder
from accounts.models import User
from .models import SharedAccess
from .permissions import get_file_permission, get_folder_permission
from notifications.broadcast import broadcast_to_user
from notifications.services import create_notification
from notifications.models import Notification


def _json_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


# ---------------------------------------------------------------------------
# User search (for the share modal autocomplete)
# ---------------------------------------------------------------------------

@login_required
@require_GET
def user_search(request):
    """
    Search registered users by username or email.
    Excludes the requesting user (can't share with yourself).
    Returns up to 10 matches.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'users': []})

    users = User.objects.filter(
        username__icontains=query
    ).exclude(
        id=request.user.id
    ).values('id', 'username', 'email')[:10]

    # Also search by email
    email_users = User.objects.filter(
        email__icontains=query
    ).exclude(
        id=request.user.id
    ).values('id', 'username', 'email')[:10]

    # Merge and deduplicate
    seen_ids = set()
    results = []
    for u in list(users) + list(email_users):
        if u['id'] not in seen_ids:
            seen_ids.add(u['id'])
            results.append(u)

    return JsonResponse({'users': results[:10]})


# ---------------------------------------------------------------------------
# Share an item
# ---------------------------------------------------------------------------

@login_required
@require_POST
def share_item(request):
    """
    Creates a SharedAccess record.
    Expects POST: item_type, item_id, shared_with_id, permission
    Owner-only — you can only share items you own.
    """
    item_type = request.POST.get('item_type')
    item_id = request.POST.get('item_id')
    shared_with_id = request.POST.get('shared_with_id')
    permission = request.POST.get('permission', SharedAccess.PERMISSION_VIEW)

    if item_type not in ('file', 'folder'):
        return _json_error('Invalid item type.')

    if permission not in (SharedAccess.PERMISSION_VIEW, SharedAccess.PERMISSION_EDIT):
        return _json_error('Invalid permission level.')

    # Resolve the target item — must be owned by the requester
    if item_type == 'file':
        item = get_object_or_404(File, pk=item_id, owner=request.user, is_deleted=False)
    else:
        item = get_object_or_404(Folder, pk=item_id, owner=request.user, is_deleted=False)

    # Resolve the target user
    try:
        shared_with = User.objects.get(pk=shared_with_id)
    except User.DoesNotExist:
        return _json_error('User not found.')

    if shared_with == request.user:
        return _json_error('You cannot share with yourself.')

    # Build the SharedAccess record
    access = SharedAccess(
        shared_with=shared_with,
        shared_by=request.user,
        permission=permission,
    )
    if item_type == 'file':
        access.file = item
    else:
        access.folder = item

    try:
        access.full_clean()
        access.save()
    except (ValidationError, IntegrityError):
        return _json_error(
            f'This {item_type} is already shared with {shared_with.username}.'
        )

    # --- Notify the recipient via WebSocket (Phase 5 infrastructure)   
    # broadcast_to_user(
    #     shared_with.id,
    #     'notification',
    #     {
    #         'message': f'{request.user.username} shared a {item_type} "{item.name}" with you.',
    #         'notif_type': 'info',
    #     }
    # )
 
    # --- Persist a Notification record (Phase 7 will fully build this out) ---
    # We call it here so the notification exists even if the user wasn't online.
    create_notification(
        recipient=shared_with,
    message=f'{request.user.username} shared {item_type} "{item.name}" with you.',
    notif_type=Notification.TYPE_SHARE,
    actor=request.user,
    link=f'/folder/{item.id}/' if item_type == 'folder' else f'/file/{item.id}/view/',
    )

    # --- Trigger email (Phase 8 implements this — stub call for now) ---
    _send_share_email(
        shared_by=request.user,
        shared_with=shared_with,
        item=item,
        item_type=item_type,
        permission=permission,
    )

    return JsonResponse({
        'success': True,
        'access': {
            'id': access.id,
            'shared_with': shared_with.username,
            'permission': access.permission,
        }
    })


# ---------------------------------------------------------------------------
# List who has access to an item
# ---------------------------------------------------------------------------

@login_required
@require_GET
def list_access(request):
    """
    Returns all SharedAccess records for a given item.
    Owner-only.
    """
    item_type = request.GET.get('item_type')
    item_id = request.GET.get('item_id')

    if item_type == 'file':
        item = get_object_or_404(File, pk=item_id, owner=request.user, is_deleted=False)
        accesses = SharedAccess.objects.filter(file=item).select_related('shared_with')
    elif item_type == 'folder':
        item = get_object_or_404(Folder, pk=item_id, owner=request.user, is_deleted=False)
        accesses = SharedAccess.objects.filter(folder=item).select_related('shared_with')
    else:
        return _json_error('Invalid item type.')

    return JsonResponse({
        'accesses': [
            {
                'id': a.id,
                'shared_with': a.shared_with.username,
                'shared_with_email': a.shared_with.email,
                'permission': a.permission,
                'created_at': a.created_at.strftime('%b %d, %Y'),
            }
            for a in accesses
        ]
    })


# ---------------------------------------------------------------------------
# Update permission level
# ---------------------------------------------------------------------------

@login_required
@require_POST
def update_permission(request, access_id):
    access = get_object_or_404(SharedAccess, pk=access_id)

    # Verify the requester owns the item being shared
    owner = access.file.owner if access.file else access.folder.owner
    if owner != request.user:
        return _json_error('Permission denied.', status=403)

    permission = request.POST.get('permission')
    if permission not in (SharedAccess.PERMISSION_VIEW, SharedAccess.PERMISSION_EDIT):
        return _json_error('Invalid permission level.')

    access.permission = permission
    access.save(update_fields=['permission'])

    create_notification(
    recipient=access.shared_with,
    message=f'{request.user.username} changed your access to "{access.item.name}" to {permission}.',
    notif_type=Notification.TYPE_PERMISSION,
    actor=request.user,
    )

    _safe_broadcast(
        access.shared_with.id,
        'notification',
        {
            'message': f'{request.user.username} changed your access to "{access.item.name}" to {permission}.',
            'notif_type': 'info',
        }
    )

    return JsonResponse({'success': True, 'permission': access.permission})


# ---------------------------------------------------------------------------
# Revoke access
# ---------------------------------------------------------------------------

@login_required
@require_POST
def revoke_access(request, access_id):
    """
    Deletes a SharedAccess record. Owner-only.
    """
    access = get_object_or_404(SharedAccess, pk=access_id)

    owner = access.file.owner if access.file else access.folder.owner
    if owner != request.user:
        return _json_error('Permission denied.', status=403)

    username = access.shared_with.username
    item_name = access.item.name
    shared_with_id = access.shared_with.id

    access.delete()

    create_notification(
    recipient=User.objects.get(pk=shared_with_id),
    message=f'{request.user.username} removed your access to "{item_name}".',
    notif_type=Notification.TYPE_REVOKE,
    actor=request.user,
    )

    broadcast_to_user(
        shared_with_id,
        'notification',
        {
            'message': f'{request.user.username} removed your access to "{item_name}".',
            'notif_type': 'info',
        }
    )

    return JsonResponse({'success': True})


# ---------------------------------------------------------------------------
# Shared with me page
# ---------------------------------------------------------------------------

@login_required
def shared_with_me(request):
    """
    Shows all files and folders shared with the current user.
    """
    file_shares = SharedAccess.objects.filter(
        shared_with=request.user,
        file__isnull=False,
        file__is_deleted=False,
    ).select_related('file', 'shared_by')

    folder_shares = SharedAccess.objects.filter(
        shared_with=request.user,
        folder__isnull=False,
        folder__is_deleted=False,
    ).select_related('folder', 'shared_by')

    return render(request, 'sharing/shared_with_me.html', {
        'file_shares': file_shares,
        'folder_shares': folder_shares,
    })


# ---------------------------------------------------------------------------
# Stubs for Phase 8 (email) and Phase 7 (notifications)
# These are called now so the wiring exists; implemented in their phases.
# ---------------------------------------------------------------------------

def _send_share_email(shared_by, shared_with, item, item_type, permission):
    """
    Fires a Celery task to send the share email asynchronously.
    The view returns immediately — email sends in the background.
    All arguments are passed as primitives (strings) not ORM objects,
    because Celery serializes task args to JSON.
    """
    from sharing.tasks import send_share_email

    # Build the access link
    if item_type == 'folder':
        link = f'http://127.0.0.1:8000/folder/{item.id}/'
    else:
        link = f'http://127.0.0.1:8000/'

    send_share_email.delay(
        shared_by_name=shared_by.username,
        shared_with_email=shared_with.email,
        shared_with_name=shared_with.username,
        item_type=item_type,
        item_name=item.name,
        permission=permission,
        access_link=link,
    )


# def _create_notification(recipient, actor, verb, item_type, item_name, item_id):
#     pass 