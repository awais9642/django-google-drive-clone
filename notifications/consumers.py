import json
from channels.generic.websocket import AsyncWebsocketConsumer


class DriveConsumer(AsyncWebsocketConsumer):
    """
    One instance of this class is created per WebSocket connection.
    So if a user has 2 tabs open, there are 2 instances — both joined
    to the same Redis group. A broadcast to the group reaches all of them.

    Event types flowing through this consumer:

    From server → client (broadcast by views):
      - file_created     { id, name, size, created_at, folder_id }
      - file_deleted     { id, type: 'file' }
      - file_renamed     { id, name }
      - file_moved       { id }
      - folder_created   { id, name, created_at, parent_id }
      - folder_deleted   { id, type: 'folder' }
      - folder_renamed   { id, name }
      - folder_moved     { id }
      - notification     { message, notif_type: 'success'|'error'|'info', notif_id? }

    From client → server:
      (none for now — all actions go through regular Django views via fetch(),
       the WebSocket is receive-only from the client's perspective. This keeps
       auth/CSRF handling clean and in the normal Django request cycle.)
    """

    async def connect(self):
        user = self.scope['user']

        # Reject unauthenticated WebSocket connections immediately.
        # This can happen if someone opens a WS connection without a valid
        # session cookie (e.g. a tool trying to probe the endpoint).
        if not user.is_authenticated:
            await self.close()
            return

        # Each user gets their own Redis group. Group name must be a valid
        # Redis key — using user ID (integer) is safe and unique.
        self.group_name = f'user_{user.id}'

        # Join the group — now broadcasts to this group reach this connection
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave the group cleanly so Redis doesn't accumulate stale members
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        # We don't expect messages from the client right now, but we handle
        # the method so Channels doesn't raise an error if a client sends
        # something unexpected (e.g. a ping from some browsers/proxies).
        pass

    # -----------------------------------------------------------------------
    # Group message handlers
    # Each method name here maps to the 'type' key in the broadcast payload.
    # Channels calls the method matching type (dots replaced with underscores).
    # e.g. type='file.created' calls file_created()
    # -----------------------------------------------------------------------

    async def file_created(self, event):
        await self.send(text_data=json.dumps({
            'event': 'file_created',
            'data': event['data'],
        }))

    async def file_deleted(self, event):
        await self.send(text_data=json.dumps({
            'event': 'file_deleted',
            'data': event['data'],
        }))

    async def file_renamed(self, event):
        await self.send(text_data=json.dumps({
            'event': 'file_renamed',
            'data': event['data'],
        }))

    async def file_moved(self, event):
        await self.send(text_data=json.dumps({
            'event': 'file_moved',
            'data': event['data'],
        }))

    async def folder_created(self, event):
        await self.send(text_data=json.dumps({
            'event': 'folder_created',
            'data': event['data'],
        }))

    async def folder_deleted(self, event):
        await self.send(text_data=json.dumps({
            'event': 'folder_deleted',
            'data': event['data'],
        }))

    async def folder_renamed(self, event):
        await self.send(text_data=json.dumps({
            'event': 'folder_renamed',
            'data': event['data'],
        }))

    async def folder_moved(self, event):
        await self.send(text_data=json.dumps({
            'event': 'folder_moved',
            'data': event['data'],
        }))

    async def notification(self, event):
        await self.send(text_data=json.dumps({
            'event': 'notification',
            'data': event['data'],
        }))