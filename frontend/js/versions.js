// ── Resume version tracking (for diff) ───────────────────────────────────────
const _resumeVersions={};

// ── Auto-title from JD/resume metadata ───────────────────────────────────────
async function _autoTitleSession(sessionId,resumeJson){
  const sess=_allSessions.find(s=>s.id===sessionId);
  if(!sess||sess.title!=='New Resume')return;
  const meta=resumeJson.metadata||{};
  const title=(meta.jd_role||resumeJson.personal_info?.professional_title||'').trim();
  if(!title)return;
  await fetch(`${API}/api/sessions/${sessionId}`,{
    method:'PATCH',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({title:title.slice(0,255)})
  });
}
