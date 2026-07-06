/*
  schedule.js
  Handles the scheduled deletion modal — opening it, setting a schedule,
  and cancelling an existing schedule.
  Loaded on the drive home page via {% block extra_js %}.
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

    const modalEl = document.getElementById('scheduleModal');
    if (!modalEl) return;

    const modal = new bootstrap.Modal(modalEl);

    // -----------------------------------------------------------------------
    // Open modal when "Schedule deletion" is clicked
    // -----------------------------------------------------------------------

    document.body.addEventListener('click', (e) => {
        const btn = e.target.closest('.schedule-btn');
        if (!btn) return;

        const id = btn.dataset.id;
        const name = btn.dataset.name;
        const scheduled = btn.dataset.scheduled; // existing schedule if any

        document.getElementById('scheduleFileId').value = id;
        document.getElementById('scheduleFileName').textContent = name;
        document.getElementById('scheduleError').classList.add('d-none');

        // Show existing schedule info if there is one
        const currentInfo = document.getElementById('scheduleCurrentInfo');
        if (scheduled) {
            document.getElementById('scheduleCurrentTime').textContent = formatDatetime(scheduled);
            currentInfo.classList.remove('d-none');
            // Pre-fill the picker with the existing schedule
            document.getElementById('scheduleDateTime').value = scheduled;
        } else {
            currentInfo.classList.add('d-none');
            document.getElementById('scheduleDateTime').value = '';
        }

        modal.show();
    });

    // -----------------------------------------------------------------------
    // Set schedule
    // -----------------------------------------------------------------------

    document.getElementById('scheduleConfirmBtn').addEventListener('click', async () => {
        const errorEl = document.getElementById('scheduleError');
        errorEl.classList.add('d-none');

        const fileId = document.getElementById('scheduleFileId').value;
        const deleteAt = document.getElementById('scheduleDateTime').value;

        if (!deleteAt) {
            errorEl.textContent = 'Please select a date and time.';
            errorEl.classList.remove('d-none');
            return;
        }

        // Convert datetime-local value to ISO format the server expects
        const isoDatetime = new Date(deleteAt).toISOString();

        const result = await postForm(`/file/${fileId}/schedule-delete/`, {
            delete_at: isoDatetime,
        });

        if (!result.success) {
            errorEl.textContent = result.error;
            errorEl.classList.remove('d-none');
            return;
        }

        modal.hide();
        window.showToast(
            `File will be deleted on ${result.scheduled_delete_at}.`,
            'info'
        );

        // Update the data-scheduled attribute on the button so re-opening
        // the modal shows the correct existing schedule
        document.querySelectorAll(`.schedule-btn[data-id="${fileId}"]`).forEach(btn => {
            btn.dataset.scheduled = deleteAt;
        });
    });

    // -----------------------------------------------------------------------
    // Cancel schedule
    // -----------------------------------------------------------------------

    document.getElementById('cancelScheduleBtn').addEventListener('click', async () => {
        const fileId = document.getElementById('scheduleFileId').value;

        const result = await postForm(`/file/${fileId}/cancel-schedule/`, {});

        if (!result.success) {
            window.showToast('Failed to cancel schedule.', 'error');
            return;
        }

        modal.hide();
        window.showToast('Scheduled deletion cancelled.', 'success');

        // Clear the data-scheduled attribute
        document.querySelectorAll(`.schedule-btn[data-id="${fileId}"]`).forEach(btn => {
            btn.dataset.scheduled = '';
        });
    });

    // -----------------------------------------------------------------------
    // Utility
    // -----------------------------------------------------------------------

    function formatDatetime(datetimeLocal) {
        // Converts "2026-07-10T14:30" to "Jul 10, 2026 at 14:30"
        const d = new Date(datetimeLocal);
        return d.toLocaleString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: false,
        });
    }

})();