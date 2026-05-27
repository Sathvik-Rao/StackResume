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
})();
