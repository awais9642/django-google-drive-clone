import json
from notifications.broadcast import broadcast_to_user
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseForbidden, Http404
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST, require_http_methods
from django.db import IntegrityError
from .models import Folder, File
from .forms import FolderForm, FileUploadForm, FileRenameForm, MoveItemForm
from django.utils import timezone
from django.utils.dateparse import parse_datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_owned_folder_or_none(user, folder_id):
    """
    Returns the folder if it exists, belongs to the user, and isn't deleted.
    Returns None for folder_id=None (root level) — treated as a valid case,
    not an error.
    """
    if folder_id in (None, '', 'null', 'root'):
        return None
    folder = get_object_or_404(Folder, pk=folder_id, owner=user, is_deleted=False)
    return folder


def _json_error(message, status=400):
    return JsonResponse({'success': False, 'error': message}, status=status)


# ---------------------------------------------------------------------------
# Overview page (grid/list, breadcrumbs)
# ---------------------------------------------------------------------------

@login_required
def home(request, folder_id=None):
    current_folder = None

    if folder_id is not None:
        # Try as owner first
        try:
            current_folder = Folder.objects.get(
                pk=folder_id, owner=request.user, is_deleted=False
            )
        except Folder.DoesNotExist:
            # Try as shared-with user
            from sharing.permissions import can_view_folder
            try:
                current_folder = Folder.objects.get(pk=folder_id, is_deleted=False)
            except Folder.DoesNotExist:
                raise Http404
            if not can_view_folder(request.user, current_folder):
                raise Http404

    # For shared folders, show only items owned by the folder owner
    # For own folders, show items owned by the current user
    if current_folder and current_folder.owner != request.user:
        # Viewing someone else's shared folder
        folders = Folder.objects.filter(
            parent=current_folder, is_deleted=False
        )
        files = File.objects.filter(
            folder=current_folder, is_deleted=False
        )
        is_shared_view = True
    else:
        folders = Folder.objects.filter(
            owner=request.user, parent=current_folder, is_deleted=False
        )
        files = File.objects.filter(
            owner=request.user, folder=current_folder, is_deleted=False
        )
        is_shared_view = False

    breadcrumbs = current_folder.get_breadcrumbs() if current_folder else []
    all_folders = Folder.objects.filter(owner=request.user, is_deleted=False)

    context = {
        'current_folder': current_folder,
        'folders': folders,
        'files': files,
        'breadcrumbs': breadcrumbs,
        'all_folders': all_folders,
        'folder_form': FolderForm(),
        'upload_form': FileUploadForm(),
        'is_shared_view': is_shared_view,
    }
    return render(request, 'drive/home.html', context)


# ---------------------------------------------------------------------------
# Folder CRUD
# ---------------------------------------------------------------------------

@login_required
@require_POST
def folder_create(request):
    parent_id = request.POST.get('parent_id')
    parent = _get_owned_folder_or_none(request.user, parent_id)

    form = FolderForm(request.POST)
    if not form.is_valid():
        return _json_error(form.errors.get('name', ['Invalid name.'])[0])

    folder = form.save(commit=False)
    folder.owner = request.user
    folder.parent = parent

    try:
        folder.full_clean()
        folder.save()

        broadcast_to_user(request.user.id, 'folder.created', {
    'id': folder.id,
    'name': folder.name,
    'parent_id': folder.parent_id,
    'created_at': folder.created_at.strftime('%b %d, %Y'),
})
        

    except (ValidationError, IntegrityError):
        return _json_error('A folder with this name already exists here.')

    return JsonResponse({
        'success': True,
        'folder': {
            'id': folder.id,
            'name': folder.name,
            'created_at': folder.created_at.strftime('%b %d, %Y'),
        }
    })


@login_required
@require_POST
def folder_rename(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, owner=request.user, is_deleted=False)
    form = FolderForm(request.POST, instance=folder)

    if not form.is_valid():
        return _json_error(form.errors.get('name', ['Invalid name.'])[0])

    try:
        folder.full_clean()
        form.save() 

        broadcast_to_user(request.user.id, 'folder.renamed', {
    'id': folder.id,
    'name': folder.name,
      })
        
        
    except (ValidationError, IntegrityError):
        return _json_error('A folder with this name already exists here.')

    return JsonResponse({'success': True, 'id': folder.id, 'name': folder.name})


