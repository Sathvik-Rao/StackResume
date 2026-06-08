// FOUC-prevention: resolve theme synchronously before first paint.
// Must run in <head> with no `defer`/`async` — otherwise the first frame
// renders against the wrong theme and flashes.
(function () {
  try {
    var pref = localStorage.getItem('sr_theme') || 'system';
    var eff = pref === 'system'
      ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
      : pref;
    document.documentElement.setAttribute('data-theme', eff);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
  // Restore the saved sidebar width pre-paint so it doesn't flash at the
  // default. The drag handler (sidebar-resize.js) maintains this value.
  try {
    var w = parseInt(localStorage.getItem('sr_sidebar_w'), 10);
    if (w && w >= 200 && w <= 600) {
      document.documentElement.style.setProperty('--sw', w + 'px');
    }
  } catch (e) {}
})();
