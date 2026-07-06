"""
Integration tests for drive views.
These tests send real HTTP requests through Django's test client
and verify JSON responses, status codes, and DB state.
"""

import pytest
from django.urls import reverse

from drive.models import Folder, File
from .factories import UserFactory, FolderFactory, FileFactory


@pytest.fixture
def client_logged_in(client):
    """Returns a test client already logged in as a fresh user."""
    user = UserFactory()
    client.force_login(user)
    client.user = user
    return client


@pytest.mark.django_db
class TestFolderCRUD:

    def test_create_folder_at_root(self, client_logged_in):
        response = client_logged_in.post(
            reverse('drive:folder_create'),
            {'name': 'My Folder', 'parent_id': ''},
        )
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['folder']['name'] == 'My Folder'
        assert Folder.objects.filter(
            name='My Folder', owner=client_logged_in.user
        ).exists()

    def test_create_folder_inside_parent(self, client_logged_in):
        parent = FolderFactory(owner=client_logged_in.user)
        response = client_logged_in.post(
            reverse('drive:folder_create'),
            {'name': 'Child', 'parent_id': parent.id},
        )
        data = response.json()
        assert data['success'] is True
        child = Folder.objects.get(pk=data['folder']['id'])
        assert child.parent == parent

    def test_create_duplicate_folder_name_returns_error(self, client_logged_in):
        FolderFactory(owner=client_logged_in.user, name='Duplicate')
        response = client_logged_in.post(
            reverse('drive:folder_create'),
            {'name': 'Duplicate', 'parent_id': ''},
        )
        data = response.json()
        assert data['success'] is False
        assert 'already exists' in data['error'].lower()

    def test_rename_folder(self, client_logged_in):
        folder = FolderFactory(owner=client_logged_in.user, name='Old Name')
        response = client_logged_in.post(
            reverse('drive:folder_rename', args=[folder.id]),
            {'name': 'New Name'},
        )
        data = response.json()
        assert data['success'] is True
        folder.refresh_from_db()
        assert folder.name == 'New Name'

    def test_rename_folder_empty_name_rejected(self, client_logged_in):
        folder = FolderFactory(owner=client_logged_in.user)
        response = client_logged_in.post(
            reverse('drive:folder_rename', args=[folder.id]),
            {'name': ''},
        )
        data = response.json()
        assert data['success'] is False

    def test_soft_delete_folder(self, client_logged_in):
        folder = FolderFactory(owner=client_logged_in.user)
        response = client_logged_in.post(
            reverse('drive:folder_delete', args=[folder.id]),
        )
        data = response.json()
        assert data['success'] is True
        folder.refresh_from_db()
        assert folder.is_deleted is True

    def test_soft_delete_cascades_via_view(self, client_logged_in):
        parent = FolderFactory(owner=client_logged_in.user)
        child = FolderFactory(owner=client_logged_in.user, parent=parent)
        file_obj = FileFactory(owner=client_logged_in.user, folder=parent)

        client_logged_in.post(reverse('drive:folder_delete', args=[parent.id]))

        child.refresh_from_db()
        file_obj.refresh_from_db()
        assert child.is_deleted is True
        assert file_obj.is_deleted is True

    def test_restore_folder(self, client_logged_in):
        folder = FolderFactory(owner=client_logged_in.user)
        folder.soft_delete()

        response = client_logged_in.post(
            reverse('drive:folder_restore', args=[folder.id]),
        )
        data = response.json()
        assert data['success'] is True
        folder.refresh_from_db()
        assert folder.is_deleted is False

    def test_cannot_delete_another_users_folder(self, client_logged_in):
        other_user = UserFactory()
        other_folder = FolderFactory(owner=other_user)

        response = client_logged_in.post(
            reverse('drive:folder_delete', args=[other_folder.id]),
        )
        assert response.status_code == 404

    def test_move_folder(self, client_logged_in):
        folder = FolderFactory(owner=client_logged_in.user)
        destination = FolderFactory(owner=client_logged_in.user)

        response = client_logged_in.post(
            reverse('drive:folder_move', args=[folder.id]),
            {'destination_folder': destination.id},
        )
        data = response.json()
        assert data['success'] is True
        folder.refresh_from_db()
        assert folder.parent == destination

    def test_unauthenticated_redirects_to_login(self, client):
        response = client.post(
            reverse('drive:folder_create'),
            {'name': 'Test'},
        )
        assert response.status_code == 302
        assert '/accounts/login/' in response['Location']


