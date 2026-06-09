// ── Resume Diff ───────────────────────────────────────────────────────────────
// The resume currently being compared against a master (master-mode only), so
// the picker's onchange can re-render without re-resolving the message.
let _diffMasterTargetResume=null;

function _hideDiffMasterRow(){
  const row=document.getElementById('diff-master-row');
  if(row)row.style.display='none';
}

function openDiff(msgId,sessionId){
  const versions=_resumeVersions[sessionId]||[];
  const myIdx=versions.findIndex(v=>v.id===msgId);
  if(myIdx<1)return;
  const prev=versions[myIdx-1].resume;
  const curr=versions[myIdx].resume;
  _diffMasterTargetResume=null;
  _hideDiffMasterRow();
  document.getElementById('diff-ver').textContent=`(v${myIdx} → v${myIdx+1})`;
  document.getElementById('diff-body').innerHTML=_buildDiffHtml(prev,curr);
  document.getElementById('diff-modal').classList.add('open');
}

// Compare any resume version against a saved master resume (the reference).
// Direction is master → this version, so tailoring/edits read as additions.
function openDiffVsMaster(msgId){
  const curr=window['__r_'+msgId];
  if(!curr){showToast('Resume not loaded yet');return;}
  if(typeof _masterResumes==='undefined'||!_masterResumes.length){
    showToast('No master resume saved to compare against');return;
  }
  _diffMasterTargetResume=curr;
  const sel=document.getElementById('diff-master-pick');
  if(sel){
    sel.innerHTML=_masterResumes.map(it=>
      `<option value="${it.id}"${it.is_default?' selected':''}>${esc(it.name||'Untitled')}${it.is_default?' · default':''}</option>`
    ).join('');
  }
  const row=document.getElementById('diff-master-row');
  if(row)row.style.display='flex';
  _renderMasterDiff();
  document.getElementById('diff-modal').classList.add('open');
}

function _renderMasterDiff(){
  if(!_diffMasterTargetResume)return;
  const sel=document.getElementById('diff-master-pick');
  const mid=sel?sel.value:null;
  const m=(_masterResumes.find(x=>x.id===mid))||_defaultMaster();
  const body=document.getElementById('diff-body');
  if(!m){body.innerHTML='<div style="color:var(--text3);font-size:13px;text-align:center;padding:32px 0">No master resume to compare against.</div>';return;}
  document.getElementById('diff-ver').textContent=`(Master “${m.name}” → this version)`;
  body.innerHTML=_buildDiffHtml(m.resume,_diffMasterTargetResume);
}

function closeDiff(){document.getElementById('diff-modal').classList.remove('open');}
document.getElementById('diff-modal').addEventListener('click',e=>{if(e.target===e.currentTarget)closeDiff();});

// Line-aware diff. Aligns unchanged lines first (each bullet/point is a line),
// then runs the word-level diff only inside the line pairs that actually
// changed. This keeps a small wording tweak in one bullet from lighting up
// every bullet, and keeps each word-level diff small enough to stay precise.
function _diffText(a,b){
  a=a==null?'':String(a);b=b==null?'':String(b);
  if(a===b)return esc(a);
  const al=a.split('\n'),bl=b.split('\n');
  if(al.length<2&&bl.length<2)return _diffWords(a,b);
  const m=al.length,n=bl.length;
  const dp=Array.from({length:m+1},()=>new Array(n+1).fill(0));
  for(let i=1;i<=m;i++)for(let j=1;j<=n;j++)
    dp[i][j]=al[i-1]===bl[j-1]?dp[i-1][j-1]+1:Math.max(dp[i-1][j],dp[i][j-1]);
  const ops=[];let i=m,j=n;
  while(i>0||j>0){
    if(i>0&&j>0&&al[i-1]===bl[j-1]){ops.unshift({t:'=',v:al[i-1]});i--;j--;}
    else if(j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])){ops.unshift({t:'+',v:bl[j-1]});j--;}
    else{ops.unshift({t:'-',v:al[i-1]});i--;}
  }
  const out=[];
  for(let k=0;k<ops.length;){
    if(ops[k].t==='='){out.push(esc(ops[k].v));k++;continue;}
    // Gather a contiguous run of changed lines, then pair removed lines with
    // added lines so a reworded bullet gets word-level highlighting instead of
    // a full delete + full add.
    const dels=[],adds=[];
    while(k<ops.length&&ops[k].t!=='='){
      (ops[k].t==='-'?dels:adds).push(ops[k].v);k++;
    }
    const pairs=Math.min(dels.length,adds.length);
    for(let p=0;p<pairs;p++)out.push(_diffWords(dels[p],adds[p]));
    for(let p=pairs;p<dels.length;p++)out.push(`<span class="df-del">${esc(dels[p])}</span>`);
    for(let p=pairs;p<adds.length;p++)out.push(`<span class="df-add">${esc(adds[p])}</span>`);
  }
  return out.join('\n');
}

