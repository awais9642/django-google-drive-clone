/*
  websocket.js
  Loaded on every authenticated page (added to base.html).
  Opens one WebSocket connection per tab, handles all real-time events.

  Event handlers update the DOM directly so the page reflects changes
  from other tabs instantly, without a reload.
*/

(function () {
    // Only connect if the user is authenticated.
    // The template sets window.IS_AUTHENTICATED via a script tag in base.html.
    if (!window.IS_AUTHENTICATED) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = `${protocol}://${window.location.host}/ws/drive/`;

    let socket;
    let reconnectDelay = 1000; // starts at 1s, backs off on repeated failures

    function connect() {
        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            reconnectDelay = 1000; // reset backoff on successful connection
        };

        socket.onmessage = (e) => {
            let payload;
            try {
                payload = JSON.parse(e.data);
            } catch {
                return;
            }
            handleEvent(payload.event, payload.data);
        };

        socket.onclose = () => {
            // Auto-reconnect with exponential backoff (capped at 30s).
            // This handles the server restarting, Redis blip, etc.
            setTimeout(connect, reconnectDelay);
            reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        };

        socket.onerror = () => {
            socket.close(); // triggers onclose which triggers reconnect
        };
    }

    // -----------------------------------------------------------------------
    // Event router
    // -----------------------------------------------------------------------

    function handleEvent(event, data) {
        switch (event) {
            case 'file_created':    onFileCreated(data);    break;
            case 'file_deleted':    onItemDeleted(data);    break;
            case 'file_renamed':    onItemRenamed(data);    break;
            case 'file_moved':      onItemMoved(data);      break;
            case 'folder_created':  onFolderCreated(data);  break;
            case 'folder_deleted':  onItemDeleted(data);    break;
            case 'folder_renamed':  onItemRenamed(data);    break;
            case 'folder_moved':    onItemMoved(data);      break;
            case 'notification':    onNotification(data);   break;
        }
    }

    // -----------------------------------------------------------------------
    // DOM helpers
    // -----------------------------------------------------------------------

    function getCurrentFolderId() {
        // Set in the drive/home.html template as window.CURRENT_FOLDER_ID
        return window.CURRENT_FOLDER_ID !== undefined ? window.CURRENT_FOLDER_ID : null;
    }

    function removeItem(id, type) {
        // Removes from both grid and list view simultaneously
        document.querySelectorAll(
            `[data-id="${id}"][data-type="${type}"]`
        ).forEach(el => {
            el.classList.add('removing');
            el.addEventListener('animationend', () => el.remove(), { once: true });
        });
    }

    function updateItemName(id, type, newName) {
        document.querySelectorAll(
            `[data-id="${id}"][data-type="${type}"]`
        ).forEach(el => {
            // Update the visible name span/link in both grid and list views
            const nameEl = el.querySelector('.drive-item-name') || el.querySelector('a');
            if (nameEl) {
                // Preserve any icon prefix in the list view anchor (e.g. "📁 ")
                const icon = nameEl.textContent.match(/^[^\w]*/)?.[0] || '';
                nameEl.textContent = icon + newName;
            }
            // Update the data-name attribute so rename modal pre-fills correctly
            const renameBtn = el.querySelector('.rename-btn');
            if (renameBtn) renameBtn.dataset.name = newName;
        });
    }

    function buildFolderCard(data) {
        // Mirrors the structure in templates/drive/partials/folder_card.html
        const div = document.createElement('div');
        div.className = 'app-card drive-item folder-item fade-in-item';
        div.dataset.id = data.id;
        div.dataset.type = 'folder';
        div.innerHTML = `
            <a href="/folder/${data.id}/" class="drive-item-link">
                <div class="drive-item-icon folder-icon">📁</div>
                <div class="drive-item-name">${escapeHtml(data.name)}</div>
            </a>
            <div class="dropdown drive-item-menu">
                <button class="btn btn-sm btn-light" data-bs-toggle="dropdown">⋮</button>
                <ul class="dropdown-menu">
                    <li><button class="dropdown-item rename-btn" data-id="${data.id}" data-type="folder" data-name="${escapeHtml(data.name)}">Rename</button></li>
                    <li><button class="dropdown-item move-btn" data-id="${data.id}" data-type="folder">Move</button></li>
                    <li><button class="dropdown-item text-danger delete-btn" data-id="${data.id}" data-type="folder">Delete</button></li>
                </ul>
            </div>`;
        return div;
    }

    function buildFileCard(data) {
        // Mirrors templates/drive/partials/file_card.html
        const div = document.createElement('div');
        div.className = 'app-card drive-item file-item fade-in-item';
        div.dataset.id = data.id;
        div.dataset.type = 'file';
        div.innerHTML = `
            <a href="/media/user_${data.owner_id || ''}/" class="drive-item-link" target="_blank">
                <div class="drive-item-icon file-icon">📄</div>
                <div class="drive-item-name">${escapeHtml(data.name)}</div>
            </a>
            <div class="dropdown drive-item-menu">
                <button class="btn btn-sm btn-light" data-bs-toggle="dropdown">⋮</button>
                <ul class="dropdown-menu">
                    <li><button class="dropdown-item rename-btn" data-id="${data.id}" data-type="file" data-name="${escapeHtml(data.name)}">Rename</button></li>
                    <li><button class="dropdown-item move-btn" data-id="${data.id}" data-type="file">Move</button></li>
                    <li><button class="dropdown-item text-danger delete-btn" data-id="${data.id}" data-type="file">Delete</button></li>
                </ul>
            </div>`;
        return div;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // -----------------------------------------------------------------------
    // Event handlers
    // -----------------------------------------------------------------------

    function onFileCreated(data) {
        // Only insert if we're currently viewing the folder this file belongs to
        const currentFolderId = getCurrentFolderId();
        const fileFolderId = data.folder_id === null ? null : Number(data.folder_id);

        if (currentFolderId !== fileFolderId) return;

        // Don't double-insert if the item already exists (this tab made the action)
        if (document.querySelector(`[data-id="${data.id}"][data-type="file"]`)) return;

        const gridView = document.getElementById('gridView');
        if (gridView) gridView.appendChild(buildFileCard(data));

        const listBody = document.querySelector('#listView tbody');
        if (listBody) {
            const tr = document.createElement('tr');
            tr.dataset.id = data.id;
            tr.dataset.type = 'file';
            tr.className = 'drive-item-row fade-in-item';
            tr.innerHTML = `
                <td>📄 ${escapeHtml(data.name)}</td>
                <td>File</td>
                <td>${formatBytes(data.size)}</td>
                <td>${data.created_at}</td>
                <td>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-light" data-bs-toggle="dropdown">⋮</button>
                        <ul class="dropdown-menu">
                            <li><button class="dropdown-item rename-btn" data-id="${data.id}" data-type="file" data-name="${escapeHtml(data.name)}">Rename</button></li>
                            <li><button class="dropdown-item move-btn" data-id="${data.id}" data-type="file">Move</button></li>
                            <li><button class="dropdown-item text-danger delete-btn" data-id="${data.id}" data-type="file">Delete</button></li>
                        </ul>
                    </div>
                </td>`;
            listBody.appendChild(tr);
        }

        // Remove empty state message if it was showing
        document.getElementById('emptyState')?.remove();
    }

    function onFolderCreated(data) {
        const currentFolderId = getCurrentFolderId();
        const parentId = data.parent_id === null ? null : Number(data.parent_id);

        if (currentFolderId !== parentId) return;
        if (document.querySelector(`[data-id="${data.id}"][data-type="folder"]`)) return;

        const gridView = document.getElementById('gridView');
        if (gridView) gridView.prepend(buildFolderCard(data));

        const listBody = document.querySelector('#listView tbody');
        if (listBody) {
            const tr = document.createElement('tr');
            tr.dataset.id = data.id;
            tr.dataset.type = 'folder';
            tr.className = 'drive-item-row fade-in-item';
            tr.innerHTML = `
                <td><a href="/folder/${data.id}/">📁 ${escapeHtml(data.name)}</a></td>
                <td>Folder</td>
                <td>—</td>
                <td>${data.created_at}</td>
                <td>
                    <div class="dropdown">
                        <button class="btn btn-sm btn-light" data-bs-toggle="dropdown">⋮</button>
                        <ul class="dropdown-menu">
                            <li><button class="dropdown-item rename-btn" data-id="${data.id}" data-type="folder" data-name="${escapeHtml(data.name)}">Rename</button></li>
                            <li><button class="dropdown-item move-btn" data-id="${data.id}" data-type="folder">Move</button></li>
                            <li><button class="dropdown-item text-danger delete-btn" data-id="${data.id}" data-type="folder">Delete</button></li>
                        </ul>
                    </div>
                </td>`;
            listBody.prepend(tr);
        }

        document.getElementById('emptyState')?.remove();
    }

    function onItemDeleted(data) {
        removeItem(data.id, data.type);
    }

    function onItemRenamed(data) {
        // We don't know if it's file or folder from just the event name in
        // the data, so try both — only the matching element will update.
        updateItemName(data.id, 'file', data.name);
        updateItemName(data.id, 'folder', data.name);
    }

    function onItemMoved(data) {
        // An item that was moved might no longer belong in the current folder view.
        // Simplest correct behavior: remove it from the current view. The user
        // can navigate to the destination to see it there.
        removeItem(data.id, 'file');
        removeItem(data.id, 'folder');
    }

    function onNotification(data) {
         // Delegate to notifications.js which handles both toast and dropdown update
        if (window.onLiveNotification) {
        window.onLiveNotification(data);
    } else if (window.showToast) {
        // Fallback if notifications.js hasn't loaded yet
        window.showToast(data.message, data.notif_type || 'info');
    }
    }

    // -----------------------------------------------------------------------
    // Utility
    // -----------------------------------------------------------------------

    function formatBytes(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // -----------------------------------------------------------------------
    // Start connection
    // -----------------------------------------------------------------------

    connect();

})();