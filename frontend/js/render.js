// ── Render ──────────────────────────────────────────────────────────────────
const __stagePrompts={};let __spc=0;
function appendUBub(content,jdText,attachLabel,ts){
  const msgs=document.getElementById('messages');
  const row=document.createElement('div');
  row.className='mrow';
  row.style.cssText='display:flex;justify-content:flex-end;flex-direction:column;align-items:flex-end';
  row.innerHTML=`<div class="ubub">${esc(content)}</div>`+
    (jdText?`<div class="jd-badge">🎯 With job description attached</div>`:'')+
    (attachLabel?`<div class="jd-badge" style="background:var(--gbg);border-color:rgba(34,211,160,.3);color:var(--green)">📎 ${esc(attachLabel)}</div>`:'');
  row.appendChild(_msgMeta(ts||Date.now(),content,true));
  msgs.appendChild(row);scrollBot();
}
function createARow(msgId){
  const msgs=document.getElementById('messages');
  const row=document.createElement('div');
  row.className='mrow asst';
  if(msgId)row.dataset.msgId=msgId;
  msgs.appendChild(row);scrollBot();return row;
}

function _progHash(events){
  // Hash-key that ignores microsecond changes so we don't re-render on every poll
  return (events||[]).map(e=>{
    const lev=e.llm_event||{};
    return `${e.agent}|${e.status}|${(e.notes||'').slice(0,80)}|${lev.model||''}|${lev.duration_ms||0}|${lev.input_tokens||0}|${lev.output_tokens||0}`;
  }).join('§');
}
function renderProg(c,events){
  // Skip re-paint if the trace is unchanged — keeps the running-step spinner smooth
  const h=_progHash(events);
  if(c.dataset.progHash===h)return;
  c.dataset.progHash=h;

  const agMap={};
  (events||[]).forEach(e=>{agMap[e.agent]=e;});
  let html=`<div class="prog-panel">
    <div class="prog-hdr"><div class="phdr-dot"></div>Building your resume…</div>
    <div class="step-list">`;
  STEPS.forEach(step=>{
    const ev=agMap[step.agent];
    let cls='pend',iconHtml=ico('ic-circle-empty')||'<span class="step-dot"></span>',notes=step.desc,llmHtml='';
    if(ev){
      if(ev.status==='running'){cls='run';iconHtml=`<span class="spin-ring"></span>`;notes=ev.notes||step.desc;}
      else if(ev.status==='complete'){cls='done';iconHtml=ico('ic-check');notes=ev.notes||step.desc;}
      else if(ev.status==='error'){cls='err';iconHtml=ico('ic-x');notes=ev.notes||'Error';}
      if(ev.llm_event&&ev.llm_event.duration_ms){
        const lev=ev.llm_event;
        const toks=lev.input_tokens?`${lev.input_tokens}→${lev.output_tokens} tkns · `:'';
        const evBadge=`<div class="llm-ev">${ico('ic-cpu')}<span>${esc(lev.model||'')}</span> · ${toks}<span>${lev.duration_ms}ms</span></div>`;
        let cpBtn='';
        if(lev.system_prompt||lev.user_prompt){const pk=++__spc;__stagePrompts[pk]={system:lev.system_prompt||'',user:lev.user_prompt||''};cpBtn=`<button class="prompt-copy-btn" onclick="copyStagePrompt(event,${pk})" type="button">Copy prompt</button>`;}
        llmHtml=`<div class="llm-ev-row">${evBadge}${cpBtn}</div>`;
      }
    }else{
      iconHtml='<span class="step-dot"></span>';
    }
    html+=`<div class="srow">
      <div class="sic ${cls}">${iconHtml}</div>
      <div class="sbody">
        <div class="sname${!ev?' pend':''}">${ico(step.icon)} ${esc(step.agent)}</div>
        <div class="snotes">${esc(notes)}</div>
        ${llmHtml}
      </div>
    </div>`;
  });
  (events||[]).forEach(e=>{
    if(!STEPS.find(s=>s.agent===e.agent)){
      const cls=e.status==='complete'?'done':e.status==='error'?'err':'run';
      const ic=cls==='done'?ico('ic-check'):cls==='err'?ico('ic-x'):'<span class="spin-ring"></span>';
      html+=`<div class="srow"><div class="sic ${cls}">${ic}</div>
        <div class="sbody"><div class="sname">${ico('ic-settings')} ${esc(e.agent)}</div>
          <div class="snotes">${esc(e.notes||'')}</div></div></div>`;
    }
  });
  html+='</div></div>';
  c.innerHTML=html;
}