function _diffWords(a,b){
  if(!a&&!b)return'';
  if(!a)return`<span class="df-add">${esc(b)}</span>`;
  if(!b)return`<span class="df-del">${esc(a)}</span>`;
  if(a===b)return esc(a);
  const aw=a.split(/(\s+)/),bw=b.split(/(\s+)/);
  const m=aw.length,n=bw.length;
  if(m*n>1000000)return`<span class="df-del">${esc(a)}</span>\n<span class="df-add">${esc(b)}</span>`;
  const dp=Array.from({length:m+1},()=>new Array(n+1).fill(0));
  for(let i=1;i<=m;i++)for(let j=1;j<=n;j++)
    dp[i][j]=aw[i-1]===bw[j-1]?dp[i-1][j-1]+1:Math.max(dp[i-1][j],dp[i][j-1]);
  const parts=[];let i=m,j=n;
  while(i>0||j>0){
    if(i>0&&j>0&&aw[i-1]===bw[j-1]){parts.unshift({t:'=',v:aw[i-1]});i--;j--;}
    else if(j>0&&(i===0||dp[i][j-1]>=dp[i-1][j])){parts.unshift({t:'+',v:bw[j-1]});j--;}
    else{parts.unshift({t:'-',v:aw[i-1]});i--;}
  }
  return parts.map(p=>p.t==='='?esc(p.v):p.t==='+'?`<span class="df-add">${esc(p.v)}</span>`:`<span class="df-del">${esc(p.v)}</span>`).join('');
}

// ── Section serializers ───────────────────────────────────────────────────────
// Turn each resume section into diff-friendly plain text: one logical entry per
// block, with a blank line between blocks so the line-diff aligns whole entries.
// A section/entry present only in the new version reads as all-added (green);
// one dropped from the new version reads as all-removed (red). Field ordering
// mirrors the preview so the diff reads naturally. ss()/toArr() come from
// preview.js and coerce the LLM's loose field shapes.
const _j=(arr,sep)=>arr.filter(x=>x!=null&&x!=='').join(sep);

function _seEdu(list){return toArr(list).map(e=>{
  const deg=ss(e.degree)+(ss(e.field_of_study)?` in ${ss(e.field_of_study)}`:'');
  const L=[_j([deg,ss(e.institution),ss(e.location),_j([ss(e.start_date),ss(e.end_date)],' – ')],'  ·  ')];
  if(ss(e.gpa))L.push('GPA: '+ss(e.gpa));
  if(ss(e.honors))L.push(ss(e.honors));
  const cw=toArr(e.relevant_coursework).map(ss).filter(Boolean);if(cw.length)L.push('Coursework: '+cw.join(', '));
  const ac=toArr(e.activities).map(ss).filter(Boolean);if(ac.length)L.push('Activities: '+ac.join(', '));
  return L.join('\n');
}).join('\n\n');}

function _seProjects(list){return toArr(list).map(p=>{
  const L=[_j([ss(p.name),ss(p.role),ss(p.type),_j([ss(p.start_date),ss(p.end_date)],' – ')],'  ·  ')];
  if(ss(p.description))L.push(ss(p.description));
  const tech=toArr(p.technologies).map(ss).filter(Boolean);if(tech.length)L.push('Tech: '+tech.join(', '));
  toArr(p.highlights).map(ss).filter(Boolean).forEach(h=>L.push('• '+h));
  const url=ss(p.url)||ss(p.github);if(url)L.push(url);
  return L.join('\n');
}).join('\n\n');}

function _seOSS(list){return toArr(list).map(o=>{
  const L=[_j([ss(o.project),ss(o.role),ss(o.language),ss(o.stars)?'★ '+ss(o.stars):''],'  ·  ')];
  if(ss(o.description))L.push(ss(o.description));
  toArr(o.contributions).map(ss).filter(Boolean).forEach(c=>L.push('• '+c));
  if(ss(o.url))L.push(ss(o.url));
  return L.join('\n');
}).join('\n\n');}

function _seCerts(list){return toArr(list).map(c=>{
  const d=[];if(ss(c.date))d.push('issued '+ss(c.date));if(ss(c.expiry))d.push('expires '+ss(c.expiry));
  return _j([ss(c.name),ss(c.issuer),d.join(', '),ss(c.credential_id)?'ID '+ss(c.credential_id):'',ss(c.url)],'  ·  ');
}).join('\n');}

function _sePubs(list){return toArr(list).map(p=>
  _j([ss(p.title),ss(p.type),ss(p.venue),ss(p.date),toArr(p.authors).map(ss).filter(Boolean).join(', '),ss(p.url)],'  ·  ')
).join('\n');}

function _sePatents(list){return toArr(list).map(p=>{
  const L=[_j([ss(p.title),ss(p.patent_number),ss(p.date)],'  ·  ')];
  if(ss(p.description))L.push(ss(p.description));
  return L.join('\n');
}).join('\n\n');}

