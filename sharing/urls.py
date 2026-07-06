from django.urls import path
from . import views

app_name = 'sharing'

urlpatterns = [
    path('users/search/', views.user_search, name='user_search'),
    path('share/', views.share_item, name='share_item'),
    path('access/', views.list_access, name='list_access'),
    path('access/<int:access_id>/update/', views.update_permission, name='update_permission'),
    path('access/<int:access_id>/revoke/', views.revoke_access, name='revoke_access'),
    path('shared-with-me/', views.shared_with_me, name='shared_with_me'),
]