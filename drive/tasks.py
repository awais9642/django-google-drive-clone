from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def scheduled_file_delete(self, file_id):
    """
    Fires at the exact eta time set when the task was queued.
    Permanently deletes the file from disk and DB, broadcasts
    the deletion to all open tabs, and notifies the owner.

    Arguments are primitives (file_id int) not ORM objects —
    Celery serializes args to JSON and the file must be looked
    up fresh at execution time, not at scheduling time.
    """
    from drive.models import File
    from notifications.services import create_notification
    from notifications.models import Notification
    from notifications.broadcast import broadcast_to_user

    try:
        file_obj = File.objects.get(pk=file_id)
    except File.DoesNotExist:
        # File was already deleted manually — nothing to do, not an error
        return f'File {file_id} already deleted, skipping.'

    # Verify it still has a scheduled deletion time set.
    # If the user cancelled the schedule after the task was queued,
    # scheduled_delete_at will be None and we should abort.
    if file_obj.scheduled_delete_at is None:
        return f'File {file_id} schedule was cancelled, skipping.'

    owner = file_obj.owner
    file_name = file_obj.name
    folder_id = file_obj.folder_id

    # Hard delete — removes from disk and DB
    try:
        file_obj.hard_delete()
    except Exception as exc:
        raise self.retry(exc=exc)

    # Broadcast real-time deletion to all open tabs for this user
    try:
        broadcast_to_user(owner.id, 'file.deleted', {
            'id': file_id,
            'type': 'file',
        })
    except Exception:
        pass  # Non-fatal — file is deleted, real-time update is best-effort

    # Persist a notification so the owner knows what happened
    create_notification(
        recipient=owner,
        message=f'"{file_name}" was automatically deleted as scheduled.',
        notif_type=Notification.TYPE_SCHEDULED_DELETE,
        link=f'/folder/{folder_id}/' if folder_id else '/',
    )

    return f'File {file_id} ({file_name}) deleted successfully.'