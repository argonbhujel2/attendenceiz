/* My Attendance — Client JS */
(function () {
  'use strict';

  // Mobile sidebar toggle
  const menuToggle = document.getElementById('menu-toggle');
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');

  function openSidebar() {
    if (sidebar) sidebar.classList.add('open');
    if (overlay) overlay.classList.add('open');
  }
  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('open');
  }

  if (menuToggle) menuToggle.addEventListener('click', openSidebar);
  if (overlay) overlay.addEventListener('click', closeSidebar);

  // Live clock (Nepal time approximation via offset if server didn't inject)
  const timeEl = document.getElementById('live-time');
  if (timeEl) {
    function updateClock() {
      // Use browser local time; server already uses Asia/Kathmandu for logic
      const now = new Date();
      const h = String(now.getHours()).padStart(2, '0');
      const m = String(now.getMinutes()).padStart(2, '0');
      const s = String(now.getSeconds()).padStart(2, '0');
      timeEl.textContent = `${h}:${m}:${s}`;
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  // Auto-dismiss flash messages
  document.querySelectorAll('.alert').forEach(function (el) {
    setTimeout(function () {
      el.style.transition = 'opacity 0.4s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 400);
    }, 5000);
  });

  // Confirm destructive actions
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (!confirm(el.getAttribute('data-confirm'))) {
        e.preventDefault();
      }
    });
  });

  // Form submit loading state
  document.querySelectorAll('form[data-loading]').forEach(function (form) {
    form.addEventListener('submit', function () {
      const btn = form.querySelector('button[type="submit"]');
      if (btn) {
        btn.disabled = true;
        const original = btn.innerHTML;
        btn.innerHTML = '<span class="spinner"></span> Saving…';
        // Re-enable after timeout as safety
        setTimeout(function () {
          btn.disabled = false;
          btn.innerHTML = original;
        }, 8000);
      }
    });
  });

  // Manual entry: show BS date preview if possible
  const dateInput = document.getElementById('attendance_date');
  const bsPreview = document.getElementById('bs-date-preview');
  if (dateInput && bsPreview) {
    dateInput.addEventListener('change', function () {
      // Client-side cannot convert to BS without library; server handles display
      bsPreview.textContent = dateInput.value ? 'Date selected (B.S. shown after save)' : '';
    });
  }

  // PWA install prompt
  let deferredPrompt;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;
    const installBtn = document.getElementById('install-pwa');
    if (installBtn) {
      installBtn.classList.remove('hidden');
      installBtn.addEventListener('click', function () {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function () {
          deferredPrompt = null;
          installBtn.classList.add('hidden');
        });
      });
    }
  });

  // Offline detection
  function updateOnlineStatus() {
    const banner = document.getElementById('offline-banner');
    if (!banner) return;
    if (!navigator.onLine) {
      banner.classList.remove('hidden');
    } else {
      banner.classList.add('hidden');
    }
  }
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);
  updateOnlineStatus();
})();
