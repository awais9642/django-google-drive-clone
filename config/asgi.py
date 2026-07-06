"""
ASGI config for the drive_clone project.

Django Channels replaces Django's standard WSGI server with an ASGI server
that handles both HTTP requests (same as before) AND WebSocket connections.
The URLRouter here decides which connections go to Channels consumers vs
the regular Django HTTP handler.
"""

import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from notifications.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # All normal HTTP traffic continues to go through Django as before
    'http': get_asgi_application(),

    # WebSocket traffic is routed through AuthMiddlewareStack (so we know
    # which user is connecting) then URLRouter (to match to a consumer)
    'websocket': AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})