@login_required
@require_POST
def folder_delete(request, folder_id):
    """Soft-delete: cascades to all nested subfolders and files (Phase 2 logic)."""
    folder = get_object_or_404(Folder, pk=folder_id, owner=request.user, is_deleted=False)
    folder.soft_delete()
    broadcast_to_user(request.user.id, 'folder.deleted', {
    'id': folder.id,
    'type': 'folder',
     })
    return JsonResponse({'success': True, 'id': folder.id, 'type': 'folder'})


@login_required
@require_POST
def folder_move(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, owner=request.user, is_deleted=False)

    form = MoveItemForm(request.POST)
    form.fields['destination_folder'].queryset = Folder.objects.filter(
        owner=request.user, is_deleted=False
    )

    if not form.is_valid():
        return _json_error('Invalid destination.')

    destination = form.cleaned_data['destination_folder']

    folder.parent = destination
    try:
        folder.full_clean()  # catches circular-reference attempts
        folder.save()
        broadcast_to_user(request.user.id, 'folder.moved', {
    'id': folder.id,
     
     })
    except (ValidationError, IntegrityError) as e:
        return _json_error(str(e.messages[0]) if hasattr(e, 'messages') else 'Cannot move folder here.')

    return JsonResponse({'success': True, 'id': folder.id})


@login_required
@require_POST
def folder_restore(request, folder_id):
    folder = get_object_or_404(Folder, pk=folder_id, owner=request.user, is_deleted=True)
    folder.restore()
    return JsonResponse({'success': True, 'id': folder.id})


@login_required
@require_POST
def folder_permanent_delete(request, folder_id):
    """
    Permanently deletes a folder and everything inside it. Only allowed
    from Trash (is_deleted=True) — you can't skip Trash from the main view.
    """
    folder = get_object_or_404(Folder, pk=folder_id, owner=request.user, is_deleted=True)

    # Permanently delete all files inside this folder and its descendants first.
    # We walk descendants regardless of is_deleted state, since a folder sitting
    # in Trash may have nested children also already marked deleted.
    all_folders = [folder] + _all_descendants_any_state(folder)

    for f in File.objects.filter(folder__in=all_folders):
        f.hard_delete()

    # Delete folders bottom-up isn't required since this is a real DB delete
    # with on_delete=CASCADE on the self-FK, so deleting the top folder
    # cascades the actual DB rows automatically.
    folder.delete()

    return JsonResponse({'success': True, 'id': folder_id, 'type': 'folder'})


def _all_descendants_any_state(folder):
    """Fallback descendant walker that doesn't filter by is_deleted, used only
    for permanent delete where we want every nested folder regardless of state."""
    descendants = []
    for child in folder.children.all():
        descendants.append(child)
        descendants.extend(_all_descendants_any_state(child))
    return descendants


# ---------------------------------------------------------------------------
# File CRUD
# ---------------------------------------------------------------------------

@login_required
@require_POST
def file_upload(request):
    folder_id = request.POST.get('folder_id')
    folder = _get_owned_folder_or_none(request.user, folder_id)

    uploaded = request.FILES.get('upload')
    if not uploaded:
        return _json_error('No file selected.')

    file_obj = File(
        name=uploaded.name,
        owner=request.user,
        folder=folder,
        upload=uploaded,
        size=uploaded.size,
        mime_type=uploaded.content_type or '',
    )

    try:
        file_obj.full_clean(exclude=['upload'])  # upload field validated separately by ModelForm normally; full_clean on FileField with a fresh file is fine here
        file_obj.save()
    except (ValidationError, IntegrityError):
        return _json_error('A file with this name already exists here.')

    request.user.storage_used += file_obj.size
    request.user.save(update_fields=['storage_used'])

    broadcast_to_user(request.user.id, 'file.created', {

    'id': file_obj.id,
    'name': file_obj.name,
    'size': file_obj.size,
    'folder_id': file_obj.folder_id,
    'created_at': file_obj.created_at.strftime('%b %d, %Y'),

     })

    return JsonResponse({
        'success': True,
        'file': {
            'id': file_obj.id,
            'name': file_obj.name,
            'size': file_obj.size,
            'created_at': file_obj.created_at.strftime('%b %d, %Y'),
        }
    })