function _seVol(list){return toArr(list).map(v=>{
  const L=[_j([ss(v.role),ss(v.organization),_j([ss(v.start_date),ss(v.end_date)],' – ')],'  ·  ')];
  if(ss(v.description))L.push(ss(v.description));
  return L.join('\n');
}).join('\n\n');}

function _seLangs(list){return toArr(list).map(l=>
  typeof l==='string'?l:_j([ss(l.language),ss(l.proficiency)?`(${ss(l.proficiency)})`:''],' ')
).join('\n');}

function _seContact(r){const pi=r.personal_info||{};
  return _j([ss(pi.full_name),ss(pi.professional_title),ss(pi.email),ss(pi.phone),ss(pi.location),ss(pi.linkedin),ss(pi.github),ss(pi.website)||ss(pi.portfolio)],'\n');
}

function _buildDiffHtml(a,b){
  a=a||{};b=b||{};
  const secs=[];
  const check=(title,va,vb)=>{if((va||'')!==(vb||''))secs.push({title,html:_diffText(va||'',vb||'')});};

  check('Contact',_seContact(a),_seContact(b));
  check('Professional Summary',a.professional_summary,b.professional_summary);

  const ccA=toArr(a.core_competencies).map(ss).filter(Boolean).join(', ');
  const ccB=toArr(b.core_competencies).map(ss).filter(Boolean).join(', ');
  check('Core Competencies',ccA,ccB);

  // Experience — per job, so a small wording tweak in one bullet doesn't light up
  // the whole section. Walking the longer of the two lists also surfaces jobs
  // added to (or removed from) the new version, not just edited ones.
  const expA=a.experience||[],expB=b.experience||[];
  for(let i=0;i<Math.max(expA.length,expB.length);i++){
    const pj=expA[i],nj=expB[i],job=nj||pj;
    const txtA=pj?[...toArr(pj.responsibilities),...toArr(pj.achievements)].map(ss).join('\n'):'';
    const txtB=nj?[...toArr(nj.responsibilities),...toArr(nj.achievements)].map(ss).join('\n'):'';
    if(txtA!==txtB)secs.push({title:`Experience — ${ss(job.title)} @ ${ss(job.company)}`,html:_diffText(txtA,txtB)});
  }

  const skA=Object.values(a.technical_skills||{}).flat().map(ss).join(', ');
  const skB=Object.values(b.technical_skills||{}).flat().map(ss).join(', ');
  check('Technical Skills',skA,skB);

  // Remaining sections — these were previously never compared, so newly added
  // entries/sections (a fresh Projects list, a new certification, etc.) silently
  // failed to appear in the diff.
  check('Projects',_seProjects(a.projects),_seProjects(b.projects));
  check('Open Source',_seOSS(a.open_source_contributions),_seOSS(b.open_source_contributions));
  check('Education',_seEdu(a.education),_seEdu(b.education));
  check('Certifications',_seCerts(a.certifications),_seCerts(b.certifications));
  check('Publications',_sePubs(a.publications),_sePubs(b.publications));
  check('Patents',_sePatents(a.patents),_sePatents(b.patents));
  check('Awards & Honors',toArr(a.awards_and_honors).map(ss).filter(Boolean).join('\n'),toArr(b.awards_and_honors).map(ss).filter(Boolean).join('\n'));
  check('Volunteer Experience',_seVol(a.volunteer_experience),_seVol(b.volunteer_experience));
  check('Languages',_seLangs(a.languages),_seLangs(b.languages));
  check('Interests',toArr(a.interests).map(ss).filter(Boolean).join(', '),toArr(b.interests).map(ss).filter(Boolean).join(', '));

  const metaA=a.metadata||{},metaB=b.metadata||{};
  const scoreKeys=['overall_score','ats_score','quality_score','impact_score'];
  if(scoreKeys.some(k=>metaA[k]!==metaB[k])){
    const scoreHtml=`<div style="display:flex;gap:20px;flex-wrap:wrap">`+
      scoreKeys.map(k=>{
        const va=Math.round(metaA[k]||0),vb=Math.round(metaB[k]||0),d=vb-va;
        const cl=d>0?'df-add':d<0?'df-del':'';
        return`<div style="text-align:center"><div style="font-size:10px;color:var(--text3);margin-bottom:2px">${k.replace('_score','').replace('_',' ').toUpperCase()}</div>`+
          `<div style="font-size:18px;font-weight:700;color:var(--text1)">${vb} <span class="${cl}" style="font-size:11px;font-weight:600">${d>=0?'+':''}${d}</span></div></div>`;
      }).join('')+`</div>`;
    secs.push({title:'Score Changes',html:scoreHtml});
  }

  if(!secs.length)return'<div style="color:var(--text3);font-size:13px;text-align:center;padding:32px 0">No visible changes between these versions.</div>';
  return secs.map(s=>`<div class="diff-section"><div class="diff-section-title">${esc(s.title)}</div><div class="diff-content">${s.html}</div></div>`).join('');
}
