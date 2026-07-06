from django.urls import path
from . import views

app_name = 'drive'

urlpatterns = [
    path('', views.home, name='home'),
    path('folder/<int:folder_id>/', views.home, name='folder_view'),

    path('folder/create/', views.folder_create, name='folder_create'),
    path('folder/<int:folder_id>/rename/', views.folder_rename, name='folder_rename'),
    path('folder/<int:folder_id>/delete/', views.folder_delete, name='folder_delete'),
    path('folder/<int:folder_id>/move/', views.folder_move, name='folder_move'),
    path('folder/<int:folder_id>/restore/', views.folder_restore, name='folder_restore'),
    path('folder/<int:folder_id>/permanent-delete/', views.folder_permanent_delete, name='folder_permanent_delete'),

    path('file/upload/', views.file_upload, name='file_upload'),
    path('file/<int:file_id>/rename/', views.file_rename, name='file_rename'),
    path('file/<int:file_id>/delete/', views.file_delete, name='file_delete'),
    path('file/<int:file_id>/move/', views.file_move, name='file_move'),
    path('file/<int:file_id>/restore/', views.file_restore, name='file_restore'),
    path('file/<int:file_id>/permanent-delete/', views.file_permanent_delete, name='file_permanent_delete'),

    path('file/<int:file_id>/schedule-delete/', views.file_schedule_delete, name='file_schedule_delete'),
    path('file/<int:file_id>/cancel-schedule/', views.file_cancel_schedule, name='file_cancel_schedule'),

    path('trash/', views.trash, name='trash'),
]