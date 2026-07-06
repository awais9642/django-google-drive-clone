/*
  sharing.js
  Handles the Share modal: user search autocomplete, share action,
  and the access management panel (list, update permission, revoke).
  Loaded only on the drive home page via {% block extra_js %}.
*/

(function () {
    const CSRF_TOKEN = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];

    async function postForm(url, data) {
        const formData = new URLSearchParams(data);
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': CSRF_TOKEN,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData,
        });
        return res.json();
    }

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------

    let selectedUserId = null;
    let selectedUsername = null;
    let searchTimeout = null;

    // -----------------------------------------------------------------------
    // Open modal when "Share" button is clicked
    // -----------------------------------------------------------------------

    document.body.addEventListener('click', (e) => {
        if (!e.target.matches('.share-btn')) return;

        const id = e.target.dataset.id;
        const type = e.target.dataset.type;
        const name = e.target.dataset.name;

        // Set hidden fields
        document.getElementById('shareItemId').value = id;
        document.getElementById('shareItemType').value = type;
        document.getElementById('shareItemName').textContent = name;

        // Reset state
        resetShareModal();

        // Load existing access list
        loadAccessList(id, type);

        new bootstrap.Modal(document.getElementById('shareModal')).show();
    });

    function resetShareModal() {
        selectedUserId = null;
        selectedUsername = null;
        document.getElementById('shareUserSearch').value = '';
        document.getElementById('shareUserResults').innerHTML = '';
        document.getElementById('shareSelectedUser').classList.add('d-none');
        document.getElementById('shareError').classList.add('d-none');
    }

    // -----------------------------------------------------------------------
    // User search autocomplete
    // -----------------------------------------------------------------------

    document.getElementById('shareUserSearch').addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const q = e.target.value.trim();

        if (q.length < 2) {
            document.getElementById('shareUserResults').innerHTML = '';
            return;
        }

        // Debounce — don't fire on every keystroke
        searchTimeout = setTimeout(async () => {
            const res = await fetch(`/sharing/users/search/?q=${encodeURIComponent(q)}`);
            const data = await res.json();

            const container = document.getElementById('shareUserResults');
            container.innerHTML = '';

            if (data.users.length === 0) {
                container.innerHTML = '<div class="list-group-item text-muted">No users found</div>';
                return;
            }

            data.users.forEach(user => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'list-group-item list-group-item-action';
                item.innerHTML = `<strong>${escapeHtml(user.username)}</strong>
                    <span class="text-muted ms-2 small">${escapeHtml(user.email)}</span>`;

                item.addEventListener('click', () => {
                    selectUser(user.id, user.username);
                    container.innerHTML = '';
                    document.getElementById('shareUserSearch').value = '';
                });

                container.appendChild(item);
            });
        }, 250);
    });

    function selectUser(id, username) {
        selectedUserId = id;
        selectedUsername = username;
        document.getElementById('shareSelectedUsername').textContent = username;
        document.getElementById('shareSelectedUser').classList.remove('d-none');
    }

    document.getElementById('shareClearUser').addEventListener('click', () => {
        selectedUserId = null;
        selectedUsername = null;
        document.getElementById('shareSelectedUser').classList.add('d-none');
        document.getElementById('shareUserSearch').value = '';
    });

    // -----------------------------------------------------------------------
    // Share confirm
    // -----------------------------------------------------------------------

    document.getElementById('shareConfirmBtn').addEventListener('click', async () => {
        const errorEl = document.getElementById('shareError');
        errorEl.classList.add('d-none');

        if (!selectedUserId) {
            errorEl.textContent = 'Please search for and select a user first.';
            errorEl.classList.remove('d-none');
            return;
        }

        const itemId = document.getElementById('shareItemId').value;
        const itemType = document.getElementById('shareItemType').value;
        const permission = document.getElementById('sharePermission').value;

        const result = await postForm('/sharing/share/', {
            item_type: itemType,
            item_id: itemId,
            shared_with_id: selectedUserId,
            permission: permission,
        });

        if (!result.success) {
            errorEl.textContent = result.error;
            errorEl.classList.remove('d-none');
            return;
        }

        window.showToast(`Shared with ${selectedUsername}.`, 'success');
        resetShareModal();

        // Refresh the access list to show the new entry
        loadAccessList(itemId, itemType);
    });

    // -----------------------------------------------------------------------
    // Access management panel
    // -----------------------------------------------------------------------

    async function loadAccessList(itemId, itemType) {
        const container = document.getElementById('shareAccessList');
        container.innerHTML = '<div class="text-muted small">Loading...</div>';

        const res = await fetch(`/sharing/access/?item_type=${itemType}&item_id=${itemId}`);
        const data = await res.json();

        if (!data.accesses || data.accesses.length === 0) {
            container.innerHTML = '<div class="text-muted small">Not shared with anyone yet.</div>';
            return;
        }

        container.innerHTML = '';

        data.accesses.forEach(access => {
            const row = document.createElement('div');
            row.className = 'd-flex align-items-center justify-content-between mb-2';
            row.dataset.accessId = access.id;
            row.innerHTML = `
                <div>
                    <strong>${escapeHtml(access.shared_with)}</strong>
                    <span class="text-muted small ms-1">${escapeHtml(access.shared_with_email)}</span>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <select class="form-select form-select-sm permission-select" style="width:120px">
                        <option value="view" ${access.permission === 'view' ? 'selected' : ''}>View</option>
                        <option value="edit" ${access.permission === 'edit' ? 'selected' : ''}>Edit</option>
                    </select>
                    <button class="btn btn-sm btn-outline-danger revoke-btn">Revoke</button>
                </div>`;
            container.appendChild(row);
        });
    }

    // Update permission
    document.getElementById('shareAccessList').addEventListener('change', async (e) => {
        if (!e.target.matches('.permission-select')) return;

        const row = e.target.closest('[data-access-id]');
        const accessId = row.dataset.accessId;
        const permission = e.target.value;

        const result = await postForm(`/sharing/access/${accessId}/update/`, { permission });

        if (!result.success) {
            window.showToast(result.error, 'error');
            // Revert the select
            e.target.value = e.target.value === 'view' ? 'edit' : 'view';
            return;
        }

        window.showToast('Permission updated.', 'success');
    });

    // Revoke access
    document.getElementById('shareAccessList').addEventListener('click', async (e) => {
        if (!e.target.matches('.revoke-btn')) return;

        if (!confirm('Remove this person\'s access?')) return;

        const row = e.target.closest('[data-access-id]');
        const accessId = row.dataset.accessId;

        const result = await postForm(`/sharing/access/${accessId}/revoke/`, {});

        if (!result.success) {
            window.showToast(result.error, 'error');
            return;
        }

        row.remove();
        window.showToast('Access revoked.', 'success');

        // Show empty state if no more rows
        const container = document.getElementById('shareAccessList');
        if (container.children.length === 0) {
            container.innerHTML = '<div class="text-muted small">Not shared with anyone yet.</div>';
        }
    });

    // -----------------------------------------------------------------------
    // Utility
    // -----------------------------------------------------------------------

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

})();