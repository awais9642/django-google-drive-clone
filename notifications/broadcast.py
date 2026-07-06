from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_to_user(user_id: int, event_type: str, data: dict):
    """
    Sends a real-time event to ALL WebSocket connections for a given user.

    This is a synchronous function (safe to call from regular Django views),
    but it internally calls the async channel layer via async_to_sync().

    Args:
        user_id:    The owner whose connected tabs should receive this event.
        event_type: Matches a handler method in DriveConsumer.
                    Use dot notation: 'file.deleted', 'folder.created', etc.
                    Channels converts 'file.deleted' → calls file_deleted()
        data:       The payload dict sent to the frontend JS handler.

    Example:
        broadcast_to_user(
            user_id=request.user.id,
            event_type='file.deleted',
            data={'id': file_obj.id, 'type': 'file'}
        )
    """
    channel_layer = get_channel_layer()
    group_name = f'user_{user_id}'

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': event_type,   # Channels maps this to a consumer method
            'data': data,
        }
    )