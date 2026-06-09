const $ = (s) => document.querySelector(s);
let current = null;       // 현재 store 객체
let curImageIdx = 0;

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}

// ---- 드래그앤드롭 업로드 ----
const drop = $("#drop");
["dragover", "dragenter"].forEach((e) =>
  drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("hot"); }));
["dragleave", "drop"].forEach((e) =>
  drop.addEventListener(e, () => drop.classList.remove("hot")));
drop.addEventListener("drop", async (ev) => {
  ev.preventDefault();
  const files = [...ev.dataTransfer.files].filter((f) => f.type.startsWith("image/"));
  if (!files.length) return;
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  await api("/api/upload", { method: "POST", body: fd });
  pollProgress();
});

async function pollProgress() {
  const p = await api("/api/progress");
  $("#progress").textContent = `OCR ${p.done}/${p.total}`;
  await loadSidebar();
  if (p.done < p.total) setTimeout(pollProgress, 1500);
}

// ---- 사이드바 ----
async function loadSidebar() {
  const stores = await api("/api/stores");
  const el = $("#sidebar"); el.innerHTML = "";
  stores.forEach((s) => {
    const d = document.createElement("div");
    d.className = "store-item" + (current && current.store_key === s.store_key ? " active" : "");
    d.textContent = `${s.title} (${s.rows}) ${s.status === "done" ? "✓" : ""}`;
    d.onclick = () => openStore(s.store_key);
    el.appendChild(d);
  });
}

// ---- PlaceID 자동완성 ----
async function loadPlaces() {
  const places = await api("/api/places");
  const dl = $("#places"); dl.innerHTML = "";
  places.forEach((p) => {
    const o = document.createElement("option");
    o.value = p.place_id; o.label = `${p.place_id} ${p.title}`;
    dl.appendChild(o);
  });
}

// ---- 가게 열기 ----
async function openStore(key) {
  current = await api(`/api/stores/${encodeURIComponent(key)}`);
  curImageIdx = 0;
  $("#title").value = current.title_confirmed || current.title_extracted || "";
  $("#placeid").value = current.place_id ?? "";
  await loadSidebar();
  renderTabs();
  renderImage();
  renderRows();
}

function curImage() { return current.images[curImageIdx]; }

function renderTabs() {
  const el = $("#img-tabs"); el.innerHTML = "";
  current.images.forEach((im, i) => {
    const b = document.createElement("button");
    b.textContent = (im.reviewed ? "✓ " : "") + (i + 1);
    b.className = i === curImageIdx ? "tab active" : "tab";
    b.onclick = () => { curImageIdx = i; renderTabs(); renderImage(); renderRows(); };
    el.appendChild(b);
  });
}

function renderImage() {
  const img = $("#img");
  img.onload = drawBoxes;
  img.src = `/api/image/${encodeURIComponent(curImage().filename)}`;
}

let _boxRects = [];
let _highlightBoxes = new Set();
function drawBoxes() {
  const img = $("#img"), cv = $("#overlay");
  const scale = img.clientWidth / curImage().width;
  cv.width = img.clientWidth; cv.height = img.clientHeight;
  cv.style.pointerEvents = "auto";
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, cv.width, cv.height);
  _boxRects = curImage().boxes.map((b, i) => {
    const [x, y, w, h] = b.bbox;
    const r = { i, x: x * scale, y: y * scale, w: w * scale, h: h * scale };
    ctx.strokeStyle = _highlightBoxes.has(i) ? "#dc2626" : "#6366f1";
    ctx.lineWidth = _highlightBoxes.has(i) ? 2 : 1;
    ctx.strokeRect(r.x, r.y, r.w, r.h);
    return r;
  });
}

$("#overlay").addEventListener("click", (ev) => {
  const rect = ev.target.getBoundingClientRect();
  const px = ev.clientX - rect.left, py = ev.clientY - rect.top;
  const hit = _boxRects.find((r) => px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h);
  if (!hit) return;
  const rowIdx = curImage().rows.findIndex((row) => (row.source_boxes || []).includes(hit.i));
  selectRow(rowIdx);
});

function selectRow(rowIdx) {
  document.querySelectorAll("#rows tbody tr").forEach((tr, i) =>
    tr.classList.toggle("sel", i === rowIdx));
  _highlightBoxes = new Set(rowIdx >= 0 ? (curImage().rows[rowIdx].source_boxes || []) : []);
  drawBoxes();
}

// ---- 편집 표 ----
function renderRows() {
  const tb = $("#rows tbody"); tb.innerHTML = "";
  curImage().rows.forEach((row, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td><input value="${esc(row.menu)}" data-i="${i}" data-k="menu"></td>` +
      `<td><input value="${esc(row.price)}" data-i="${i}" data-k="price"></td>` +
      `<td><button data-split="${i}">소/중/대</button>` +
      `<button data-del="${i}">×</button></td>`;
    tb.appendChild(tr);
    tr.addEventListener("click", (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
      selectRow(i);
    });
  });
  tb.querySelectorAll("input").forEach((inp) =>
    inp.oninput = () => {
      curImage().rows[inp.dataset.i][inp.dataset.k] = inp.value;
    });
  tb.querySelectorAll("[data-del]").forEach((b) =>
    b.onclick = () => { curImage().rows.splice(+b.dataset.del, 1); renderRows(); });
  tb.querySelectorAll("[data-split]").forEach((b) =>
    b.onclick = () => {
      const r = curImage().rows[+b.dataset.split];
      curImage().rows.splice(+b.dataset.split + 1, 0,
        { menu: r.menu, price: "", source_boxes: [] });
      renderRows();
    });
}

function esc(s) { return (s ?? "").replace(/"/g, "&quot;"); }

// ---- 액션 ----
$("#add-row").onclick = () => {
  curImage().rows.push({ menu: "", price: "", source_boxes: [] });
  renderRows();
};
$("#mark-done").onclick = async () => {
  curImage().reviewed = true;
  current.status = current.images.every((i) => i.reviewed) ? "done" : "in_progress";
  await save();
  renderTabs();
};
$("#save").onclick = save;
async function save() {
  current.title_confirmed = $("#title").value;
  current.place_id = $("#placeid").value ? parseInt($("#placeid").value, 10) : null;
  await api(`/api/stores/${encodeURIComponent(current.store_key)}`,
    { method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify(current) });
  await loadSidebar();
}
$("#export-all").onclick = () => { window.location = "/api/export"; };

// init
loadPlaces();
loadSidebar();
