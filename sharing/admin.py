from django.contrib import admin
from .models import SharedAccess

@admin.register(SharedAccess)
class SharedAccessAdmin(admin.ModelAdmin):
    list_display = ['item_type', 'shared_with', 'shared_by', 'permission', 'created_at']
    list_filter = ['permission']