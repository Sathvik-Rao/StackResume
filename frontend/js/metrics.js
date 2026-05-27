// ── Metrics ──────────────────────────────────────────────────────────────────
// openMetrics() / closeMetrics() now live in section-prefs.js — they route
// into the consolidated #settings-modal and switch to the Usage Metrics tab.
async function loadMetrics(){
  const body=document.getElementById('metrics-body');
  body.innerHTML='<div class="pv-empty">Loading…</div>';
  try{
    const r=await fetch(`${API}/api/metrics`);
    if(!r.ok)throw new Error('Failed to load metrics');
    const m=await r.json();
    body.innerHTML=renderMetrics(m);
    document.getElementById('met-refresh-meta').textContent=`updated ${new Date().toLocaleTimeString()}`;
  }catch(e){
    body.innerHTML=`<div style="color:var(--red);font-size:13px">${esc(e.message)}</div>`;
  }
}
function renderMetrics(m){
  const t=m.totals||{};
  const card=(label,v)=>`<div class="met-card"><div class="met-label">${esc(label)}</div><div class="met-value">${v??'—'}</div></div>`;
  const num=v=>v==null?'—':Number(v).toLocaleString();
  const fmtMs=ms=>{if(!ms)return'—';const s=ms/1000;if(s<60)return s.toFixed(1)+'s';return(s/60).toFixed(1)+'m';};
  const avgMs=(ms,calls)=>fmtMs(calls?Math.round(ms/calls):0);
  let h='<div class="metrics-grid">';
  h+=card('Resumes generated',num(t.resumes_completed));
  h+=card('Sessions',num(t.sessions));
  h+=card('Avg quality',t.average_score!=null?`${t.average_score}`:'—');
  h+=card('Avg iterations',t.average_iterations||0);
  h+=card('Total tokens',num(t.total_tokens));
  h+=card('In tokens',num(t.total_input_tokens));
  h+=card('Out tokens',num(t.total_output_tokens));
  h+=card('Cover letters',num(t.cover_letters_generated));
  h+=card('Outreach emails',num(t.outreach_emails_generated));
  h+=card('JD-tailored',num(t.jd_tailored_resumes));
  if(t.in_flight)h+=card('In flight',`<span style="color:var(--accent2)">${t.in_flight}</span>`);
  if(t.failed)h+=card('Failed',`<span style="color:var(--red)">${t.failed}</span>`);
  if(t.cancelled)h+=card('Cancelled',`<span style="color:var(--text3)">${t.cancelled}</span>`);
  h+='</div>';

  // 7-day daily strip — bucketed in browser's local timezone
  const tsList=m.recent_resume_timestamps||[];
  const todayStart=new Date();todayStart.setHours(0,0,0,0);
  const daily=Array.from({length:8},(_,i)=>{
    const d=new Date(todayStart);d.setDate(d.getDate()-(7-i));
    const next=new Date(d);next.setDate(next.getDate()+1);
    const count=tsList.filter(ts=>ts>=d.getTime()&&ts<next.getTime()).length;
    const lbl=`${d.getMonth()+1}-${String(d.getDate()).padStart(2,'0')}`;
    return{count,lbl};
  });
  const maxV=Math.max(1,...daily.map(d=>d.count));
  h+='<div class="set-section-title">Last 8 days</div><div class="daily-row">';
  daily.forEach(d=>{
    const h2=Math.max(3,Math.round((d.count/maxV)*60));
    h+=`<div class="daily-col"><div class="daily-bar${d.count?'':' zero'}" style="height:${h2}px" title="${d.count} resume(s)"></div>
      <div class="daily-lbl">${d.lbl}</div>
      <div class="daily-lbl" style="color:${d.count?'var(--accent2)':'var(--text3)'}">${d.count}</div></div>`;
  });
  h+='</div>';

  // by model
  const bm=m.by_model||[];
  if(bm.length){
    h+='<div class="set-section-title">By model</div><table class="met-table"><thead><tr><th>Model</th><th class="r">Calls</th><th class="r">In tkn</th><th class="r">Out tkn</th><th class="r">Avg time</th><th class="r">Total time</th></tr></thead><tbody>';
    bm.forEach(r=>{
      h+=`<tr><td>${esc(r.model)}</td><td class="r">${num(r.calls)}</td><td class="r">${num(r.in_tokens)}</td><td class="r">${num(r.out_tokens)}</td><td class="r">${avgMs(r.ms,r.calls)}</td><td class="r">${fmtMs(r.ms)}</td></tr>`;
    });
    h+='</tbody></table>';
  }

  const ba=m.by_agent||[];
  if(ba.length){
    h+='<div class="set-section-title">By agent</div><table class="met-table"><thead><tr><th>Agent</th><th class="r">Calls</th><th class="r">In tkn</th><th class="r">Out tkn</th><th class="r">Avg time</th><th class="r">Total time</th></tr></thead><tbody>';
    ba.forEach(r=>{
      h+=`<tr><td>${esc(r.agent)}</td><td class="r">${num(r.calls)}</td><td class="r">${num(r.in_tokens)}</td><td class="r">${num(r.out_tokens)}</td><td class="r">${avgMs(r.ms,r.calls)}</td><td class="r">${fmtMs(r.ms)}</td></tr>`;
    });
    h+='</tbody></table>';
  }
  return h;
}
// click-outside-to-close is handled by the consolidated settings modal.
