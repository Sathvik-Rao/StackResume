// ── Sidebar resize ───────────────────────────────────────────────────────────
// Drag the right edge of the sidebar to resize it. The chosen width is written
// to the --sw CSS variable (which drives both #sb width and min-width) and
// persisted to localStorage. The initial restore happens pre-paint in
// theme-init.js to avoid a width flash on load.
//
// The intended width is tracked in `currentWidth` rather than read back from the
// DOM, so the collapse animation and viewport-driven re-clamps never bake a
// transient/animated width into the variable.
(function () {
  const MIN = 200;
  const DEFAULT = 268;
  const STORE_KEY = 'sr_sidebar_w';

  // Cap so the main pane never gets squeezed below a usable width, and never
  // let the sidebar take more than ~60% of the viewport on small screens.
  function maxWidth() {
    return Math.max(MIN, Math.min(window.innerWidth - 360, window.innerWidth * 0.6, 600));
  }
  function clampWidth(w) {
    return Math.round(Math.max(MIN, Math.min(w, maxWidth())));
  }

  function readStored() {
    try {
      const w = parseInt(localStorage.getItem(STORE_KEY), 10);
      return (w && w >= MIN) ? w : DEFAULT;
    } catch (e) { return DEFAULT; }
  }

  let currentWidth = readStored();

  function applyWidth(w) {
    currentWidth = w;
    document.documentElement.style.setProperty('--sw', w + 'px');
  }

  function init() {
    const sb = document.getElementById('sb');
    const handle = document.getElementById('sb-resizer');
    if (!sb || !handle) return;

    // Reconcile with whatever theme-init applied pre-paint.
    applyWidth(clampWidth(currentWidth));

    let dragging = false;

    function onMove(e) {
      if (!dragging) return;
      const left = sb.getBoundingClientRect().left;
      applyWidth(clampWidth(e.clientX - left));
      e.preventDefault();
    }

    function onUp() {
      if (!dragging) return;
      dragging = false;
      sb.classList.remove('sb-resizing');
      document.body.classList.remove('sb-resizing');
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      try { localStorage.setItem(STORE_KEY, String(currentWidth)); } catch (e) {}
    }

    handle.addEventListener('pointerdown', (e) => {
      // Left button only; ignore when the sidebar is collapsed.
      if (e.button !== 0 || sb.classList.contains('collapsed')) return;
      dragging = true;
      sb.classList.add('sb-resizing');
      document.body.classList.add('sb-resizing');
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
      e.preventDefault();
    });

    // Double-click the handle to reset to the default width.
    handle.addEventListener('dblclick', () => {
      applyWidth(DEFAULT);
      try { localStorage.removeItem(STORE_KEY); } catch (e) {}
    });

    // On viewport shrink, re-clamp the *intended* width (never the live/animated
    // DOM width) so a wide sidebar can't strand the main pane.
    window.addEventListener('resize', () => {
      const w = clampWidth(currentWidth);
      if (w !== currentWidth) applyWidth(w);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
