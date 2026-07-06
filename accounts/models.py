from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """
    Custom user model. Inherits username, email, password, etc. from AbstractUser.
    Extending now (rather than using Django's default User) means we can add
    fields later — e.g. storage quota, avatar — without a painful migration.
    """
    storage_used = models.BigIntegerField(default=0)  # bytes; used in Phase 2/3

    def __str__(self):
        return self.username
