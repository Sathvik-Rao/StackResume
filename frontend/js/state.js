// ── State ───────────────────────────────────────────────────────────────────
const API='';
let curSession=null;
let pdfResume=null;
let curProv=localStorage.getItem('sr_p')||'google';
let curModel=localStorage.getItem('sr_m')||'gemini-2.5-flash';
let pdfTemplate='classic_ats',pdfFs='normal',pdfMp='auto',pdfFmt='pdf';
// Export modal context: 'resume' | 'coverletter' — drives which endpoint is hit.
let exportKind='resume';
let exportClMsgId=null;

/** Per-message poll state — survives session navigation. */
const messageStates={};   // { msgId: { sessionId, status, msg, container } }
const pollers={};         // { msgId: timeoutId }
const sessionProcessing={}; // { sessionId: msgId }  — at most one in-flight per session
// In-flight user sends — survives session navigation so the user bubble and
// pending row can be restored if the user navigates A→B→A while the POST is
// still committing. Cleared once the server has confirmed the user msg.
const inFlightSends={}; // { sessionId: { content, jdText, attachLabel, finalContent, ts, assistantMessageId? } }

const STEPS=[
  {agent:'Intent Guard',     icon:'ic-shield',    desc:'Checking if this is a resume request…'},
  {agent:'Input Parser',     icon:'ic-search',    desc:'Extracting career data from your message…'},
  {agent:'JD Analyzer',      icon:'ic-list',      desc:'Parsing job description requirements and keywords…'},
  {agent:'Resume Generator', icon:'ic-edit-pencil', desc:'Crafting STAR-format bullets with ATS keywords…'},
  {agent:'Quality Reviewer', icon:'ic-chart',     desc:'Scoring ATS, quality, impact and completeness…'},
  {agent:'Resume Enhancer',  icon:'ic-sparkles',  desc:'Fixing issues, strengthening bullets, injecting keywords…'},
  {agent:'Finalizer',        icon:'ic-check',     desc:'Wrapping up…'},
  {agent:'Cover Letter Writer', icon:'ic-mail',   desc:'Drafting a tailored cover letter from your resume and the JD…'},
  {agent:'Outreach Writer',  icon:'ic-mail',      desc:'Composing cold-application, LinkedIn, referral and follow-up templates…'},
];
function ico(name){return `<svg class="ic"><use href="#${name}"/></svg>`;}
