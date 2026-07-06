import os
import uuid

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


def user_upload_path(instance, filename):
    """
    Builds the on-disk path for an uploaded file:
    media/user_<id>/<uuid>_<original_filename>

    We prefix with a UUID (not just use the original filename) so that
    two different files named "report.pdf" by the same user never collide
    on disk, even though we also enforce name-uniqueness per folder at
    the DB/display level. The UUID is purely a storage-layer safeguard.
    """
    ext = filename.split('.')[-1] if '.' in filename else ''
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    return os.path.join(f"user_{instance.owner.id}", unique_name)


class Folder(models.Model):
    """ 
    Self-referencing model: `parent` points to another Folder, or is null
    for a root-level folder. This single FK is what gives us unlimited
    nesting depth without needing a separate "path" table.
    """
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='folders')
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='children'
    )

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # A user cannot have two non-deleted folders with the same name
            # in the same parent. We can't enforce "ignore soft-deleted rows"
            # purely in a DB constraint cleanly across all DBs, so the hard
            # constraint covers owner+parent+name, and clean() below adds the
            # is_deleted-aware check at the application level (see note below).
            models.UniqueConstraint(
                fields=['owner', 'parent', 'name'],
                condition=models.Q(is_deleted=False),
                name='unique_folder_name_per_parent_when_active',
            )
        ]
        ordering = ['name']

    def __str__(self):
        return self.name

    def clean(self):
        # Guard against circular references: a folder cannot become its own
        # ancestor. Without this, moving "A" into "A > B" creates an infinite
        # loop when walking the tree (breadcrumbs, recursive delete, etc.)
        if self.parent_id is None:
            return
        if self.pk is not None:
            ancestor = self.parent
            while ancestor is not None:
                if ancestor.pk == self.pk:
                    raise ValidationError("A folder cannot be moved into itself or one of its own subfolders.")
                ancestor = ancestor.parent

    def get_descendant_folders(self):
        """
        Recursively collects all nested subfolders (any depth).
        Used by soft-delete cascade and by storage/size calculations later.
        """
        descendants = []
        for child in self.children.filter(is_deleted=False):
            descendants.append(child)
            descendants.extend(child.get_descendant_folders())
        return descendants

    def soft_delete(self):
        """
        Cascades the soft-delete flag down through every nested subfolder
        and every file inside this folder and its subfolders. This is an
        application-level cascade (not models.CASCADE on delete) because
        we never want a real DB row deleted here — only flagged.
        """
        now = timezone.now()
        all_folders = [self] + self.get_descendant_folders()

        for folder in all_folders:
            folder.is_deleted = True
            folder.deleted_at = now
            folder.save(update_fields=['is_deleted', 'deleted_at'])

        File.objects.filter(folder__in=all_folders, is_deleted=False).update(
            is_deleted=True, deleted_at=now
        )

    def restore(self):
        """
        Restores this folder only (not a full cascade-restore of children,
        since a child might have been independently deleted earlier — Phase 3
        UI will surface restore per-item rather than assuming a full tree
        restore is always correct).
        """
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def get_breadcrumbs(self):
        """Returns ancestors from root -> this folder, for breadcrumb UI."""
        crumbs = []
        node = self
        while node is not None:
            crumbs.insert(0, node)
            node = node.parent
        return crumbs


class File(models.Model):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True, related_name='files'
    )

    upload = models.FileField(upload_to=user_upload_path)
    size = models.BigIntegerField(default=0)  # bytes
    mime_type = models.CharField(max_length=150, blank=True)

    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Scheduled deletion (used in Phase 9, field lives here from the start
    # since it's part of the core file model, not a separate concern)
    scheduled_delete_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'folder', 'name'],
                condition=models.Q(is_deleted=False),
                name='unique_file_name_per_folder_when_active',
            )
        ]
        ordering = ['name']

    def __str__(self):
        return self.name

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
        # Storage accounting: free up the user's used space immediately on
        # soft-delete (Trash) rather than waiting for permanent deletion —
        # matches how Drive's quota behaves (Trash still counts in some
        # products, but we're keeping this simple/predictable for now).
        self.owner.storage_used = max(0, self.owner.storage_used - self.size)
        self.owner.save(update_fields=['storage_used'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])
        self.owner.storage_used += self.size
        self.owner.save(update_fields=['storage_used'])

    def hard_delete(self):
        """
        Actually removes the file from disk and the DB row. Called by the
        permanent-delete action and by the Phase 9 scheduled-deletion task.
        """
        storage_path = self.upload.path if self.upload else None
        if storage_path and os.path.isfile(storage_path):
            os.remove(storage_path)
        self.delete()