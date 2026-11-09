const $ = (id) => document.getElementById(id);
let board = [], events = [], staffToken = sessionStorage.getItem("game-on-token") || "";
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
  return '<img loading="lazy" src="'+esc(i.image)+'" alt="'+name+' cover" onerror="this.style.display=\'none\';this.parentElement.classList.add(\'no-image\')">';
}
function card(item) {
  const out=!!item.checked_out_at, late=out && new Date(item.due_at).getTime() < Date.now();
  const el=document.createElement("article");
  el.className="card"+(late?" late":"");
  const action=out?"Mark checked in":"Check out for 3 hours";
  el.innerHTML='<div class="cover">'+imageTag(item)+'</div><div class="content"><div class="category">'+esc(item.category)+'</div><h3>'+esc(item.title)+'</h3><p>'+esc(item.details)+'</p><p class="description">'+esc(item.description||"")+'</p>'+(item.warning?'<p class="warning">⚠ '+esc(item.warning)+'</p>':"")+
    '<p class="meta">RESERVE (Ask front desk)<br>'+esc(item.call_number)+' · '+esc(item.barcode)+'</p>'+
    (out?'<div class="checkout"><strong>'+(late?'Overdue':'Checked out')+'</strong><br>Out: '+localTime(item.checked_out_at)+'<br>Due: '+localTime(item.due_at)+'<br><span class="remaining">'+timeLeft(item.due_at)+'</span></div>':'<p class="ready">Available at the desk</p>')+
    (staffToken?'<button class="toggle" data-id="'+esc(item.id)+'">'+action+'</button>':'')+'</div>';
  return el;
}
function render() {
  const query=$("search").value.trim().toLowerCase();
  const matches=board.filter(x=>[x.title,x.category,x.details,x.barcode,x.call_number].join(" ").toLowerCase().includes(query));
  const avail=$("available"), out=$("out"); avail.replaceChildren(); out.replaceChildren();
  for(const item of matches) (item.checked_out_at?out:avail).appendChild(card(item));
  if(!avail.children.length) avail.innerHTML='<p class="empty">No available items match your search.</p>';
  if(!out.children.length) out.innerHTML='<p class="empty">No checked-out items match your search.</p>';
  const checked=board.filter(i=>i.checked_out_at);
  $("available-count").textContent=(board.length-checked.length)+" ready to borrow";
  $("out-count").textContent=checked.length+" checked out";
  $("overdue-count").textContent=checked.filter(i=>new Date(i.due_at)<new Date()).length+" overdue";
  const byId=Object.fromEntries(board.map(i=>[i.id,i.title]));
  $("events").replaceChildren(...events.map(e=>{
    const li=document.createElement("li");
    li.textContent=(byId[e.item_id]||e.item_id)+" — "+(e.action==="checked_out"?"Checked out":"Checked in")+" · "+localTime(e.at);
    return li;
  }));
  $("login-button").hidden=!!staffToken; $("logout-button").hidden=!staffToken;
}
async function refresh() {
  try {
    const response=await fetch("/api/board",{cache:"no-store"});
    if(!response.ok) throw new Error("Could not refresh availability");
    const data=await response.json(); board=data.items; events=data.events;
    $("updated").textContent="Updated "+localTime(data.server_now);
    render();
  } catch(e) {$("updated").textContent="Unable to connect — refresh the page"; }
}
document.addEventListener("click", async event=>{
  const btn=event.target.closest("button.toggle");
  if(!btn) return;
  btn.disabled=true;
  try {
    const response=await fetch("/api/item/"+encodeURIComponent(btn.dataset.id)+"/toggle",{method:"POST",headers:{"Authorization":"Bearer "+staffToken}});
    if(response.status===401){staffToken="";sessionStorage.removeItem("game-on-token");throw Error("Session expired. Sign in again.");}
    if(!response.ok) throw Error("Could not change item status.");
    await refresh();
  } catch(e){alert(e.message);btn.disabled=false;render();}
});
$("search").addEventListener("input",render);
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
refresh();setInterval(refresh,60000);setInterval(()=>{if(board.length)render();},30000);
