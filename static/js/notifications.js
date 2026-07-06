/*
  notifications.js
  Loaded on every authenticated page (added to base.html).
  Handles:
  - Fetching unread count on page load → updates badge
  - Loading notification list when bell is clicked
  - Mark single notification as read on click
  - Mark all as read button
  - Receiving live notification events from WebSocket (websocket.js calls
    window.onLiveNotification which is defined here)
*/

(function () {
    const CSRF_TOKEN = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];

    // -----------------------------------------------------------------------
    // Badge management
    // -----------------------------------------------------------------------

    let unreadCount = 0;

    function setBadge(count) {
        unreadCount = count;
        const badge = document.getElementById('notifBadge');
        if (!badge) return;

        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }

    function incrementBadge() {
        setBadge(unreadCount + 1);
    }

    function resetBadge() {
        setBadge(0);
    }

    // Fetch initial unread count on page load
    async function fetchUnreadCount() {
        try {
            const res = await fetch('/notifications/unread-count/');
            const data = await res.json();
            setBadge(data.count || 0);
        } catch (e) {
            // Non-fatal — badge stays at 0
        }
    }

    // -----------------------------------------------------------------------
    // Notification list (dropdown)
    // -----------------------------------------------------------------------

    async function loadNotifications() {
        const list = document.getElementById('notifList');
        const empty = document.getElementById('notifEmpty');
        if (!list) return;

        list.innerHTML = '<div class="text-muted small text-center py-3">Loading...</div>';

        try {
            const res = await fetch('/notifications/');
            const data = await res.json();

            list.innerHTML = '';

            if (!data.notifications || data.notifications.length === 0) {
                list.innerHTML = '<div class="text-muted small text-center py-3">No notifications yet.</div>';
                return;
            }

            data.notifications.forEach(n => {
                list.appendChild(buildNotifItem(n));
            });

        } catch (e) {
            list.innerHTML = '<div class="text-muted small text-center py-3 text-danger">Failed to load.</div>';
        }
    }

    function buildNotifItem(n) {
        const div = document.createElement('div');
        div.className = `notif-item ${n.is_read ? '' : 'unread'}`;
        div.dataset.notifId = n.id;
        div.dataset.link = n.link || '';

        div.innerHTML = `
            <div class="d-flex justify-content-between align-items-start">
                <span>${escapeHtml(n.message)}</span>
                ${!n.is_read ? '<span class="ms-2 text-primary small flex-shrink-0">●</span>' : ''}
            </div>
            <div class="notif-item-time mt-1">${escapeHtml(n.created_at)}</div>`;

        div.addEventListener('click', () => handleNotifClick(n.id, n.link, div));
        return div;
    }

    async function handleNotifClick(notifId, link, el) {
        // Mark as read
        if (el.classList.contains('unread')) {
            try {
                await fetch(`/notifications/${notifId}/read/`, {
                    method: 'POST',
                    headers: { 'X-CSRFToken': CSRF_TOKEN },
                });
                el.classList.remove('unread');
                const dot = el.querySelector('.text-primary');
                if (dot) dot.remove();
                setBadge(Math.max(0, unreadCount - 1));
            } catch (e) { /* non-fatal */ }
        }

        // Navigate if there's a link
        if (link) {
            window.location.href = link;
        }
    }

    // -----------------------------------------------------------------------
    // Mark all as read
    // -----------------------------------------------------------------------

    document.getElementById('markAllReadBtn')?.addEventListener('click', async (e) => {
        e.stopPropagation(); // prevent dropdown from closing

        try {
            await fetch('/notifications/mark-all-read/', {
                method: 'POST',
                headers: { 'X-CSRFToken': CSRF_TOKEN },
            });

            // Update all items in the dropdown to read state
            document.querySelectorAll('.notif-item.unread').forEach(el => {
                el.classList.remove('unread');
                const dot = el.querySelector('.text-primary');
                if (dot) dot.remove();
            });

            resetBadge();
        } catch (e) { /* non-fatal */ }
    });

    // -----------------------------------------------------------------------
    // Bell click → load notifications
    // -----------------------------------------------------------------------

    document.getElementById('notifBellBtn')?.addEventListener('shown.bs.dropdown', () => {
        loadNotifications();
    });

    // -----------------------------------------------------------------------
    // Live notification handler (called by websocket.js)
    // -----------------------------------------------------------------------

    window.onLiveNotification = function (data) {
        // Show toast
        if (window.showToast) {
            window.showToast(data.message, data.notif_type || 'info');
        }

        // Increment badge
        incrementBadge();

        // If dropdown is currently open, prepend the new notification
        const dropdown = document.getElementById('notifDropdown');
        const isOpen = dropdown && dropdown.classList.contains('show');

        if (isOpen) {
            const list = document.getElementById('notifList');
            const emptyMsg = list.querySelector('.text-muted');
            if (emptyMsg) emptyMsg.remove();

            const tempNotif = {
                id: data.id || Date.now(),
                message: data.message,
                notif_type: data.notif_type,
                is_read: false,
                link: data.link || '',
                created_at: data.created_at || 'Just now',
            };
            list.prepend(buildNotifItem(tempNotif));
        }
    };

    // -----------------------------------------------------------------------
    // Utility
    // -----------------------------------------------------------------------

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    // -----------------------------------------------------------------------
    // Init
    // -----------------------------------------------------------------------

    fetchUnreadCount();

})();