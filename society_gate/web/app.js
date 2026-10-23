const $ = (id) => document.getElementById(id);
let token = sessionStorage.getItem('society-token') || '';
let state = null;
let session = crypto.randomUUID();
let updating = false;
let announcedActor = '';
const labels = {pending:'Waiting for resident',approved:'Approved',denied:'Denied',expired:'Expired',checked_in:'Inside society',checked_out:'Checked out'};
const node = (tag, content, cls) => { const n = document.createElement(tag); if(content !== undefined) n.textContent = content; if(cls) n.className = cls; return n; };
function notice(message) { $('notice').textContent = message; $('notice').hidden = !message; }
async function api(path, body) {
  const response = await fetch(path, {method: body === undefined ? 'GET' : 'POST', headers:{Authorization:`Bearer ${token}`,...(body === undefined ? {} : {'Content-Type':'application/json'})},...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const data = await response.json();
  if(!response.ok) throw new Error(data.error || 'Request failed.');
  return data;
}
function formatTime(seconds) {return new Date(seconds * 1000).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});}
function button(label, action, secondary=true) {const n = node('button',label,secondary?'secondary':'');n.type='button';n.addEventListener('click',()=>run(action));return n;}
async function run(action) {try {notice('');await action();await refresh();} catch(e) {notice(e.message);}}
async function refresh() {
  if(!token || updating) return;
  updating=true;
  try {state=await api('/api/state');render();} finally {updating=false;}
}
function render() {
  const role=state.actor.role, resident=role==='resident', integration=role==='integration';
  if(announcedActor!==token) {announcedActor=token;window.dispatchEvent(new CustomEvent('society-account',{detail:{role,token}}));}
  $('workspace').hidden=false;$('disconnect').hidden=false;
  $('identity').textContent=`Connected: ${state.actor.name} · ${role}`;
  $('queue-title').textContent=resident?`Visitors for ${state.actor.unit}`:'Visitor requests';
  $('pending-count').textContent=state.visits.filter(v=>v.status==='pending').length;
  $('approved-count').textContent=state.visits.filter(v=>v.status==='approved').length;
  $('inside-count').textContent=state.visits.filter(v=>v.status==='checked_in').length;
  $('arrival-section').hidden=resident;$('provider-fields').hidden=!integration;
  $('arrival-heading').textContent=integration?'Mock a vendor arrival':'Register a visitor';
  $('arrival-description').textContent=integration?'Exercise the integration contract with a test event. No vendor app is connected.':'Send an entry request to the resident.';
  $('voice-section').hidden=!resident;$('rule-form').hidden=!resident;
  const visits=$('visits');visits.replaceChildren();
  if(!state.visits.length) visits.append(node('div',resident?'No visitors for your flat yet. Ask the guard to register an arrival.':'A quiet gate. Register your first visitor to start.', 'empty'));
  for(const v of state.visits) {
    const row=node('div',undefined,'visit');const who=node('div');who.append(node('strong',v.visitor),node('small',`${v.unit} · ${v.purpose}`));
    const status=node('div');status.append(node('span',labels[v.status]||v.status,`badge ${v.status}`));status.append(node('small',v.status==='pending'||v.status==='approved'?`Valid until ${formatTime(v.expires)}`:`Requested ${formatTime(v.created)}`));
    const actions=node('div',undefined,'actions');
    if(resident && v.status==='pending') for(const [label,decision] of [['Approve','approved'],['Deny','denied']]) actions.append(button(label,async()=>{await api('/api/decision',{id:v.id,decision});},decision==='denied'));
    if(role==='guard' && ['approved','checked_in'].includes(v.status)) actions.append(button(v.status==='approved'?'Record entry':'Record exit',()=>api('/api/movement',{id:v.id,action:v.status==='approved'?'check-in':'check-out'}),false));
    row.append(who,status,actions);visits.append(row);
  }
  const rules=$('rules');rules.replaceChildren();
  if(!state.rules.length) rules.append(node('p','No trusted visitor rules. Each arrival needs a resident decision.','empty'));
  for(const rule of state.rules) {
    const active=rule.active && rule.ends>state.now;const row=node('div',undefined,'rule-row'),info=node('div');
    info.append(node('strong',rule.label),node('small',`${rule.unit} · ${rule.visitor_ref} · ${active?'until '+formatTime(rule.ends):'inactive'}`));row.append(info);
    if(resident && active && rule.resident===state.actor.id) row.append(button('Revoke',()=>api('/api/rules/revoke',{id:rule.id})));
    rules.append(row);
  }
  const activity=$('activity');activity.replaceChildren();
  if(!state.audit.length) activity.append(node('p','Decisions and gate movements will appear here.','empty'));
  for(const event of state.audit.slice(0,25)) {const row=node('div',undefined,'activity-row');const v=state.visits.find(v=>v.id===event.visit);row.append(node('span',formatTime(event.at)),node('div',`${event.event.replaceAll('_',' ')} · ${v?.visitor||event.visit} · ${event.actor}`));activity.append(row);}
}
$('login-form').addEventListener('submit',event=>{event.preventDefault();token=$('token').value.trim();session=crypto.randomUUID();run(async()=>{state=await api('/api/state');sessionStorage.setItem('society-token',token);$('token').value='';$('transcript').textContent='Ready. Open the skill to hear who is waiting.';render();});});
$('disconnect').addEventListener('click',()=>{token='';state=null;announcedActor='';window.dispatchEvent(new CustomEvent('society-account',{detail:{}}));sessionStorage.removeItem('society-token');$('workspace').hidden=true;$('disconnect').hidden=true;$('identity').textContent='Not connected';notice('');});
$('refresh').addEventListener('click',()=>run(refresh));
$('arrival-form').addEventListener('submit',event=>{event.preventDefault();run(async()=>{const integration=state.actor.role==='integration';const body={visitor:$('visitor').value,unit:$('unit').value,purpose:$('purpose').value};if(integration) Object.assign(body,{external_id:crypto.randomUUID(),visitor_ref:$('visitor-ref').value,identity_verified:$('verified').checked});const visit=await api(integration?'/api/integrations/visitors':'/api/visitors',body);$('arrival-form').reset();notice(visit.rule_id?'Approved by the resident’s trusted visitor rule.':'Request sent. The visitor must wait for resident approval.');});});
$('rule-form').addEventListener('submit',event=>{event.preventDefault();run(async()=>{await api('/api/rules',{label:$('rule-label').value,visitor_ref:$('rule-ref').value,hours:Number($('rule-hours').value)});$('rule-form').reset();notice('Rule saved for your flat. Only verified vendor arrivals can match it.');});});
for(const control of document.querySelectorAll('[data-intent]')) control.addEventListener('click',()=>run(async()=>{const result=await api('/api/simulate',{session_id:session,intent:control.dataset.intent});$('transcript').textContent=result.response.outputSpeech?.text||'Session ended.';if(result.response.shouldEndSession) session=crypto.randomUUID();}));
setInterval(()=>{if(token) refresh().catch(e=>notice(e.message));},3000);
if(token) refresh().catch(e=>notice(e.message));
