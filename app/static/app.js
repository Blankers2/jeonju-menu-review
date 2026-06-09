const $ = (s) => document.querySelector(s);
let current = null;       // 현재 item 드래프트
let selectedRow = -1;     // 가격 할당 대상 행
let zoom = 1;

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}

function esc(s) {
  return (s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

// ---- 설정(번역 폴더 경로) ----
async function loadSettings() {
  try {
    const s = await api("/api/settings");
    if (s.translations_dir) $("#trans-path").value = s.translations_dir;
  } catch (e) { /* ignore */ }
}

// ---- 폴더 드래그앤드롭 업로드 ----
const drop = $("#drop");
["dragover", "dragenter"].forEach((e) =>
  drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("hot"); }));
["dragleave", "dragend"].forEach((e) =>
  drop.addEventListener(e, () => drop.classList.remove("hot")));
drop.addEventListener("drop", async (ev) => {
  ev.preventDefault(); drop.classList.remove("hot");
  const files = await filesFromDrop(ev.dataTransfer);
  uploadFiles(files);
});
drop.addEventListener("click", (ev) => {
  if (ev.target.closest("details") || ev.target.tagName === "INPUT" || ev.target.tagName === "BUTTON") return;
  $("#folder").click();
});
$("#folder").addEventListener("change", (ev) => {
  const files = [...ev.target.files];
  files.forEach((f) => { f._rel = f.webkitRelativePath || f.name; });
  uploadFiles(files);
});

function readAllDirEntries(reader) {
  return new Promise((resolve, reject) => {
    const out = [];
    const read = () => reader.readEntries((es) => { es.length ? (out.push(...es), read()) : resolve(out); }, reject);
    read();
  });
}
function fileFromEntry(entry) { return new Promise((res, rej) => entry.file(res, rej)); }
async function collectEntry(entry, prefix, acc) {
  if (entry.isFile) { const f = await fileFromEntry(entry); f._rel = prefix + entry.name; acc.push(f); }
  else if (entry.isDirectory) {
    const es = await readAllDirEntries(entry.createReader());
    for (const e of es) await collectEntry(e, prefix + entry.name + "/", acc);
  }
}
async function filesFromDrop(dt) {
  const acc = [];
  const entries = [...dt.items].map((i) => i.webkitGetAsEntry && i.webkitGetAsEntry()).filter(Boolean);
  if (entries.length) { for (const e of entries) await collectEntry(e, "", acc); }
  else { [...dt.files].forEach((f) => { f._rel = f.name; acc.push(f); }); }
  return acc;
}

async function uploadFiles(allFiles) {
  const useful = allFiles.filter((f) => /\.(xlsx|zip)$/i.test(f.name) && !f.name.startsWith("~$"));
  const gsheets = allFiles.filter((f) => /\.gsheet$/i.test(f.name)).length;
  if (!useful.length) {
    if (gsheets) {
      alert(`구글시트(.gsheet) ${gsheets}개만 있어 읽을 수 없습니다.\n\n` +
            `Google Drive에서 해당 폴더를 "다운로드"하면 .xlsx로 변환된 .zip을 받습니다.\n` +
            `그 .zip(또는 .xlsx 파일들)을 드롭하세요.`);
    } else {
      alert(".xlsx 또는 .zip 파일을 찾지 못했습니다.");
    }
    return;
  }
  const fd = new FormData();
  useful.forEach((f) => { fd.append("files", f); fd.append("paths", f._rel || f.webkitRelativePath || f.name); });
  $("#progress").textContent = `업로드 중… (${useful.length}개 파일)`;
  try {
    const res = await api("/api/upload_translations", { method: "POST", body: fd });
    await loadSidebar();
    let msg = `완료: 신규 ${res.created} / 갱신 ${res.refreshed} / 보존 ${res.kept} / 전체 ${res.total} (번역 ${res.fragment_items}건)`;
    if (res.skipped_gsheet) msg += ` · ⚠ 구글시트 ${res.skipped_gsheet}개 건너뜀(xlsx로 받아야 함)`;
    $("#progress").textContent = msg;
  } catch (e) {
    $("#progress").textContent = "업로드 실패: " + e.message;
  }
}

// ---- (대안) 서버 경로에서 가져오기 ----
$("#import").onclick = async () => {
  $("#import").disabled = true;
  $("#progress").textContent = "가져오는 중… (네트워크 폴더는 다소 걸릴 수 있음)";
  try {
    const translations_dir = $("#trans-path").value.trim();
    const res = await api("/api/import", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ translations_dir }),
    });
    await loadSidebar();
    $("#progress").textContent =
      `가져옴: 신규 ${res.created} / 갱신 ${res.refreshed} / 보존 ${res.kept} / 전체 ${res.total} (번역 ${res.fragment_items}건)`;
  } catch (e) {
    $("#progress").textContent = "가져오기 실패: " + e.message;
  } finally { $("#import").disabled = false; }
};

