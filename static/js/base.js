// Global JS shared across all pages.
// WebSocket connection logic (Phase 5) and notification handling (Phase 7)
// will be initialized from here.
console.log("BASE JS LOADED");
document.addEventListener('DOMContentLoaded', function () {
    console.log('Drive Clone app loaded.');
});

/*
  ADDITION TO base.js — paste at the bottom of the existing file.

  showToast(message, type, duration)
  ------------------------------------
  type: 'success' | 'error' | 'info'   (default: 'info')
  duration: milliseconds before auto-dismiss  (default: 3500)

  Usage from any page:
    showToast('File uploaded successfully.', 'success');
    showToast('A file with this name already exists.', 'error');
    showToast('John shared a file with you.', 'info');

  Phase 7 (notifications) and Phase 5 (real-time events) will both
  call this function to surface feedback without page reloads.
*/

window.showToast = function(message, type = 'info', duration = 3500) {
    console.log("TOAST CALLED");

    const container = document.body.querySelector('#toastContainer');

    if (!container) {
        console.error("Toast container not found!");
        return;
    }

    const toast = document.createElement('div');
    toast.className = `app-toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    console.log("Toast added to DOM");

    setTimeout(() => {
        toast.classList.add('toast-hiding');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
    }, duration);
};