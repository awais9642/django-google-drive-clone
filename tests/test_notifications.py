"""
Integration tests for the notification system.
Tests the notification service, views (list, unread count,
mark read, mark all read), and persistence behavior.
"""

import pytest
from django.urls import reverse

from notifications.models import Notification
from notifications.services import create_notification
from .factories import UserFactory, NotificationFactory, FileFactory


@pytest.fixture
def auth_client(client):
    user = UserFactory()
    client.force_login(user)
    client.user = user
    return client


@pytest.mark.django_db
class TestNotificationService:

    def test_create_notification_persists(self):
        recipient = UserFactory()
        actor = UserFactory()

        notif = create_notification(
            recipient=recipient,
            message='Test message',
            notif_type=Notification.TYPE_SHARE,
            actor=actor,
            link='/folder/1/',
        )

        assert notif.pk is not None
        assert Notification.objects.filter(pk=notif.pk).exists()

    def test_create_notification_correct_fields(self):
        recipient = UserFactory()
        actor = UserFactory()

        notif = create_notification(
            recipient=recipient,
            message='shared a file with you',
            notif_type=Notification.TYPE_SHARE,
            actor=actor,
            link='/folder/5/',
        )

        assert notif.recipient == recipient
        assert notif.actor == actor
        assert notif.notif_type == Notification.TYPE_SHARE
        assert notif.is_read is False
        assert notif.link == '/folder/5/'

    def test_notification_created_on_share(self, auth_client):
        """Sharing a file should create a notification for the recipient."""
        recipient = UserFactory()
        file_obj = FileFactory(owner=auth_client.user)

        auth_client.post(reverse('sharing:share_item'), {
            'item_type': 'file',
            'item_id': file_obj.id,
            'shared_with_id': recipient.id,
            'permission': 'view',
        })

        assert Notification.objects.filter(
            recipient=recipient,
            notif_type=Notification.TYPE_SHARE,
        ).exists()


@pytest.mark.django_db
class TestNotificationViews:

    def test_notification_list_returns_json(self, auth_client):
        NotificationFactory(recipient=auth_client.user)
        NotificationFactory(recipient=auth_client.user)

        response = auth_client.get(reverse('notifications:list'))
        assert response.status_code == 200
        data = response.json()
        assert 'notifications' in data
        assert len(data['notifications']) == 2

    def test_notification_list_only_shows_own(self, auth_client):
        other_user = UserFactory()
        NotificationFactory(recipient=other_user)      # someone else's
        NotificationFactory(recipient=auth_client.user)  # mine

        response = auth_client.get(reverse('notifications:list'))
        data = response.json()
        assert len(data['notifications']) == 1

    def test_unread_count_correct(self, auth_client):
        NotificationFactory(recipient=auth_client.user, is_read=False)
        NotificationFactory(recipient=auth_client.user, is_read=False)
        NotificationFactory(recipient=auth_client.user, is_read=True)

        response = auth_client.get(reverse('notifications:unread_count'))
        data = response.json()
        assert data['count'] == 2

    def test_unread_count_zero_when_all_read(self, auth_client):
        NotificationFactory(recipient=auth_client.user, is_read=True)

        response = auth_client.get(reverse('notifications:unread_count'))
        data = response.json()
        assert data['count'] == 0

    def test_mark_single_notification_read(self, auth_client):
        notif = NotificationFactory(recipient=auth_client.user, is_read=False)

        response = auth_client.post(
            reverse('notifications:mark_read', args=[notif.id])
        )
        data = response.json()
        assert data['success'] is True
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_cannot_mark_other_users_notification_read(self, auth_client):
        other_user = UserFactory()
        notif = NotificationFactory(recipient=other_user, is_read=False)

        response = auth_client.post(
            reverse('notifications:mark_read', args=[notif.id])
        )
        assert response.status_code == 404
        notif.refresh_from_db()
        assert notif.is_read is False  # unchanged

    def test_mark_all_read(self, auth_client):
        NotificationFactory(recipient=auth_client.user, is_read=False)
        NotificationFactory(recipient=auth_client.user, is_read=False)
        NotificationFactory(recipient=auth_client.user, is_read=False)

        response = auth_client.post(reverse('notifications:mark_all_read'))
        data = response.json()
        assert data['success'] is True

        unread = Notification.objects.filter(
            recipient=auth_client.user, is_read=False
        ).count()
        assert unread == 0

    def test_mark_all_read_only_affects_own(self, auth_client):
        other_user = UserFactory()
        other_notif = NotificationFactory(recipient=other_user, is_read=False)

        auth_client.post(reverse('notifications:mark_all_read'))

        other_notif.refresh_from_db()
        assert other_notif.is_read is False  # untouched

    def test_notification_list_max_20(self, auth_client):
        for _ in range(25):
            NotificationFactory(recipient=auth_client.user)

        response = auth_client.get(reverse('notifications:list'))
        data = response.json()
        assert len(data['notifications']) == 20

    def test_unauthenticated_redirected(self, client):
        response = client.get(reverse('notifications:list'))
        assert response.status_code == 302