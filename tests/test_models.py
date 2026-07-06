"""
Unit tests for model-level business logic.
These tests don't touch HTTP — they test the data layer directly.
Covers: soft-delete cascade, circular reference protection,
uniqueness constraints, permission helpers, storage tracking.
"""

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from drive.models import Folder, File
from sharing.models import SharedAccess
from sharing.permissions import (
    get_file_permission, get_folder_permission,
    can_view_file, can_edit_file,
    can_view_folder, can_edit_folder,
)
from notifications.models import Notification

from .factories import (
    UserFactory, FolderFactory, FileFactory,
    SharedAccessFactory, NotificationFactory,
)


@pytest.mark.django_db
class TestFolderModel:

    def test_create_root_folder(self):
        user = UserFactory()
        folder = FolderFactory(owner=user, parent=None)
        assert folder.pk is not None
        assert folder.parent is None
        assert folder.is_deleted is False

    def test_create_nested_folder(self):
        user = UserFactory()
        root = FolderFactory(owner=user)
        child = FolderFactory(owner=user, parent=root)
        grandchild = FolderFactory(owner=user, parent=child)
        assert child.parent == root
        assert grandchild.parent == child

    def test_soft_delete_cascades_to_children(self):
        user = UserFactory()
        root = FolderFactory(owner=user)
        child = FolderFactory(owner=user, parent=root)
        grandchild = FolderFactory(owner=user, parent=child)

        root.soft_delete()

        root.refresh_from_db()
        child.refresh_from_db()
        grandchild.refresh_from_db()

        assert root.is_deleted is True
        assert child.is_deleted is True
        assert grandchild.is_deleted is True

    def test_soft_delete_cascades_to_files(self):
        user = UserFactory()
        folder = FolderFactory(owner=user)
        file_obj = FileFactory(owner=user, folder=folder)

        folder.soft_delete()
        file_obj.refresh_from_db()

        assert file_obj.is_deleted is True

    def test_restore_folder(self):
        user = UserFactory()
        folder = FolderFactory(owner=user)
        folder.soft_delete()
        folder.restore()

        folder.refresh_from_db()
        assert folder.is_deleted is False
        assert folder.deleted_at is None

    def test_circular_reference_raises_validation_error(self):
        user = UserFactory()
        root = FolderFactory(owner=user)
        child = FolderFactory(owner=user, parent=root)
        grandchild = FolderFactory(owner=user, parent=child)

        # Try to make root a child of its own grandchild
        root.parent = grandchild
        with pytest.raises(ValidationError):
            root.clean()

    def test_folder_cannot_be_its_own_parent(self):
        user = UserFactory()
        folder = FolderFactory(owner=user)
        folder.parent = folder
        with pytest.raises(ValidationError):
            folder.clean()

    def test_get_breadcrumbs(self):
        user = UserFactory()
        root = FolderFactory(owner=user, name='Root')
        child = FolderFactory(owner=user, parent=root, name='Child')
        grandchild = FolderFactory(owner=user, parent=child, name='Grandchild')

        crumbs = grandchild.get_breadcrumbs()
        assert len(crumbs) == 3
        assert crumbs[0] == root
        assert crumbs[1] == child
        assert crumbs[2] == grandchild

    def test_duplicate_folder_name_same_parent_blocked(self):
        user = UserFactory()
        parent = FolderFactory(owner=user)
        FolderFactory(owner=user, parent=parent, name='Documents')

        duplicate = Folder(owner=user, parent=parent, name='Documents')
        with pytest.raises(Exception):  # IntegrityError or ValidationError
            duplicate.full_clean()
            duplicate.save()

    def test_same_name_allowed_in_different_parent(self):
        user = UserFactory()
        parent_a = FolderFactory(owner=user)
        parent_b = FolderFactory(owner=user)
        FolderFactory(owner=user, parent=parent_a, name='Reports')
        # Should not raise
        folder = FolderFactory(owner=user, parent=parent_b, name='Reports')
        assert folder.pk is not None

    def test_soft_deleted_name_can_be_reused(self):
        user = UserFactory()
        folder = FolderFactory(owner=user, name='Archive')
        folder.soft_delete()
        # Should be able to create a new folder with the same name
        new_folder = FolderFactory(owner=user, name='Archive')
        assert new_folder.pk is not None


