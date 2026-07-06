from django.contrib import admin
from .models import Folder, File


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'parent', 'is_deleted', 'created_at']
    list_filter = ['is_deleted']
    search_fields = ['name', 'owner__username']


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'folder', 'size', 'is_deleted', 'scheduled_delete_at', 'created_at']
    list_filter = ['is_deleted']
    search_fields = ['name', 'owner__username']