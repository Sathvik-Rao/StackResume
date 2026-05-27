// ── Keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener('keydown',e=>{
  const mod=e.metaKey||e.ctrlKey;
  // Close any open modal on Escape
  if(e.key==='Escape'){
    const open=document.querySelector('.ov.open');
    if(open){const mx=open.querySelector('.mx');if(mx)mx.click();return;}
  }
  // Don't fire shortcuts when typing in inputs/textareas
  const tag=(e.target.tagName||'').toLowerCase();
  if(!mod&&(tag==='input'||tag==='textarea'||tag==='select'))return;
  if(mod&&e.key==='k'){e.preventDefault();document.getElementById('sb-search').focus();}
  if(mod&&e.key==='n'){e.preventDefault();newChat();}
  if(mod&&e.key===','){ e.preventDefault();openSettings();}
  if(mod&&e.key==='Enter'){e.preventDefault();sendMsg();}
});