// ---- 사이드바 (place 그룹) ----
let _images = [];
async function loadSidebar() {
  _images = await api("/api/images");
  const el = $("#sidebar"); el.innerHTML = "";
  let lastPlace = null;
  for (const im of _images) {
    if (im.place_id !== lastPlace) {
      lastPlace = im.place_id;
      const g = document.createElement("div");
      g.className = "place-group";
      g.textContent = `${im.title || "(이름없음)"} · ${im.place_id ?? "-"}`;
      el.appendChild(g);
    }
    const d = document.createElement("div");
    d.className = "img-item" + (im.reviewed ? " done" : "")
      + (current && current.item_id === im.item_id ? " active" : "");
    d.innerHTML = `${im.reviewed ? "✓ " : ""}item ${im.item_id} <span class="badge">(${im.rows}행)</span>`;
    d.onclick = () => openItem(im.item_id);
    el.appendChild(d);
  }
  updateProgress();
}

function updateProgress() {
  const done = _images.filter((i) => i.reviewed).length;
  $("#progress").textContent = `검수완료 ${done} / ${_images.length}`;
}

// ---- 아이템 열기 ----
async function openItem(itemId) {
  current = await api(`/api/images/${encodeURIComponent(itemId)}`);
  selectedRow = -1;
  zoom = 1;
  $("#title").value = current.title || "";
  $("#meta-info").textContent =
    `place ${current.place_id ?? "-"} · item ${current.item_id} · ${current.width ?? "?"}×${current.height ?? "?"}`;
  $("#open-orig").href = current.image_url || "#";
  renderImage();
  renderRows();
  renderPrices();
  // 사이드바 active 갱신
  document.querySelectorAll(".img-item").forEach((e) => e.classList.remove("active"));
  loadSidebar();
}

function renderImage() {
  const img = $("#img");
  img.src = current.image_url || "";
  applyZoom();
}
function applyZoom() { $("#img").style.transform = `scale(${zoom})`; }
$("#zoom-in").onclick = () => { zoom = Math.min(zoom * 1.25, 8); applyZoom(); };
$("#zoom-out").onclick = () => { zoom = Math.max(zoom / 1.25, 0.1); applyZoom(); };
$("#zoom-reset").onclick = () => { zoom = 1; applyZoom(); };

// ---- 조립 표 ----
const COLS = [
  ["menu", "메뉴명"], ["price", "가격"], ["en", "영어"],
  ["ja", "일본어"], ["zh_cn", "중국어간체"], ["zh_tw", "중국어번체"],
];

function renderRows() {
  const tb = $("#rows tbody"); tb.innerHTML = "";
  current.rows.forEach((row, i) => {
    const tr = document.createElement("tr");
    if (i === selectedRow) tr.classList.add("sel");
    tr.innerHTML =
      COLS.map(([k]) => `<td><input value="${esc(row[k])}" data-i="${i}" data-k="${k}"></td>`).join("") +
      `<td class="col-del"><button data-split="${i}" title="소/중/대 분할">＋</button>` +
      `<button data-del="${i}" title="삭제">×</button></td>`;
    tb.appendChild(tr);
    tr.addEventListener("click", (e) => {
      if (e.target.tagName === "BUTTON") return;
      selectedRow = i;
      document.querySelectorAll("#rows tbody tr").forEach((t, j) => t.classList.toggle("sel", j === i));
    });
  });
  tb.querySelectorAll("input").forEach((inp) =>
    inp.oninput = () => { current.rows[inp.dataset.i][inp.dataset.k] = inp.value; });
  tb.querySelectorAll("[data-del]").forEach((b) =>
    b.onclick = () => { current.rows.splice(+b.dataset.del, 1); if (selectedRow >= current.rows.length) selectedRow = -1; renderRows(); });
  tb.querySelectorAll("[data-split]").forEach((b) =>
    b.onclick = () => {
      const r = current.rows[+b.dataset.split];
      current.rows.splice(+b.dataset.split + 1, 0,
        { menu: r.menu, price: "", en: r.en, ja: r.ja, zh_cn: r.zh_cn, zh_tw: r.zh_tw });
      renderRows();
    });
}

// ---- 가격 팔레트 ----
function renderPrices() {
  const el = $("#price-palette"); el.innerHTML = "";
  (current.prices || []).forEach((p) => {
    const c = document.createElement("span");
    c.className = "price-chip";
    c.textContent = p.text;
    c.onclick = () => {
      if (selectedRow < 0) { alert("먼저 표에서 행을 클릭해 선택하세요."); return; }
      current.rows[selectedRow].price = p.number || p.text;
      renderRows();
      document.querySelectorAll("#rows tbody tr")[selectedRow]?.classList.add("sel");
    };
    el.appendChild(c);
  });
  if (!(current.prices || []).length) el.textContent = "(가격 조각 없음)";
}

// ---- 액션 ----
$("#add-row").onclick = () => {
  current.rows.push({ menu: "", price: "", en: "", ja: "", zh_cn: "", zh_tw: "" });
  renderRows();
};
$("#mark-done").onclick = async () => {
  current.reviewed = !current.reviewed;
  current.status = current.reviewed ? "done" : "pending";
  await save();
};
$("#save").onclick = save;
async function save() {
  current.title = $("#title").value;
  await api(`/api/images/${encodeURIComponent(current.item_id)}`, {
    method: "PUT", headers: { "content-type": "application/json" },
    body: JSON.stringify({
      rows: current.rows, title: current.title,
      reviewed: current.reviewed, status: current.status,
    }),
  });
  await loadSidebar();
}
$("#export-all").onclick = () => { window.location = "/api/export"; };

// init
loadSettings();
loadSidebar();