@login_required
@require_POST
def file_rename(request, file_id):
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)
    form = FileRenameForm(request.POST, instance=file_obj)

    if not form.is_valid():
        return _json_error(form.errors.get('name', ['Invalid name.'])[0])

    try:
        file_obj.full_clean(exclude=['upload'])
        form.save()
         
        broadcast_to_user(request.user.id, 'file.renamed', {

    'id': file_obj.id,
    'name': file_obj.name,

       })
         
    except (ValidationError, IntegrityError):
        return _json_error('A file with this name already exists here.')

    return JsonResponse({'success': True, 'id': file_obj.id, 'name': file_obj.name})


@login_required
@require_POST
def file_delete(request, file_id):
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)
    file_obj.soft_delete()
    broadcast_to_user(request.user.id, 'file.deleted', {

         'id': file_obj.id,
         'type': 'file',

         })
       
    return JsonResponse({'success': True, 'id': file_obj.id, 'type': 'file'})


@login_required
@require_POST
def file_move(request, file_id):
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)

    form = MoveItemForm(request.POST)
    form.fields['destination_folder'].queryset = Folder.objects.filter(
        owner=request.user, is_deleted=False
    )

    if not form.is_valid():
        return _json_error('Invalid destination.')

    file_obj.folder = form.cleaned_data['destination_folder']
    try:
        file_obj.full_clean(exclude=['upload'])
        file_obj.save()

        broadcast_to_user(request.user.id, 'file.moved', {

        'id': file_obj.id,

        })
    except (ValidationError, IntegrityError):
        return _json_error('A file with this name already exists in that folder.')

    return JsonResponse({'success': True, 'id': file_obj.id})


@login_required
@require_POST
def file_restore(request, file_id):
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=True)
    file_obj.restore()
    return JsonResponse({'success': True, 'id': file_obj.id})


@login_required
@require_POST
def file_permanent_delete(request, file_id):
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=True)
    file_obj.hard_delete()
    return JsonResponse({'success': True, 'id': file_id, 'type': 'file'})



@login_required
@require_POST
def file_schedule_delete(request, file_id):
    """
    Sets a scheduled deletion time on a file and queues a Celery task
    with eta= set to that exact datetime.
    """
    from drive.tasks import scheduled_file_delete

    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)

    delete_at_str = request.POST.get('delete_at')
    if not delete_at_str:
        return _json_error('No deletion time provided.')

    delete_at = parse_datetime(delete_at_str)
    if not delete_at:
        return _json_error('Invalid datetime format.')

    # Make timezone-aware if it isn't already
    if timezone.is_naive(delete_at):
        delete_at = timezone.make_aware(delete_at)

    if delete_at <= timezone.now():
        return _json_error('Scheduled time must be in the future.')

    # Save the scheduled time to the file record
    file_obj.scheduled_delete_at = delete_at
    file_obj.save(update_fields=['scheduled_delete_at'])

    # Queue the Celery task — eta means "don't run until this moment"
    scheduled_file_delete.apply_async(
        args=[file_obj.id],
        eta=delete_at,
    )

    return JsonResponse({
        'success': True,
        'scheduled_delete_at': delete_at.strftime('%b %d, %Y at %H:%M'),
    })


@login_required
@require_POST
def file_cancel_schedule(request, file_id):
    """
    Cancels a scheduled deletion by clearing the scheduled_delete_at field.
    The Celery task will see scheduled_delete_at is None at execution time
    and abort — we don't need to revoke the task from Redis.
    """
    file_obj = get_object_or_404(File, pk=file_id, owner=request.user, is_deleted=False)
    file_obj.scheduled_delete_at = None
    file_obj.save(update_fields=['scheduled_delete_at'])
    return JsonResponse({'success': True})


# ---------------------------------------------------------------------------
# Trash view
# ---------------------------------------------------------------------------

@login_required
def trash(request):
    folders = Folder.objects.filter(owner=request.user, is_deleted=True)
    files = File.objects.filter(owner=request.user, is_deleted=True)
    return render(request, 'drive/trash.html', {'folders': folders, 'files': files})