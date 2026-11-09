const $ = (id) => document.getElementById(id);
let board = [], events = [], staffToken = sessionStorage.getItem("game-on-token") || "";
let availabilityFilter = "all";
let connected = false;
let pendingMaintenanceItem = null;

const localTime = (iso) => iso ? new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"}) : "—";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function timeLeft(iso) {
  if (!iso) return "";
  const minutes = Math.ceil((new Date(iso).getTime()-Date.now())/60000);
  if(minutes <= 0) return "Overdue by " + Math.ceil(-minutes/60) + "h " + (-minutes%60) + "m";
  return Math.floor(minutes/60) + "h " + (minutes%60) + "m remaining";
}
function imageTag(i) {
  const name=esc(i.title);
  return '<img loading="lazy" src="'+esc(i.image)+'" alt="'+name+' cover">';
}
function card(item) {
  const out=!!item.checked_out_at, service=!!item.out_of_service, late=out && new Date(item.due_at).getTime() < Date.now();
  const el=document.createElement("article");
  el.className="card"+(late?" late":"");
  const action=out?"Mark checked in":"Check out for 3 hours";
  const label=service?"Out of service":out?"Checked out":"Available";
  el.innerHTML='<div class="cover">'+imageTag(item)+'</div><div class="content"><span class="availability-badge '+(out||service?"unavailable":"available")+'">'+label+'</span><div class="category">'+esc(item.category)+'</div><h3>'+esc(item.title)+'</h3><p>'+esc(item.details)+'</p><p class="description">'+esc(item.description||"")+'</p>'+(item.warning?'<p class="warning">⚠ '+esc(item.warning)+'</p>':"")+
    '<p class="meta">RESERVE (Ask front desk)<br>'+esc(item.call_number)+' · '+esc(item.barcode)+'</p>'+
    (out?'<div class="checkout"><strong>'+(late?'Overdue':'Checked out')+'</strong><br>Out: '+localTime(item.checked_out_at)+'<br>Due: '+localTime(item.due_at)+'<br><span class="remaining">'+timeLeft(item.due_at)+'</span></div>' :service?'<p class="warning">Temporarily unavailable. Ask library staff.</p>':'<p class="ready">Available at the desk</p>')+
    (staffToken?'<div class="staff-card-actions">'+(!service||out?'<button class="toggle" data-id="'+esc(item.id)+'">'+action+'</button>':'')+'<button type="button" class="maintenance-open" data-id="'+esc(item.id)+'">Condition / service</button></div>'+(item.condition_note?'<p class="private-note"><strong>Staff note:</strong> '+esc(item.condition_note)+'</p>':''):'')+'</div>';
  return el;
}
function render() {
  const query=$("search").value.trim().toLowerCase();
  const matches=board.filter(x=>[x.title,x.category,x.details,x.barcode,x.call_number].join(" ").toLowerCase().includes(query));
  $("available-section").hidden=availabilityFilter==="out";
  $("out-section").hidden=availabilityFilter==="available" || availabilityFilter==="service";
  $("service-section").hidden=availabilityFilter==="available" || availabilityFilter==="out";
  $("available-section").hidden=availabilityFilter==="out" || availabilityFilter==="service";
  $("activity-section").hidden=!staffToken;
  const avail=$("available"), out=$("out"), service=$("service"); avail.replaceChildren(); out.replaceChildren();service.replaceChildren();
  for(const item of matches) (item.out_of_service?service:item.checked_out_at?out:avail).appendChild(card(item));
  if(!avail.children.length) avail.innerHTML='<p class="empty">No available items match your search.</p>';
  if(!service.children.length) service.innerHTML='<p class="empty">No out-of-service items match your search.</p>';
  if(!out.children.length) out.innerHTML='<p class="empty">No checked-out items match your search.</p>';
  const checked=board.filter(i=>i.checked_out_at && !i.out_of_service);
  const held=board.filter(i=>i.out_of_service);
  $("available-count").textContent=(board.length-board.filter(i=>i.checked_out_at||i.out_of_service).length)+" ready to borrow";
  $("out-count").textContent=checked.length+" checked out";
  $("service-count").textContent=held.length+" out of service";
  $("overdue-count").textContent=checked.filter(i=>new Date(i.due_at)<new Date()).length+" overdue";
  const byId=Object.fromEntries(board.map(i=>[i.id,i.title]));
  $("events").replaceChildren(...events.map(e=>{
    const li=document.createElement("li");
    li.textContent=(byId[e.item_id]||e.item_id)+" — "+(e.action==="checked_out"?"Checked out":"Checked in")+" · "+localTime(e.at);
    return li;
  }));
  $("login-button").hidden=!!staffToken; $("logout-button").hidden=!staffToken;
  $("stats-link").hidden=!staffToken;
  $("staff-tools").hidden=!staffToken;
}
async function refresh() {
  try {
    const response=await fetch("/api/board",{cache:"no-store"});
    if(!response.ok) throw new Error("Could not refresh availability");
    const data=await response.json(); if(!Array.isArray(data.items)||data.items.length===0)throw Error("Empty inventory response"); board=data.items; events=data.events;
    connected=true;
    $("connection").textContent="Connected · Last staff change: "+(data.last_change_at?localTime(data.last_change_at):"none recorded")+". Availability is manually managed.";
    $("connection").classList.remove("connection-error");
    $("updated").textContent="Updated "+localTime(data.server_now);
    render();
  } catch(e) {connected=false;$("updated").textContent="Unable to connect — retry";$("connection").textContent="Connection unavailable: existing statuses may be outdated. Please contact library staff."; $("connection").classList.add("connection-error");}
}
let pendingSirsiItem = null;
document.addEventListener("click", event => {
  const btn=event.target.closest("button.toggle");
  if(!btn) return;
  const item=board.find(i=>i.id===btn.dataset.id);
  if(!item) return;
  if(item.out_of_service&&!item.checked_out_at){alert("Restore this item from out-of-service status before checkout.");return;}
  pendingSirsiItem=item;
  const checkingIn=!!item.checked_out_at;
  $("sirsi-title").textContent=checkingIn?"Return item in SirsiDynix first":"Check out item in SirsiDynix first";
  $("sirsi-message").textContent=checkingIn?
    "Complete the check-in in SirsiDynix before marking this item available.":
    "Complete the 3-hour reserve checkout in SirsiDynix before marking this item checked out.";
  $("sirsi-item").textContent=item.title+" | Barcode: "+item.barcode;
  $("sirsi-confirm").checked=false;
  $("sirsi-dialog").showModal();
});
$("sirsi-cancel").addEventListener("click",()=>{
  pendingSirsiItem=null;
  $("sirsi-dialog").close();
});
$("sirsi-form").addEventListener("submit",async event=>{
  event.preventDefault();
  if(!pendingSirsiItem||!$("sirsi-confirm").checked) return;
  const item=pendingSirsiItem;
  $("sirsi-save").disabled=true;
  try {
    const response=await fetch("/api/item/"+encodeURIComponent(item.id)+"/toggle",{
      method:"POST",headers:{"Authorization":"Bearer "+staffToken}
    });
    if(response.status===401){
      staffToken="";sessionStorage.removeItem("game-on-token");
      throw Error("Staff session expired. Sign in again.");
    }
    if(!response.ok)throw Error("Could not update the tracker. Verify the item's status.");
    pendingSirsiItem=null;
    $("sirsi-dialog").close();
    await refresh();
  }catch(error){alert(error.message);render();}
  finally{$("sirsi-save").disabled=false;}
});
$("search").addEventListener("input",render);
document.querySelectorAll("button.filter").forEach(button=>button.addEventListener("click",()=>{availabilityFilter=button.dataset.filter;document.querySelectorAll("button.filter").forEach(b=>{b.classList.toggle("active",b===button);b.setAttribute("aria-pressed",String(b===button));});render();}));
$("login-button").addEventListener("click",()=>{$("login-error").textContent="";$("password").value="";$("login-dialog").showModal();});
$("cancel").addEventListener("click",()=>$("login-dialog").close());
$("logout-button").addEventListener("click",()=>{staffToken="";sessionStorage.removeItem("game-on-token");render();});
$("login-form").addEventListener("submit",async e=>{
  e.preventDefault();
  try {
    const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("password").value})});
    const data=await r.json();if(!r.ok)throw Error(data.error||"Sign in failed");
    staffToken=data.token;sessionStorage.setItem("game-on-token",staffToken);$("login-dialog").close();render();
  }catch(error){$("login-error").textContent=error.message;}
});
document.addEventListener("error",e=>{if(e.target.tagName==="IMG"){e.target.hidden=true;e.target.parentElement.classList.add("no-image");}},true);
if(new URLSearchParams(window.location.search).get("staff")==="1" && !staffToken){
  $("login-error").textContent="";
  $("password").value="";
  $("login-dialog").showModal();
}

