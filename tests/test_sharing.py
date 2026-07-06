"""
Integration tests for the sharing system.
Tests share creation, permission updates, revocation,
and the shared-with-me page.
"""

import pytest
from django.urls import reverse

from sharing.models import SharedAccess
from .factories import UserFactory, FileFactory, FolderFactory, SharedAccessFactory


@pytest.fixture
def owner_client(client):
    user = UserFactory()
    client.force_login(user)
    client.user = user
    return client


@pytest.mark.django_db
class TestShareItem:

    def test_share_file_with_user(self, owner_client):
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner_client.user)

        response = owner_client.post(reverse('sharing:share_item'), {
            'item_type': 'file',
            'item_id': file_obj.id,
            'shared_with_id': recipient.id,
            'permission': 'view',
        })
        data = response.json()
        assert data['success'] is True
        assert SharedAccess.objects.filter(
            file=file_obj, shared_with=recipient
        ).exists()

    def test_share_folder_with_user(self, owner_client):
        recipient = UserFactory()
        folder = FolderFactory(owner=owner_client.user)

        response = owner_client.post(reverse('sharing:share_item'), {
            'item_type': 'folder',
            'item_id': folder.id,
            'shared_with_id': recipient.id,
            'permission': 'edit',
        })
        data = response.json()
        assert data['success'] is True
        access = SharedAccess.objects.get(folder=folder, shared_with=recipient)
        assert access.permission == 'edit'

    def test_cannot_share_with_yourself(self, owner_client):
        file_obj = FileFactory(owner=owner_client.user)

        response = owner_client.post(reverse('sharing:share_item'), {
            'item_type': 'file',
            'item_id': file_obj.id,
            'shared_with_id': owner_client.user.id,
            'permission': 'view',
        })
        data = response.json()
        assert data['success'] is False

    def test_cannot_share_another_users_file(self, owner_client):
        other_owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=other_owner)

        response = owner_client.post(reverse('sharing:share_item'), {
            'item_type': 'file',
            'item_id': file_obj.id,
            'shared_with_id': recipient.id,
            'permission': 'view',
        })
        assert response.status_code == 404

    def test_duplicate_share_returns_error(self, owner_client):
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner_client.user)
        SharedAccessFactory(
            file=file_obj,
            shared_by=owner_client.user,
            shared_with=recipient,
        )

        response = owner_client.post(reverse('sharing:share_item'), {
            'item_type': 'file',
            'item_id': file_obj.id,
            'shared_with_id': recipient.id,
            'permission': 'view',
        })
        data = response.json()
        assert data['success'] is False
        assert 'already shared' in data['error'].lower()

    def test_invalid_permission_rejected(self, owner_client):
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner_client.user)

        response = owner_client.post(reverse('sharing:share_item'), {
            'item_type': 'file',
            'item_id': file_obj.id,
            'shared_with_id': recipient.id,
            'permission': 'superadmin',  # invalid
        })
        data = response.json()
        assert data['success'] is False


@pytest.mark.django_db
class TestUpdatePermission:

    def test_update_permission(self, owner_client):
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner_client.user)
        access = SharedAccessFactory(
            file=file_obj,
            shared_by=owner_client.user,
            shared_with=recipient,
            permission='view',
        )

        response = owner_client.post(
            reverse('sharing:update_permission', args=[access.id]),
            {'permission': 'edit'},
        )
        data = response.json()
        assert data['success'] is True
        access.refresh_from_db()
        assert access.permission == 'edit'

    def test_non_owner_cannot_update_permission(self, owner_client):
        other_owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=other_owner)
        access = SharedAccessFactory(
            file=file_obj,
            shared_by=other_owner,
            shared_with=recipient,
            permission='view',
        )

        response = owner_client.post(
            reverse('sharing:update_permission', args=[access.id]),
            {'permission': 'edit'},
        )
        data = response.json()
        assert data['success'] is False


@pytest.mark.django_db
class TestRevokeAccess:

    def test_revoke_access(self, owner_client):
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner_client.user)
        access = SharedAccessFactory(
            file=file_obj,
            shared_by=owner_client.user,
            shared_with=recipient,
        )
        access_id = access.id

        response = owner_client.post(
            reverse('sharing:revoke_access', args=[access_id]),
        )
        data = response.json()
        assert data['success'] is True
        assert not SharedAccess.objects.filter(pk=access_id).exists()

    def test_non_owner_cannot_revoke(self, owner_client):
        other_owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=other_owner)
        access = SharedAccessFactory(
            file=file_obj,
            shared_by=other_owner,
            shared_with=recipient,
        )

        response = owner_client.post(
            reverse('sharing:revoke_access', args=[access.id]),
        )
        data = response.json()
        assert data['success'] is False


@pytest.mark.django_db
class TestSharedWithMePage:

    def test_shared_with_me_shows_shared_files(self, owner_client):
        other_owner = UserFactory()
        file_obj = FileFactory(owner=other_owner)
        SharedAccessFactory(
            file=file_obj,
            shared_by=other_owner,
            shared_with=owner_client.user,
        )

        response = owner_client.get(reverse('sharing:shared_with_me'))
        assert response.status_code == 200
        assert file_obj.name.encode() in response.content

    def test_user_search_returns_results(self, owner_client):
        target = UserFactory(username='searchable_user')
        response = owner_client.get(
            reverse('sharing:user_search'),
            {'q': 'searchable'},
        )
        data = response.json()
        usernames = [u['username'] for u in data['users']]
        assert 'searchable_user' in usernames

    def test_user_search_excludes_self(self, owner_client):
        response = owner_client.get(
            reverse('sharing:user_search'),
            {'q': owner_client.user.username[:3]},
        )
        data = response.json()
        ids = [u['id'] for u in data['users']]
        assert owner_client.user.id not in ids

    def test_user_search_requires_2_chars(self, owner_client):
        response = owner_client.get(
            reverse('sharing:user_search'),
            {'q': 'a'},
        )
        data = response.json()
        assert data['users'] == []