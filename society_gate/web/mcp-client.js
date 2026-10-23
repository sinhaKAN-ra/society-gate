/* A real, local Streamable HTTP MCP client. No Alexa+ device connection is implied. */
(() => {
  const $ = id => document.getElementById(id);
  let accessToken = '', protocol = '', nextId = 1, pending = null, lastVisit = '', busy = false;
  let packets = [];
  function trace(direction, packet) {
    packets.push(`${direction} ${JSON.stringify(packet, null, 2)}`);
    packets = packets.slice(-14);
    $('mcp-trace').textContent = packets.join('\n\n');
  }
  function endpoint() {
    const url = new URL($('mcp-url').value);
    if(url.protocol !== 'http:' || !['127.0.0.1','localhost'].includes(url.hostname) || url.pathname !== '/mcp' || url.search || url.hash || url.username || url.password) throw new Error('Use a loopback HTTP endpoint ending in /mcp.');
    return url.href;
  }
  async function rpc(method, params, notification=false) {
    const packet={jsonrpc:'2.0',method,...(notification?{}:{id:nextId++}),...(params?{params}:{})};
    trace('→',packet);
    const headers={Authorization:`Bearer ${accessToken}`,'Content-Type':'application/json',Accept:'application/json, text/event-stream'};
    if(protocol) headers['MCP-Protocol-Version']=protocol;
    const response=await fetch(endpoint(),{method:'POST',headers,body:JSON.stringify(packet)});
    if(!response.ok) throw new Error(`MCP HTTP ${response.status}: ${await response.text()}`);
    if(notification && response.status===202) {trace('←',{httpStatus:202});return;}
    const result=await response.json();trace('←',result);
    if(result.error) throw new Error(result.error.message||'MCP request failed.');
    return result.result;
  }
  async function call(name,args={}) {
    const result=await rpc('tools/call',{name,arguments:args});
    if(result.isError) throw new Error(result.content?.map(c=>c.text||'').join('\n')||'Tool failed.');
    if(result.structuredContent) return result.structuredContent;
    const content=result.content?.find(c=>c.type==='text');
    return content?JSON.parse(content.text):{};
  }
  function available() {
    const connected=Boolean(protocol),selected=Boolean($('mcp-visitor').value);
    $('mcp-connect').disabled=busy;
    for(const id of ['mcp-visitors','mcp-rules']) $(id).disabled=!connected||busy;
    $('mcp-visitor').disabled=!connected||busy;
    for(const id of ['mcp-approve','mcp-deny']) $(id).disabled=!connected||!selected||busy;
    $('mcp-receipt').disabled=!connected||!lastVisit||busy;
    for(const id of ['mcp-confirm','mcp-cancel']) $(id).disabled=!pending||busy;
  }
  async function action(fn) {
    if(busy) return;busy=true;available();
    try{await fn();}catch(e){$('mcp-answer').textContent=e.message;}finally{busy=false;available();}
  }
  window.addEventListener('society-account',event=>{
    accessToken=event.detail.token||'';protocol='';pending=null;lastVisit='';packets=[];
    $('mcp-status').textContent='MCP disconnected';$('mcp-section').hidden=event.detail.role!=='resident';
    $('mcp-answer').textContent='Start the MCP server, then connect to discover its tools.';
    $('mcp-trace').textContent='No protocol messages yet.';$('mcp-visitor').replaceChildren(new Option('Check visitors first',''));available();
  });
  $('mcp-connect').addEventListener('click',()=>action(async()=>{
    protocol='';pending=null;
    const result=await rpc('initialize',{protocolVersion:'2025-11-25',capabilities:{},clientInfo:{name:'society-gate-web',version:'0.1.0'}});
    if(!result.protocolVersion || result.protocolVersion<'2025-11-25') throw new Error('Server negotiated an older protocol. Update the MCP SDK.');
    protocol=result.protocolVersion;await rpc('notifications/initialized',undefined,true);
    const tools=await rpc('tools/list',{});
    $('mcp-status').textContent=`MCP ${protocol} · Streamable HTTP`;
    $('mcp-answer').textContent=`Connected to ${result.serverInfo.name}. Discovered ${tools.tools.length} tools: ${tools.tools.map(t=>t.name).join(', ')}.\nAsk who is at the gate to start.`;
  }));
  $('mcp-visitors').addEventListener('click',()=>action(async()=>{
    const result=await call('list_waiting_visitors');pending=null;
    $('mcp-visitor').replaceChildren(...result.visitors.map(v=>new Option(`${v.visitor} · ${v.purpose} · ${v.unit}`,v.id)));
    if(!result.visitors.length) $('mcp-visitor').append(new Option('Nobody is waiting',''));
    $('mcp-answer').textContent=result.visitors.length?`${result.visitors.length} request(s) for ${result.unit}. Choose the exact visitor and prepare a decision.`:'Nobody is waiting for your flat.';
  }));
  $('mcp-visitor').addEventListener('change',()=>{pending=null;available();});
  for(const [id,decision] of [['mcp-approve','approved'],['mcp-deny','denied']]) $(id).addEventListener('click',()=>action(async()=>{
    lastVisit=$('mcp-visitor').value;
    pending=await call('prepare_visitor_decision',{visit_id:lastVisit,decision});
    $('mcp-answer').textContent=`${pending.confirmation_prompt}\nNothing has been approved or denied yet. This confirmation expires in at most 60 seconds.`;
  }));
  for(const [id,confirmed] of [['mcp-confirm',true],['mcp-cancel',false]]) $(id).addEventListener('click',()=>action(async()=>{
    const result=await call('confirm_visitor_decision',{confirmation_id:pending.confirmation_id,confirmed});pending=null;
    $('mcp-answer').textContent=result.status==='cancelled'?'Choice cancelled. The visitor is still waiting.':`${result.visitor}: ${result.status}. The companion guard dashboard is updated. Existing vendor app: not connected.`;
  }));
  $('mcp-receipt').addEventListener('click',()=>action(async()=>{
    const result=await call('get_visitor_receipt',{visit_id:lastVisit});
    $('mcp-answer').textContent=`${result.visit.visitor} · ${result.visit.unit} · ${result.visit.status}\n${result.audit.slice().reverse().map(e=>`${new Date(e.at*1000).toLocaleTimeString()}: ${e.event.replaceAll('_',' ')} by ${e.actor}`).join('\n')}\nGuard delivery: companion dashboard. Vendor delivery: not connected.`;
  }));
  $('mcp-rules').addEventListener('click',()=>action(async()=>{
    const result=await call('list_trusted_visitor_rules');
    $('mcp-answer').textContent=result.rules.length?result.rules.map(r=>`${r.label} · ${r.visitor_ref} · ${r.active && r.ends>result.now?'active until '+new Date(r.ends*1000).toLocaleString():'inactive'}`).join('\n'):'No trusted visitor rules for your flat. Add one in the resident panel below.';
  }));
})();
