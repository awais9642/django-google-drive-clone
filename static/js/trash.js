document.addEventListener('DOMContentLoaded', () => {
    const csrfToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('csrftoken='))
        ?.split('=')[1];

    async function postForm(url) {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
        });
        return response.json();
    }

    document.body.addEventListener('click', async (e) => {
        if (e.target.matches('.trash-restore-btn')) {
            const id = e.target.dataset.id;
            const type = e.target.dataset.type;
            const url = type === 'folder' ? `/folder/${id}/restore/` : `/file/${id}/restore/`;
            const result = await postForm(url);
            if (result.success) {
                window.location.reload();
            } else {
                showToast(result.error || 'Restore failed.', 'error');  
            }
        }

        if (e.target.matches('.trash-permanent-delete-btn')) {
            if (!confirm('This will permanently delete the item. This cannot be undone. Continue?')) return;
            const id = e.target.dataset.id;
            const type = e.target.dataset.type;
            const url = type === 'folder' ? `/folder/${id}/permanent-delete/` : `/file/${id}/permanent-delete/`;
            const result = await postForm(url);
            if (result.success) {
                window.location.reload();
            } else {
               window.showToast(result.error || 'Delete failed.', 'error');
            }
        }
    });
});