@pytest.mark.django_db
class TestFileModel:

    def test_soft_delete_updates_storage(self):
        user = UserFactory()
        file_obj = FileFactory(owner=user, size=500)
        user.storage_used = 500
        user.save()

        file_obj.soft_delete()
        user.refresh_from_db()

        assert file_obj.is_deleted is True
        assert user.storage_used == 0

    def test_restore_updates_storage(self):
        user = UserFactory()
        file_obj = FileFactory(owner=user, size=500)
        user.storage_used = 0
        user.save()

        file_obj.is_deleted = True
        file_obj.deleted_at = timezone.now()
        file_obj.save()

        file_obj.restore()
        user.refresh_from_db()

        assert file_obj.is_deleted is False
        assert user.storage_used == 500

    def test_scheduled_delete_at_field(self):
        file_obj = FileFactory()
        future_time = timezone.now() + timezone.timedelta(hours=1)
        file_obj.scheduled_delete_at = future_time
        file_obj.save()

        file_obj.refresh_from_db()
        assert file_obj.scheduled_delete_at is not None

    def test_duplicate_filename_same_folder_blocked(self):
        user = UserFactory()
        folder = FolderFactory(owner=user)
        FileFactory(owner=user, folder=folder, name='report.pdf')

        duplicate = File(
            owner=user,
            folder=folder,
            name='report.pdf',
            size=0,
            mime_type='application/pdf',
        )
        with pytest.raises(Exception):
            duplicate.full_clean(exclude=['upload'])
            duplicate.save()

    def test_same_filename_different_folders_allowed(self):
        user = UserFactory()
        folder_a = FolderFactory(owner=user)
        folder_b = FolderFactory(owner=user)
        FileFactory(owner=user, folder=folder_a, name='report.pdf')
        file_b = FileFactory(owner=user, folder=folder_b, name='report.pdf')
        assert file_b.pk is not None


@pytest.mark.django_db
class TestSharedAccessModel:

    def test_share_file_with_user(self):
        owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner)

        access = SharedAccess.objects.create(
            file=file_obj,
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        assert access.pk is not None
        assert access.permission == 'view'

    def test_cannot_share_with_yourself(self):
        user = UserFactory()
        file_obj = FileFactory(owner=user)

        access = SharedAccess(
            file=file_obj,
            shared_by=user,
            shared_with=user,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        with pytest.raises(ValidationError):
            access.clean()

    def test_cannot_share_same_file_twice(self):
        owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner)

        SharedAccess.objects.create(
            file=file_obj,
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        with pytest.raises(Exception):
            SharedAccess.objects.create(
                file=file_obj,
                shared_by=owner,
                shared_with=recipient,
                permission=SharedAccess.PERMISSION_EDIT,
            )

    def test_must_have_file_or_folder(self):
        owner = UserFactory()
        recipient = UserFactory()
        access = SharedAccess(
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        with pytest.raises(ValidationError):
            access.clean()

    def test_cannot_have_both_file_and_folder(self):
        owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner)
        folder = FolderFactory(owner=owner)

        access = SharedAccess(
            file=file_obj,
            folder=folder,
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        with pytest.raises(ValidationError):
            access.clean()


@pytest.mark.django_db
class TestPermissions:

    def test_owner_has_owner_permission_on_file(self):
        user = UserFactory()
        file_obj = FileFactory(owner=user)
        assert get_file_permission(user, file_obj) == 'owner'

    def test_owner_has_owner_permission_on_folder(self):
        user = UserFactory()
        folder = FolderFactory(owner=user)
        assert get_folder_permission(user, folder) == 'owner'

    def test_shared_user_gets_view_permission(self):
        owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner)
        SharedAccessFactory(
            file=file_obj,
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        assert get_file_permission(recipient, file_obj) == 'view'

    def test_shared_user_gets_edit_permission(self):
        owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner)
        SharedAccessFactory(
            file=file_obj,
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_EDIT,
        )
        assert get_file_permission(recipient, file_obj) == 'edit'

    def test_unshared_user_gets_none(self):
        owner = UserFactory()
        stranger = UserFactory()
        file_obj = FileFactory(owner=owner)
        assert get_file_permission(stranger, file_obj) is None

    def test_can_view_file_true_for_shared(self):
        owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner)
        SharedAccessFactory(
            file=file_obj,
            shared_by=owner,
            shared_with=recipient,
        )
        assert can_view_file(recipient, file_obj) is True

    def test_can_edit_file_false_for_view_only(self):
        owner = UserFactory()
        recipient = UserFactory()
        file_obj = FileFactory(owner=owner)
        SharedAccessFactory(
            file=file_obj,
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_VIEW,
        )
        assert can_edit_file(recipient, file_obj) is False

    def test_can_view_subfolder_via_ancestor_share(self):
        owner = UserFactory()
        recipient = UserFactory()
        root = FolderFactory(owner=owner)
        child = FolderFactory(owner=owner, parent=root)
        grandchild = FolderFactory(owner=owner, parent=child)

        # Share only the root
        SharedAccess.objects.create(
            folder=root,
            shared_by=owner,
            shared_with=recipient,
            permission=SharedAccess.PERMISSION_VIEW,
        )

        # Grandchild should be accessible via ancestor chain
        assert can_view_folder(recipient, grandchild) is True


@pytest.mark.django_db
class TestNotificationModel:

    def test_create_notification(self):
        notif = NotificationFactory()
        assert notif.pk is not None
        assert notif.is_read is False

    def test_mark_read(self):
        notif = NotificationFactory(is_read=False)
        notif.mark_read()
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_mark_read_idempotent(self):
        notif = NotificationFactory(is_read=True)
        notif.mark_read()  # Should not crash or re-save unnecessarily
        assert notif.is_read is True

    def test_ordering_newest_first(self):
        user = UserFactory()
        n1 = NotificationFactory(recipient=user)
        n2 = NotificationFactory(recipient=user)
        n3 = NotificationFactory(recipient=user)

        notifications = list(Notification.objects.filter(recipient=user))
        assert notifications[0] == n3  # newest first
        assert notifications[2] == n1