$("refresh-board").addEventListener("click",refresh);
function findBarcode(){
  if(!staffToken){$("scan-status").textContent="Staff sign-in required.";return;}
  const code=$("barcode-scan").value.trim();
  const item=board.find(i=>i.barcode===code);
  if(!item){$("scan-status").textContent="No item matches this barcode. Check the scan and SirsiDynix.";return;}
  $("search").value=item.barcode;
  availabilityFilter="all";
  document.querySelectorAll("button.filter").forEach(b=>{
    const selected=b.dataset.filter==="all";
    b.classList.toggle("active",selected);b.setAttribute("aria-pressed",String(selected));
  });
  render();
  $("scan-status").textContent="Found "+item.title+". Confirm checkout in SirsiDynix before updating the tracker.";
  document.querySelector(".card")?.scrollIntoView({block:"center"});
}
$("scan-find").addEventListener("click",findBarcode);
$("barcode-scan").addEventListener("keydown",e=>{if(e.key==="Enter"){e.preventDefault();findBarcode();}});
document.addEventListener("click",e=>{
  const b=e.target.closest("button.maintenance-open");if(!b)return;
  const item=board.find(i=>i.id===b.dataset.id);if(!item||!staffToken)return;
  pendingMaintenanceItem=item;
  $("maintenance-item").textContent=item.title+" · "+item.barcode;
  $("maintenance-out").checked=!!item.out_of_service;
  $("maintenance-note").value=item.condition_note||"";
  $("maintenance-error").textContent="";
  $("maintenance-dialog").showModal();
});
$("maintenance-cancel").addEventListener("click",()=>{$("maintenance-dialog").close();pendingMaintenanceItem=null;});
$("maintenance-form").addEventListener("submit",async e=>{
  e.preventDefault();if(!pendingMaintenanceItem)return;
  const b=$("maintenance-save");b.disabled=true;
  try{
    const r=await fetch("/api/staff/item/"+encodeURIComponent(pendingMaintenanceItem.id)+"/maintenance",{
      method:"POST",headers:{"Authorization":"Bearer "+staffToken,"Content-Type":"application/json"},
      body:JSON.stringify({out_of_service:$("maintenance-out").checked,note:$("maintenance-note").value})
    });
    const data=await r.json();if(!r.ok)throw Error(data.error||"Could not save condition");
    pendingMaintenanceItem=null;$("maintenance-dialog").close();await refresh();
  }catch(err){$("maintenance-error").textContent=err.message;}finally{b.disabled=false;}
});

refresh();setInterval(refresh,60000);setInterval(()=>{if(board.length)render();},30000);