function renderCancelled(c,msg){
  c.innerHTML=`<div class="prog-panel" style="border-color:rgba(248,113,113,.25)">
    <div class="prog-hdr" style="color:var(--red)">⏹ Generation stopped</div>
    <div style="font-size:12.5px;color:var(--text2);line-height:1.5">${esc(msg.content||'You stopped the generation.')}</div>
  </div>`;
  c.appendChild(_msgMeta(msg.created_at,msg.content||'',false));
}
function renderError(c,msg){
  const content=msg.content||'Error';
  // Backend may append a traceback / agent timeline after a @@TRACEBACK@@
  // sentinel — split it out so the prose renders as markdown and the trace
  // goes into a collapsible <pre> block with a copy button.
  const [mainRaw,...rest]=content.split('@@TRACEBACK@@');
  const trace=rest.join('@@TRACEBACK@@').trim();
  const mainHtml=`<div class="at err-detail" style="color:var(--red);line-height:1.55">${renderMd(mainRaw.trim())}</div>`;
  let traceHtml='';
  if(trace){
    const id='trc-'+msg.id;
    traceHtml=`<details class="err-trace" style="margin-top:8px;border:1px solid var(--bdr);border-radius:6px;background:var(--bg2)">
      <summary style="cursor:pointer;padding:8px 12px;font-size:12px;color:var(--text2);font-weight:500;display:flex;align-items:center;gap:8px;user-select:none">
        <span style="flex:1">📋 Technical details · agent timeline / traceback</span>
        <button class="bsec" style="padding:3px 8px;font-size:11px" onclick="copyErrTrace(event,'${id}')" type="button">Copy</button>
      </summary>
      <pre id="${id}" style="margin:0;padding:10px 12px;border-top:1px solid var(--bdr);font-family:var(--mono);font-size:11.5px;line-height:1.5;color:var(--text2);white-space:pre-wrap;word-break:break-word;max-height:320px;overflow-y:auto">${esc(trace)}</pre>
    </details>`;
  }
  c.innerHTML=mainHtml+traceHtml;
  c.appendChild(_msgMeta(msg.created_at,content,false));
}
function copyErrTrace(ev,id){
  ev.preventDefault();ev.stopPropagation();
  const el=document.getElementById(id);if(!el)return;
  _copyText(el.textContent||'',ev.currentTarget,'Copied');
}
function _copyText(text,btn,label){
  const done=()=>{if(btn){const o=btn.textContent;btn.textContent=label||'Copied!';setTimeout(()=>btn.textContent=o,1500);}};
  const fallback=()=>{
    const ta=document.createElement('textarea');
    ta.value=text;ta.style.cssText='position:fixed;top:-9999px;left:-9999px;opacity:0';
    document.body.appendChild(ta);ta.focus();ta.select();
    try{document.execCommand('copy');done();}catch(e){showToast('Copy failed');}
    document.body.removeChild(ta);
  };
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done).catch(fallback);
  }else{fallback();}
}
function copyStagePrompt(ev,pk){
  ev.preventDefault();ev.stopPropagation();
  const p=__stagePrompts[pk];if(!p)return;
  const sep='─'.repeat(72);
  _copyText(`SYSTEM PROMPT:\n${sep}\n${p.system}\n\n\nUSER PROMPT:\n${sep}\n${p.user}`,ev.currentTarget,'Copied!');
}

