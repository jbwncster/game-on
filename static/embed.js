/* Student-only native LibGuides availability widget: no iframe, no staff actions. */
(function(){
"use strict";
const root=document.getElementById("game-on-embed");
if(!root)return;
const base="https://game-on-flame.vercel.app";
const githubCovers="https://raw.githubusercontent.com/jbwncster/game-on/main/static/covers/";
let items=[],filter="available",loaded=false;
const style=document.createElement("style");
style.textContent="#game-on-embed{font-family:Arial,sans-serif;max-width:1200px;margin:1rem auto;color:#263747}#game-on-embed .go-head{background:#183659;color:#fff;border-radius:12px;padding:1.1rem 1.3rem}#game-on-embed .go-head h2{margin:0 0 .5rem;color:#fff}#game-on-embed .go-nav{display:flex;flex-wrap:wrap;align-items:center;gap:.6rem;margin:1rem 0}#game-on-embed button{background:#fff;color:#16375e;border:1px solid #9cb4cf;border-radius:8px;padding:.6rem .9rem;cursor:pointer}#game-on-embed button[aria-pressed=true]{background:#183659;color:white}#game-on-embed input{padding:.65rem;border-radius:8px;border:1px solid #9cb4cf;min-width:210px;flex:1}#game-on-embed .go-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.85rem}#game-on-embed .go-card{border:1px solid #d5dfec;border-radius:10px;padding:1rem;background:white;display:grid;gap:.4rem}#game-on-embed .go-card strong{font-size:1.06rem}#game-on-embed .go-card img{display:block;width:100%;height:130px;object-fit:contain;background:#edf1f7}#game-on-embed .go-badge{font-weight:bold;color:#14683d}#game-on-embed .go-badge.out{color:#8a5405}#game-on-embed .go-muted{color:#586c80;font-size:.85rem}#game-on-embed .go-head a{color:white;text-decoration:underline}#game-on-embed .go-note{padding:.7rem;background:#fff5d9;border-radius:8px;margin:.8rem 0}";
root.appendChild(style);
const h=document.createElement("div");h.className="go-head";
h.innerHTML='<h2>🎲 Game On! — Eastern Wake Library</h2><p>Browse 28 games, puzzles & LEGO items · 3-hour reserve · Ask front desk</p><p><a target="_blank" rel="noopener noreferrer" href="'+base+'">Open the full tracker in a new tab</a> &nbsp;|&nbsp; <a target="_blank" rel="noopener noreferrer" href="'+base+'/?staff=1">🔒 Staff Login (opens in a new tab)</a></p>';
root.appendChild(h);
const note=document.createElement("p");note.className="go-note";note.textContent="Availability is updated manually by library staff and is not synced with SirsiDynix. Confirm at the front desk.";root.appendChild(note);
const nav=document.createElement("div");nav.className="go-nav";root.appendChild(nav);
const count=document.createElement("span");count.className="go-muted";const list=document.createElement("div");list.className="go-list";
const search=document.createElement("input");search.type="search";search.placeholder="Search games and puzzles";search.setAttribute("aria-label","Search games and puzzles");
nav.appendChild(search);
for(const [value,label] of [["available","Available now"],["all","All items"],["out","Checked out"]]){
  const button=document.createElement("button");button.type="button";button.textContent=label;button.dataset.filter=value;
  button.addEventListener("click",()=>{filter=value;render();});nav.appendChild(button);
}
root.appendChild(count);root.appendChild(list);
const fmt=iso=>new Date(iso).toLocaleString("en-US",{timeZone:"America/New_York",month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
function render(){
  for(const button of nav.querySelectorAll("button"))button.setAttribute("aria-pressed",String(button.dataset.filter===filter));
  if(!loaded){count.textContent="Loading the 28-item collection…";list.replaceChildren();return;}
  const q=search.value.toLowerCase().trim();
  const shown=items.filter(item=>(filter==="all"||(filter==="available"?!item.checked_out_at:!!item.checked_out_at))&&[item.title,item.description,item.category,item.barcode].join(" ").toLowerCase().includes(q));
  count.textContent=shown.length+" matching items · "+items.filter(i=>!i.checked_out_at).length+" currently listed as available";
  list.replaceChildren();
  if(!shown.length){const p=document.createElement("p");p.textContent="No items match these filters.";list.appendChild(p);return;}
  for(const item of shown){
    const card=document.createElement("article");card.className="go-card";
    const img=document.createElement("img");
    const match=String(item.image||"").match(/cover_(\d{2})\.webp$/);
    if(match && match[1]!=="24"){
      img.src=githubCovers+"cover_"+match[1]+".webp";
      img.addEventListener("error",()=>{
        if(img.dataset.fallback)return img.remove();
        img.dataset.fallback="1";img.src=base+item.image;
      });
    }else{
      img.src=base+item.image;
      img.addEventListener("error",()=>img.remove());
    }
    img.alt=item.title+" cover";img.loading="lazy";
    const title=document.createElement("strong");title.textContent=item.title;
    const meta=document.createElement("span");meta.className="go-muted";meta.textContent=item.details;
    const status=document.createElement("span");status.className="go-badge"+(item.checked_out_at?" out":"");
    status.textContent=item.checked_out_at?"Checked out · due "+fmt(item.due_at):"Available — ask front desk";
    card.append(img,title,meta,status);list.appendChild(card);
  }
}
search.addEventListener("input",render);
let pendingScript=null, loadTimeout=null;
function showLoadError(){
  if(loaded)return;
  count.textContent="Live availability could not load in LibGuides.";
  list.replaceChildren();
  const p=document.createElement("p");
  p.textContent="Open the tracker using the link above or ask the front desk.";
  list.appendChild(p);
}
window.GameOnReceive=function(data){
  if(!Array.isArray(data.items)||data.items.length!==28){showLoadError();return;}
  items=data.items;loaded=true;
  if(loadTimeout)clearTimeout(loadTimeout);
  if(pendingScript){pendingScript.remove();pendingScript=null;}
  render();
};
function refresh(){
  if(pendingScript)pendingScript.remove();
  const s=document.createElement("script");
  pendingScript=s;
  s.src=base+"/api/public-board.js?v="+Date.now();
  s.async=true;
  s.onerror=showLoadError;
  document.head.appendChild(s);
  if(loadTimeout)clearTimeout(loadTimeout);
  loadTimeout=setTimeout(()=>{if(!loaded)showLoadError();},12000);
}
render();
refresh();setInterval(refresh,60000);
})();
