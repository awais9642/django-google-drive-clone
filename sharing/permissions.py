from .models import SharedAccess


def get_file_permission(user, file_obj):
    """
    Returns the permission level a user has on a file:
        'owner'  — user owns the file
        'edit'   — shared with edit permission
        'view'   — shared with view permission
        None     — no access at all

    Always call this before allowing any file operation.
    """
    if file_obj.owner == user:
        return 'owner'

    try:
        access = SharedAccess.objects.get(file=file_obj, shared_with=user)
        return access.permission
    except SharedAccess.DoesNotExist:
        return None


def get_folder_permission(user, folder_obj):
    """
    Returns the permission level a user has on a folder.
    Same return values as get_file_permission.

    Note: folder sharing doesn't cascade to contents automatically in the
    DB — permission is checked per-item. Phase 6 views use this consistently
    so a shared folder's contents are accessible when navigating into it.
    """
    if folder_obj.owner == user:
        return 'owner'

    try:
        access = SharedAccess.objects.get(folder=folder_obj, shared_with=user)
        return access.permission
    except SharedAccess.DoesNotExist:
        return None


def can_view_file(user, file_obj):
    return get_file_permission(user, file_obj) is not None


def can_edit_file(user, file_obj):
    return get_file_permission(user, file_obj) in ('owner', 'edit')


def can_view_folder(user, folder_obj):
    return get_folder_permission(user, folder_obj) is not None


def can_edit_folder(user, folder_obj):
    return get_folder_permission(user, folder_obj) in ('owner', 'edit')