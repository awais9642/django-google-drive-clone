// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

const CSRF_TOKEN = getCookie('csrftoken');

async function postForm(url, data) {
    const formData = new URLSearchParams();
    for (const key in data) {
        if (data[key] !== null && data[key] !== undefined) {
            formData.append(key, data[key]);
        }
    }
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'X-CSRFToken': CSRF_TOKEN,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData,
    });
    return response.json();
}

async function postFile(url, file, extraFields) {
    const formData = new FormData();
    formData.append('upload', file);
    for (const key in extraFields) {
        if (extraFields[key] !== null && extraFields[key] !== undefined) {
            formData.append(key, extraFields[key]);
        }
    }
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF_TOKEN },
        body: formData,
    });
    return response.json();
}

function showError(elId, message) {
    const el = document.getElementById(elId);
    el.textContent = message;
    el.classList.remove('d-none');
}

function hideError(elId) {
    document.getElementById(elId).classList.add('d-none');
}

// ---------------------------------------------------------------------------
// View toggle (grid / list)
// ---------------------------------------------------------------------------

function initViewToggle() {
    const gridView = document.getElementById('gridView');
    const listView = document.getElementById('listView');
    const buttons = document.querySelectorAll('.view-toggle-btn');

    // Remember preference across page loads (per-browser, not synced — that's fine)
    const saved = localStorage.getItem('driveView') || 'grid';
    applyView(saved);

    buttons.forEach(btn => {
        btn.addEventListener('click', () => {
            const view = btn.dataset.view;
            applyView(view);
            localStorage.setItem('driveView', view);
        });
    });

    function applyView(view) {
        buttons.forEach(b => b.classList.toggle('active', b.dataset.view === view));
        if (view === 'grid') {
            gridView.classList.remove('d-none');
            listView.classList.add('d-none');
        } else {
            gridView.classList.add('d-none');
            listView.classList.remove('d-none');
        }
    }
}

// ---------------------------------------------------------------------------
// Create folder
// ---------------------------------------------------------------------------

function initCreateFolder() {
    const confirmBtn = document.getElementById('createFolderConfirmBtn');
    const input = document.getElementById('newFolderName');
    const modalEl = document.getElementById('folderModal');
    const modal = new bootstrap.Modal(modalEl);

    confirmBtn.addEventListener('click', async () => {
        hideError('folderModalError');
        const name = input.value.trim();
        if (!name) {
            showError('folderModalError', 'Folder name cannot be empty.');
            return;
        }

        const result = await postForm('/folder/create/', {
            name: name,
            parent_id: window.CURRENT_FOLDER_ID,
        });

        if (!result.success) {
            showError('folderModalError', result.error);
            return;
        }

        // Reload is the simplest reliable way to show the new folder correctly
        // sorted/placed right now. Phase 5 (real-time) will replace this with
        // a live DOM insert broadcast over WebSocket instead of a reload.
        window.location.reload();
    });

    modalEl.addEventListener('shown.bs.modal', () => {
        input.value = '';
        hideError('folderModalError');
        input.focus();
    });
}

// ---------------------------------------------------------------------------
// Upload (button + drag-and-drop)
// ---------------------------------------------------------------------------

function initUpload() {
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    const dropZone = document.getElementById('dropZone');

    uploadBtn.addEventListener('click', () => fileInput.click());

    fileInput.addEventListener('change', async () => {
        if (fileInput.files.length === 0) return;
        await uploadFile(fileInput.files[0]);
        fileInput.value = '';
    });

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('drag-over');
        });
    });

    dropZone.addEventListener('drop', async (e) => {
        const files = e.dataTransfer.files;
        for (const file of files) {
            await uploadFile(file);
        }
    });

    async function uploadFile(file) {
        const result = await postFile('/file/upload/', file, {
            folder_id: window.CURRENT_FOLDER_ID,
        });
        if (!result.success) {
           window.showToast(result.error || 'Delete failed.', 'error');// simple for now; Phase 7 notifications will replace this
            return;
        }
        window.location.reload();
    }
}

// ---------------------------------------------------------------------------
// Rename (delegated — works for dynamically present items)
// ---------------------------------------------------------------------------

function initRename() {
    const modalEl = document.getElementById('renameModal');
    const modal = new bootstrap.Modal(modalEl);
    const input = document.getElementById('renameInput');
    const targetIdField = document.getElementById('renameTargetId');
    const targetTypeField = document.getElementById('renameTargetType');
    const confirmBtn = document.getElementById('renameConfirmBtn');

    document.body.addEventListener('click', (e) => {
        if (e.target.matches('.rename-btn')) {
            targetIdField.value = e.target.dataset.id;
            targetTypeField.value = e.target.dataset.type;
            input.value = e.target.dataset.name;
            hideError('renameModalError');
            modal.show();
        }
    });

    confirmBtn.addEventListener('click', async () => {
        hideError('renameModalError');
        const name = input.value.trim();
        if (!name) {
            showError('renameModalError', 'Name cannot be empty.');
            return;
        }

        const type = targetTypeField.value;
        const id = targetIdField.value;
        const url = type === 'folder' ? `/folder/${id}/rename/` : `/file/${id}/rename/`;

        const result = await postForm(url, { name });

        if (!result.success) {
            showError('renameModalError', result.error);
            return;
        }
        window.location.reload();
    });
}

// ---------------------------------------------------------------------------
// Move
// ---------------------------------------------------------------------------

function initMove() {
    const modalEl = document.getElementById('moveModal');
    const modal = new bootstrap.Modal(modalEl);
    const select = document.getElementById('moveDestinationSelect');
    const targetIdField = document.getElementById('moveTargetId');
    const targetTypeField = document.getElementById('moveTargetType');
    const confirmBtn = document.getElementById('moveConfirmBtn');

    document.body.addEventListener('click', (e) => {
        if (e.target.matches('.move-btn')) {
            targetIdField.value = e.target.dataset.id;
            targetTypeField.value = e.target.dataset.type;
            hideError('moveModalError');
            modal.show();
        }
    });

    confirmBtn.addEventListener('click', async () => {
        hideError('moveModalError');
        const type = targetTypeField.value;
        const id = targetIdField.value;
        const url = type === 'folder' ? `/folder/${id}/move/` : `/file/${id}/move/`;

        const result = await postForm(url, {
            destination_folder: select.value,
        });

        if (!result.success) {
            showError('moveModalError', result.error);
            return;
        }
        window.location.reload();
    });
}

// ---------------------------------------------------------------------------
// Delete (soft delete -> Trash)
// ---------------------------------------------------------------------------

function initDelete() {
    document.body.addEventListener('click', async (e) => {
        if (!e.target.matches('.delete-btn')) return;

        const id = e.target.dataset.id;
        const type = e.target.dataset.type;

        if (!confirm(`Move this ${type} to Trash?`)) return;

        const url = type === 'folder' ? `/folder/${id}/delete/` : `/file/${id}/delete/`;
        const result = await postForm(url, {});

        if (!result.success) {
           window.showToast(result.error || 'Delete failed.', 'error');
            return;
        }

        // Remove from DOM with a fade-out rather than a full reload —
        // this is the same pattern Phase 5's WebSocket handler will reuse
        // when a *different* tab triggers the delete.
         document.querySelectorAll(`[data-id="${id}"][data-type="${type}"]`).forEach(el => {
             el.classList.add('removing');
             setTimeout(() => el.remove(), 200);
         });
     });
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
    initViewToggle();
    initCreateFolder();
    initUpload();
    initRename();
    initMove();
    initDelete();
});