function renderDone(c,msg){
  const trace=msg.agent_trace||msg.progress_events||[];
  const resume=msg.resume_json;
  const meta=resume?.metadata||{};

  if(!resume){
    c.innerHTML=`<div class="at">${renderMd(msg.content||'')}</div>`;
    c.appendChild(_msgMeta(msg.created_at,msg.content||'',false));
    return;
  }
  const agMap={};trace.forEach(e=>{agMap[e.agent]=e;});
  let _nSteps=0;
  let stepsHtml=`<div class="prog-panel" style="margin-bottom:14px">
    <div class="prog-hdr" style="color:var(--green)">${ico('ic-check')} Pipeline complete</div>
    <div class="step-list">`;
  STEPS.forEach(step=>{
    const ev=agMap[step.agent];if(!ev)return;
    _nSteps++;
    const cls=ev.status==='complete'?'done':ev.status==='error'?'err':'pend';
    const ic=cls==='done'?ico('ic-check'):ico('ic-x');
    let llmHtml='';
    if(ev.llm_event&&ev.llm_event.duration_ms){
      const lev=ev.llm_event;
      const toks=lev.input_tokens?`${lev.input_tokens}→${lev.output_tokens} tkns · `:'';
      const evBadge=`<div class="llm-ev">${ico('ic-cpu')}<span>${esc(lev.model||'')}</span> · ${toks}<span>${lev.duration_ms}ms</span></div>`;
      let cpBtn='';
      if(lev.system_prompt||lev.user_prompt){const pk=++__spc;__stagePrompts[pk]={system:lev.system_prompt||'',user:lev.user_prompt||''};cpBtn=`<button class="prompt-copy-btn" onclick="copyStagePrompt(event,${pk})" type="button">Copy prompt</button>`;}
      llmHtml=`<div class="llm-ev-row">${evBadge}${cpBtn}</div>`;
    }
    stepsHtml+=`<div class="srow"><div class="sic ${cls}">${ic}</div>
      <div class="sbody"><div class="sname">${ico(step.icon)} ${esc(step.agent)}</div>
        <div class="snotes">${esc(ev.notes||step.desc)}</div>${llmHtml}</div></div>`;
  });
  stepsHtml+='</div></div>';
  // A verbatim "from master" seed has no pipeline agents to show — skip the
  // (otherwise empty) "Pipeline complete" panel for it.
  if(_nSteps===0)stepsHtml='';

  let scHtml='';
  if(meta.overall_score!==undefined){
    scHtml=`<div class="score-row">
      ${sc('Overall',meta.overall_score)}${sc('ATS',meta.ats_score)}
      ${sc('Quality',meta.quality_score)}${sc('Impact',meta.impact_score)}
      ${sc('Complete',meta.completeness_score)}
      ${meta.jd_match_score?`<div class="sb2 jdm">${ico('ic-target')} JD Match <strong>${Math.round(meta.jd_match_score)}</strong></div>`:''}
    </div>`;
  }
  const textHtml=`<div class="at">${renderMd(msg.content||'')}</div>`;
  const viewerHtml=buildViewer(resume,msg.id,msg.cover_letter,msg.outreach_emails);
  c.innerHTML=stepsHtml+scHtml+textHtml+`<div class="jv">${viewerHtml}</div>`;
  c.appendChild(_msgMeta(msg.created_at,msg.content||'',false));
  if(resume){
    window[`__r_${msg.id}`]=resume;
    const sid=msg.session_id;
    if(sid){
      if(!_resumeVersions[sid])_resumeVersions[sid]=[];
      if(!_resumeVersions[sid].find(v=>v.id===msg.id))
        _resumeVersions[sid].push({id:msg.id,resume});
      const versions=_resumeVersions[sid];
      const myIdx=versions.findIndex(v=>v.id===msg.id);
      const jvr=c.querySelector('.jv-r');
      if(jvr){
        // Compare this resume version against a saved master reference.
        if(typeof _masterResumes!=='undefined' && _masterResumes.length){
          const mbtn=document.createElement('button');
          mbtn.className='ibtn cmp';
          mbtn.innerHTML=ico('ic-compare')+` Compare to Master`;
          mbtn.title='Compare this resume against your master resume — see what changed';
          mbtn.onclick=()=>openDiffVsMaster(msg.id);
          jvr.prepend(mbtn);
        }
        // Version-to-version diff (only once a previous version exists).
        if(myIdx>0){
          const btn=document.createElement('button');
          btn.className='ibtn cmp';
          btn.innerHTML=ico('ic-refresh')+` v${myIdx}→v${myIdx+1}`;
          btn.onclick=()=>openDiff(msg.id,sid);
          jvr.prepend(btn);
        }
      }
    }
  }
}

function sc(label,val){
  if(val===undefined||val===null)return'';
  const n=Math.round(Number(val));
  const cls=n>=90?'exc':n>=75?'gd':n>=60?'fair':'poor';
  return`<div class="sb2 ${cls}"><span>${label}</span><strong>${n}</strong></div>`;
}