@pytest.mark.django_db
class TestFileCRUD:

    def test_upload_file(self, client_logged_in):
        from django.core.files.uploadedfile import SimpleUploadedFile

        uploaded = SimpleUploadedFile('test.txt', b'hello world', content_type='text/plain')
        response = client_logged_in.post(
            reverse('drive:file_upload'),
            {'upload': uploaded, 'folder_id': ''},
        )
        data = response.json()
        assert data['success'] is True
        assert File.objects.filter(
            name='test.txt', owner=client_logged_in.user
        ).exists()

    def test_upload_updates_storage_used(self, client_logged_in):
        from django.core.files.uploadedfile import SimpleUploadedFile

        uploaded = SimpleUploadedFile('test.txt', b'hello', content_type='text/plain')
        client_logged_in.post(
            reverse('drive:file_upload'),
            {'upload': uploaded, 'folder_id': ''},
        )
        client_logged_in.user.refresh_from_db()
        assert client_logged_in.user.storage_used > 0

    def test_rename_file(self, client_logged_in):
        file_obj = FileFactory(owner=client_logged_in.user, name='old.txt')
        response = client_logged_in.post(
            reverse('drive:file_rename', args=[file_obj.id]),
            {'name': 'new.txt'},
        )
        data = response.json()
        assert data['success'] is True
        file_obj.refresh_from_db()
        assert file_obj.name == 'new.txt'

    def test_soft_delete_file(self, client_logged_in):
        file_obj = FileFactory(owner=client_logged_in.user)
        response = client_logged_in.post(
            reverse('drive:file_delete', args=[file_obj.id]),
        )
        data = response.json()
        assert data['success'] is True
        file_obj.refresh_from_db()
        assert file_obj.is_deleted is True

    def test_soft_delete_decreases_storage(self, client_logged_in):
        file_obj = FileFactory(owner=client_logged_in.user, size=200)
        client_logged_in.user.storage_used = 200
        client_logged_in.user.save()

        client_logged_in.post(reverse('drive:file_delete', args=[file_obj.id]))

        client_logged_in.user.refresh_from_db()
        assert client_logged_in.user.storage_used == 0

    def test_restore_file(self, client_logged_in):
        file_obj = FileFactory(owner=client_logged_in.user)
        file_obj.soft_delete()

        response = client_logged_in.post(
            reverse('drive:file_restore', args=[file_obj.id]),
        )
        data = response.json()
        assert data['success'] is True
        file_obj.refresh_from_db()
        assert file_obj.is_deleted is False

    def test_cannot_delete_another_users_file(self, client_logged_in):
        other_user = UserFactory()
        other_file = FileFactory(owner=other_user)

        response = client_logged_in.post(
            reverse('drive:file_delete', args=[other_file.id]),
        )
        assert response.status_code == 404

    def test_move_file_to_folder(self, client_logged_in):
        file_obj = FileFactory(owner=client_logged_in.user)
        destination = FolderFactory(owner=client_logged_in.user)

        response = client_logged_in.post(
            reverse('drive:file_move', args=[file_obj.id]),
            {'destination_folder': destination.id},
        )
        data = response.json()
        assert data['success'] is True
        file_obj.refresh_from_db()
        assert file_obj.folder == destination


@pytest.mark.django_db
class TestDriveViews:

    def test_home_view_loads(self, client_logged_in):
        response = client_logged_in.get(reverse('drive:home'))
        assert response.status_code == 200

    def test_folder_view_loads(self, client_logged_in):
        folder = FolderFactory(owner=client_logged_in.user)
        response = client_logged_in.get(
            reverse('drive:folder_view', args=[folder.id])
        )
        assert response.status_code == 200

    def test_trash_view_loads(self, client_logged_in):
        response = client_logged_in.get(reverse('drive:trash'))
        assert response.status_code == 200

    def test_shared_folder_accessible_by_recipient(self, client_logged_in):
        owner = UserFactory()
        folder = FolderFactory(owner=owner)
        from sharing.models import SharedAccess
        SharedAccess.objects.create(
            folder=folder,
            shared_by=owner,
            shared_with=client_logged_in.user,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        response = client_logged_in.get(
            reverse('drive:folder_view', args=[folder.id])
        )
        assert response.status_code == 200

    def test_unshared_folder_returns_404(self, client_logged_in):
        other_user = UserFactory()
        folder = FolderFactory(owner=other_user)
        response = client_logged_in.get(
            reverse('drive:folder_view', args=[folder.id])
        )
        assert response.status_code == 404