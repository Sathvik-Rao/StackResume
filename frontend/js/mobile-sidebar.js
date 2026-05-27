// ── Mobile sidebar ───────────────────────────────────────────────────────────
function openMobileSidebar(){
  const sb=document.getElementById('sb');
  sb.classList.remove('collapsed');   // collapsed class clips overflow/width — must remove
  sb.classList.add('mobile-open');
  document.getElementById('sb-overlay').classList.add('show');
}
function closeMobileSidebar(){
  document.getElementById('sb').classList.remove('mobile-open');
  document.getElementById('sb-overlay').classList.remove('show');
}
