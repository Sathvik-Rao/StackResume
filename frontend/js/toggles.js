// ── Memory toggle ───────────────────────────────────────────────────────────
function toggleMemPill(){
  const el=document.getElementById('mem-toggle');
  const willBeOn=el.classList.contains('off');
  el.classList.toggle('on',willBeOn);
  el.classList.toggle('off',!willBeOn);
}
function isMemoryOn(){
  return document.getElementById('mem-toggle').classList.contains('on');
}

// ── JD toggle ───────────────────────────────────────────────────────────────
function toggleJD(){
  const s=document.getElementById('jd-strip');
  s.classList.toggle('open');
  document.getElementById('jd-toggle').classList.toggle('on',s.classList.contains('open'));
  if(s.classList.contains('open'))document.getElementById('jd-textarea').focus();
}
function closeJD(){
  document.getElementById('jd-strip').classList.remove('open');
  document.getElementById('jd-toggle').classList.remove('on');
  document.getElementById('jd-textarea').value='';
  // Leave the slider where it is — its value is the user's remembered
  // preference, refreshed from the server on load.
}
function _jdIntensityLabel(v){
  if(v>=90)return'Full rewrite to match the JD';
  if(v>=65)return'Heavy tailoring — keep core content intact';
  if(v>=35)return'Moderate — tweak summary + a few bullets';
  if(v>=10)return'Light touch — 1–2 small adjustments';
  return'No tailoring — keep resume as-is';
}
function updateJdIntensityUI(){
  const sl=document.getElementById('jd-intensity');
  if(!sl)return;
  const v=parseInt(sl.value,10);
  const out=document.getElementById('jd-intensity-value');
  const hint=document.getElementById('jd-intensity-hint');
  if(out)out.textContent=`${v}%`;
  if(hint)hint.textContent=_jdIntensityLabel(v);
}
function getJdIntensity(){
  const sl=document.getElementById('jd-intensity');
  if(!sl)return 100;
  const v=parseInt(sl.value,10);
  return isNaN(v)?100:v;
}
