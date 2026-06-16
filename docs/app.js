// 시청 최종검수 정적 뷰어 (읽기 전용). data.json 로드 → 좌 이미지 / 우 메뉴·가격.
const $ = (s) => document.querySelector(s);
let ALL = [], view = [], cur = -1, zoom = 1, nW = 0, nH = 0;

function esc(s){return (s??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

async function boot(){
  let bundle;
  try { bundle = await (await fetch("./data.json")).json(); }
  catch(e){ document.body.innerHTML = "<p style='padding:24px'>data.json 을 불러오지 못했습니다. 로컬에서 열 때는 <code>python -m http.server</code> 로 실행하세요.</p>"; return; }
  ALL = bundle.items || [];
  $("#meta-gen").textContent = `${bundle.count}개 · 검수 ${bundle.reviewed} · ${bundle.generated_at}`;
  applyFilter("");
  if (view.length) open(0);
}

function applyFilter(q){
  q = q.trim().toLowerCase();
  view = ALL.filter(it => !q || (it.title+" "+it.item_id+" "+it.place_id+" "+it.rows.map(r=>r.menu).join(" ")).toLowerCase().includes(q));
  const jb = $("#jump"); jb.innerHTML = "";
  view.forEach((it,i)=>{ const o=document.createElement("option"); o.value=i;
    o.textContent = `${it.reviewed?"✓ ":""}${it.title||"(이름없음)"} · ${it.item_id}`; jb.appendChild(o); });
  if (!view.length){ $("#idx").textContent="0 / 0"; }
}

function open(i){
  if (i<0 || i>=view.length) return;
  cur=i; const it=view[i]; zoom=1; nW=nH=0;
  $("#store").textContent = it.title || "(이름없음)";
  $("#placeid").textContent = it.place_id ?? "—";
  $("#itemid").textContent = it.item_id ?? "—";
  $("#rev").textContent = it.reviewed ? "검수완료 ✓" : "";
  $("#orig").href = it.image_url || "#";
  $("#idx").textContent = `${i+1} / ${view.length}`;
  $("#jump").value = i;
  const img=$("#img"), sp=$("#spinner");
  sp.hidden=false; sp.classList.remove("err"); $("#sp-text").textContent="이미지 불러오는 중…"; img.classList.add("loading");
  img.onload=()=>{ sp.hidden=true; img.classList.remove("loading"); nW=img.naturalWidth; nH=img.naturalHeight; fit(); };
  img.onerror=()=>{ img.classList.remove("loading"); sp.classList.add("err"); $("#sp-text").textContent="이미지를 불러올 수 없습니다 (인터넷 연결 확인)"; };
  img.removeAttribute("src"); img.src=it.image_url||"";
  const tb=$("#menu tbody"); tb.innerHTML="";
  it.rows.forEach(r=>{ const tr=document.createElement("tr");
    tr.innerHTML=`<td class="m">${esc(r.menu)||"&nbsp;"}</td><td class="p${r.price?"":" empty"}">${esc(r.price)||"–"}</td>`;
    tb.appendChild(tr); });
}
function applyZoom(){ if(nW) $("#img").style.width=Math.round(nW*zoom)+"px"; }
function fit(){ const w=$("#imgwrap"); if(!nW||!nH)return; zoom=Math.min(w.clientWidth/nW, w.clientHeight/nH)||1; applyZoom(); }

$("#prev").onclick=()=>open(cur-1);
$("#next").onclick=()=>open(cur+1);
$("#jump").onchange=e=>open(+e.target.value);
$("#zi").onclick=()=>{zoom=Math.min(zoom*1.25,8);applyZoom();};
$("#zo").onclick=()=>{zoom=Math.max(zoom/1.25,.05);applyZoom();};
$("#zf").onclick=fit;
$("#search").addEventListener("input",e=>{ applyFilter(e.target.value); if(view.length) open(0); });
window.addEventListener("resize",()=>{if(nW)fit();});
document.addEventListener("keydown",e=>{
  if(e.target.tagName==="INPUT"||e.target.tagName==="SELECT")return;
  if(e.key==="ArrowLeft")open(cur-1); else if(e.key==="ArrowRight")open(cur+1);
});
boot();
