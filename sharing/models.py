from django.conf import settings
from django.db import models


class SharedAccess(models.Model):
    """
    Represents one sharing relationship:
        owner's file/folder → shared with user → at permission level

    GenericForeignKey would work here, but two explicit FKs (one nullable)
    is simpler to query, easier to add DB-level constraints on, and doesn't
    require ContentType overhead for a two-type system.

    Exactly one of file/folder must be set — enforced in clean().
    """

    PERMISSION_VIEW = 'view'
    PERMISSION_EDIT = 'edit'
    PERMISSION_CHOICES = [
        (PERMISSION_VIEW, 'View'),
        (PERMISSION_EDIT, 'Edit'),
    ]

    # The item being shared — exactly one of these is non-null
    file = models.ForeignKey(
        'drive.File',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='shared_accesses',
    )
    folder = models.ForeignKey(
        'drive.Folder',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='shared_accesses',
    )

    shared_with = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_shares',
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_shares',
    )
    permission = models.CharField(
        max_length=10,
        choices=PERMISSION_CHOICES,
        default=PERMISSION_VIEW,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # Prevent sharing same file to same user twice
            models.UniqueConstraint(
                fields=['file', 'shared_with'],
                condition=models.Q(file__isnull=False),
                name='unique_file_share_per_user',
            ),
            # Prevent sharing same folder to same user twice
            models.UniqueConstraint(
                fields=['folder', 'shared_with'],
                condition=models.Q(folder__isnull=False),
                name='unique_folder_share_per_user',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.file is None and self.folder is None:
            raise ValidationError('A share must target either a file or a folder.')
        if self.file is not None and self.folder is not None:
            raise ValidationError('A share cannot target both a file and a folder.')
        if self.shared_with == self.shared_by:
            raise ValidationError('You cannot share an item with yourself.')

    def __str__(self):
        item = self.file or self.folder
        return f'{item} → {self.shared_with.username} ({self.permission})'

    @property
    def item(self):
        """Convenience property to get whichever item is set."""
        return self.file or self.folder

    @property
    def item_type(self):
        return 'file' if self.file else 'folder'