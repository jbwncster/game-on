const $=id=>document.getElementById(id);
let token=sessionStorage.getItem("game-on-token")||"";
let report=null;
const fmt=iso=>iso?new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",dateStyle:"medium",timeStyle:"short"}):"—";
function cell(row,value){const td=document.createElement("td");td.textContent=String(value??"—");row.appendChild(td);}
function row(table, values){const tr=document.createElement("tr");values.forEach(v=>cell(tr,v));table.appendChild(tr);}
function empty(table, columns, message){if(table.children.length)return;const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=columns;td.textContent=message;tr.appendChild(td);table.appendChild(tr);}
function render(data){
  report=data;
  $("stats-dashboard").hidden=false;$("stats-login").hidden=true;
  $("stats-updated").textContent="Updated "+fmt(data.generated_at);
  $("stats-reset-note").textContent=data.stats_reset_at?"Reporting totals reset on "+fmt(data.stats_reset_at)+". Current availability is unchanged.":"Reporting totals include all recorded activity.";
  const kpis=[["All-time checkouts",data.total_checkouts],["Checkouts, 7 days",data.checkouts_7d],["Checkouts, 30 days",data.checkouts_30d],["Returns, 30 days",data.returns_30d],["Currently checked out",data.currently_out],["Currently overdue",data.currently_overdue]];
  $("stats-kpis").replaceChildren(...kpis.map(([label,value])=>{const item=document.createElement("div");item.className="stats-kpi";const n=document.createElement("strong");n.textContent=value;const p=document.createElement("span");p.textContent=label;item.append(n,p);return item;}));
  const out=$("stats-out");out.replaceChildren();
  data.current_out.forEach(i=>row(out,[i.title,i.barcode,fmt(i.checked_out_at),fmt(i.due_at),i.overdue?"Overdue":"Checked out"]));
  empty(out,5,"No items currently checked out.");
  const ranking=$("stats-ranking");ranking.replaceChildren();
  data.by_item.forEach(i=>row(ranking,[i.title,i.barcode,i.checkouts]));empty(ranking,3,"No checkouts recorded.");
  const events=$("stats-events");events.replaceChildren();
  data.recent.forEach(i=>row(events,[i.title,i.action==="checked_out"?"Checked out":"Checked in",fmt(i.at)]));
  empty(events,3,"No activity recorded yet.");
}
async function load(){
  const r=await fetch("/api/staff/stats",{headers:{Authorization:"Bearer "+token},cache:"no-store"});
  if(r.status===401){token="";sessionStorage.removeItem("game-on-token");$("stats-dashboard").hidden=true;$("stats-login").hidden=false;throw Error("Staff sign-in required.");}
  if(!r.ok)throw Error("Could not retrieve statistics.");
  render(await r.json());
}
$("stats-login-form").addEventListener("submit",async e=>{
  e.preventDefault();$("stats-error").textContent="";
  try{
    const r=await fetch("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({password:$("stats-password").value})});
    const d=await r.json();if(!r.ok)throw Error(d.error||"Sign-in failed");
    token=d.token;sessionStorage.setItem("game-on-token",token);$("stats-password").value="";
    await load();
  }catch(error){$("stats-error").textContent=error.message;}
});
$("stats-refresh").addEventListener("click",()=>load().catch(e=>alert(e.message)));
$("stats-logout").addEventListener("click",()=>{token="";sessionStorage.removeItem("game-on-token");report=null;closeClearPanel();$("stats-login").hidden=false;$("stats-dashboard").hidden=true;});
function csvCell(value){return '"'+String(value??"").replaceAll('"','""').replace(/^[=+@-]/,"'")+'"';}
$("stats-export").addEventListener("click",()=>{
  if(!report)return;
  const rows=[["Title","Barcode","Recorded checkouts"],...report.by_item.map(i=>[i.title,i.barcode,i.checkouts])];
  const csv=rows.map(r=>r.map(csvCell).join(",")).join("\r\n");
  const objectUrl=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
  const a=document.createElement("a");a.href=objectUrl;a.download="game-on-checkout-stats.csv";a.click();URL.revokeObjectURL(objectUrl);
});

const clearPanel=$("stats-clear-panel");
const clearOpen=$("stats-clear-open");
function closeClearPanel(){
  clearPanel.hidden=true;
  clearOpen.setAttribute("aria-expanded","false");
  $("stats-clear-password").value="";
  $("stats-clear-phrase").value="";
  $("stats-clear-error").textContent="";
}
clearOpen.addEventListener("click",()=>{
  if(!clearPanel.hidden){closeClearPanel();return;}
  clearPanel.hidden=false;
  clearOpen.setAttribute("aria-expanded","true");
  $("stats-clear-password").value="";
  $("stats-clear-phrase").value="";
  $("stats-clear-error").textContent="";
  $("stats-clear-password").focus();
  clearPanel.scrollIntoView({behavior:"smooth",block:"nearest"});
});
$("stats-clear-cancel").addEventListener("click",closeClearPanel);
$("stats-clear-form").addEventListener("submit",async event=>{
  event.preventDefault();
  if($("stats-clear-phrase").value!=="CLEAR STATS"){
    $("stats-clear-error").textContent="Type CLEAR STATS exactly to continue.";
    return;
  }
  const submit=$("stats-clear-submit");
  submit.disabled=true;
  $("stats-clear-error").textContent="";
  try{
    const response=await fetch("/api/staff/stats/reset",{
      method:"POST",
      headers:{"Authorization":"Bearer "+token,"Content-Type":"application/json"},
      body:JSON.stringify({
        password:$("stats-clear-password").value,
        confirmation:$("stats-clear-phrase").value
      })
    });
    const result=await response.json();
    if(!response.ok)throw Error(result.error||"Unable to reset statistics");
    closeClearPanel();
    await load();
  }catch(error){
    $("stats-clear-error").textContent=error.message;
  }finally{submit.disabled=false;}
});
if(token)load().catch(e=>{$("stats-error").textContent=e.message;});
