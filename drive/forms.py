from django import forms
from .models import Folder, File


class FolderForm(forms.ModelForm):
    """Used for both create and rename — same shape, different save context."""
    class Meta:
        model = Folder
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Untitled folder'}),
        }

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError("Folder name cannot be empty.")
        return name


class FileUploadForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['upload']


class FileRenameForm(forms.ModelForm):
    class Meta:
        model = File
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError("File name cannot be empty.")
        return name


class MoveItemForm(forms.Form):
    """
    Generic move form for both files and folders. destination_folder is
    null = move to root (My Drive top level).
    """
    destination_folder = forms.ModelChoiceField(
        queryset=Folder.objects.none(),  # populated per-request in the view (user-scoped)
        required=False,
        empty_label="My Drive (root)"
    )