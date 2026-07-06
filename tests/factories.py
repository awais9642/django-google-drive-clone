import factory
from django.contrib.auth import get_user_model
from drive.models import Folder, File
from sharing.models import SharedAccess
from notifications.models import Notification

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    password = factory.PostGenerationMethodCall('set_password', 'testpass123')


class FolderFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Folder

    name = factory.Sequence(lambda n: f'Folder {n}')
    owner = factory.SubFactory(UserFactory)
    parent = None


class FileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = File

    name = factory.Sequence(lambda n: f'file{n}.txt')
    owner = factory.SubFactory(UserFactory)
    folder = None
    upload = factory.django.FileField(filename='test.txt', data=b'test content')
    size = 12
    mime_type = 'text/plain'


class SharedAccessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SharedAccess

    shared_by = factory.SubFactory(UserFactory)
    shared_with = factory.SubFactory(UserFactory)
    permission = SharedAccess.PERMISSION_VIEW
    file = factory.SubFactory(FileFactory)


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    recipient = factory.SubFactory(UserFactory)
    actor = factory.SubFactory(UserFactory)
    notif_type = Notification.TYPE_SHARE
    message = 'Test notification'
    is_read = False