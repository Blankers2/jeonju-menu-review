const $ = (s) => document.querySelector(s);
let current = null;       // 현재 item 드래프트
let selectedRow = -1;     // 가격 할당 대상 행
let dragFrom = -1;        // 드래그 중인 행 인덱스
let zoom = 1;
let catGroups = [];       // 현재 item의 분류 그룹(순서). 빈 그룹도 유지(뷰 전용)
let catInfo = {};         // 추천 카테고리 ko -> {has_fragment, en, ...}

// 드래그로 행 순서 변경: from 행을 to 위치로 이동(대상 행의 분류를 따라감)
function reorderRow(from, to) {
  if (from < 0 || from === to || !current) return;
  const cat = current.rows[to]?.category || "";
  const [r] = current.rows.splice(from, 1);
  r.category = cat;
  const dest = from < to ? to - 1 : to;  // 제거 후 인덱스 보정
  current.rows.splice(dest, 0, r);
  selectedRow = dest;
  renderRows();
}

// rows 배열을 그룹 순서(미분류 → catGroups 순)로 안정 정렬해 유지
function normalizeGroups() {
  for (const r of current.rows) {
    const c = (r.category || "").trim();
    if (c && !catGroups.includes(c)) catGroups.push(c);
  }
  const sel = current.rows[selectedRow];
  const order = ["", ...catGroups];
  const buckets = new Map(order.map((g) => [g, []]));
  for (const r of current.rows) buckets.get((r.category || "").trim()).push(r);
  current.rows = order.flatMap((g) => buckets.get(g));
  selectedRow = sel ? current.rows.indexOf(sel) : -1;
}

// 행을 특정 그룹의 끝으로 이동
function moveRowToGroup(from, cat) {
  if (from < 0 || !current) return;
  current.rows[from].category = cat;
  const sel = current.rows[from];
  normalizeGroups();
  selectedRow = current.rows.indexOf(sel);
  renderRows();
}

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
      g.innerHTML = `${esc(im.title) || "(이름없음)"} <span class="pid">#${im.place_id ?? "-"}</span>`;
      el.appendChild(g);
    }
    const d = document.createElement("div");
    d.className = "img-item" + (im.reviewed ? " done" : "")
      + (current && current.item_id === im.item_id ? " active" : "");
    d.innerHTML = `${im.reviewed ? "✓ " : ""}<span class="mono">${im.item_id}</span>`
      + ` <span class="badge">${im.rows}행</span>`;
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
  catGroups = [];
  catInfo = {};
  $("#tr-edit").checked = false;  // 아이템 열 때마다 번역 수정 OFF로 리셋
  $("#title").value = current.title || "";
  $("#meta-info").textContent =
    `place ${current.place_id ?? "-"} · item ${current.item_id} · ${current.width ?? "?"}×${current.height ?? "?"}`;
  $("#open-orig").href = current.image_url || "#";
  normalizeGroups();
  renderImage();
  renderRows();
  renderPrices();
  renderCityFix();
  renderCatBar();   // 추천은 비동기 로드
  // 사이드바 active 갱신
  document.querySelectorAll(".img-item").forEach((e) => e.classList.remove("active"));
  loadSidebar();
}

// 시청 수정지시 코멘트 배너
async function renderCityFix() {
  const el = $("#city-fix");
  el.hidden = true; el.innerHTML = "";
  try {
    const fx = await api(`/api/fixes/${encodeURIComponent(current.item_id)}`);
    if (!fx || !fx.comments || !fx.comments.length) return;
    const pages = (fx.pages || []).join(", ");
    el.innerHTML = `<div class="cf-head">📋 시청 수정요청${pages ? ` <span class="cf-pg">p.${pages}</span>` : ""}</div>`
      + fx.comments.map((c) => `<div class="cf-line">${esc(c).replace(/\n/g, "<br>")}</div>`).join("")
      + ((fx.memo && fx.memo.length) ? `<div class="cf-memo">메모: ${esc(fx.memo.join(" / "))}</div>` : "");
    el.hidden = false;
  } catch (e) { /* 코멘트 없거나 파일 없음 → 무시 */ }
}

let naturalW = 0, naturalH = 0;
function renderImage() {
  const img = $("#img");
  naturalW = naturalH = 0;
  img.style.transform = "";
  img.onload = () => { naturalW = img.naturalWidth; naturalH = img.naturalHeight; fitImage(); };
  img.src = current.image_url || "";
}
function applyZoom() { if (naturalW) $("#img").style.width = Math.round(naturalW * zoom) + "px"; }
function fitImage() {
  const wrap = $("#img-wrap");
  if (!naturalW || !naturalH) return;
  zoom = Math.min(wrap.clientWidth / naturalW, wrap.clientHeight / naturalH) || 1;
  applyZoom();
}
$("#zoom-in").onclick = () => { zoom = Math.min(zoom * 1.25, 8); applyZoom(); };
$("#zoom-out").onclick = () => { zoom = Math.max(zoom / 1.25, 0.05); applyZoom(); };
$("#zoom-reset").onclick = () => { fitImage(); };  // "맞춤" = 영역에 맞게
window.addEventListener("resize", () => { if (naturalW) fitImage(); });

// ---- 카테고리 그룹 바 ----
let _catReq = 0;
async function renderCatBar() {
  const chips = $("#cat-chips");
  chips.innerHTML = `<span class="hint">추천 불러오는 중…</span>`;
  const token = ++_catReq;
  try {
    const res = await api(`/api/categories/${encodeURIComponent(current.item_id)}`);
    if (token !== _catReq) return;  // 다른 item으로 이동함
    catInfo = {};
    for (const s of res.suggestions || []) catInfo[s.ko] = s;
    drawCatChips();
    if (catGroups.length) renderRows();  // 그룹 헤더의 조각 배지 갱신
  } catch (e) {
    if (token === _catReq) chips.innerHTML = `<span class="hint">추천 없음</span>`;
  }
}

function drawCatChips() {
  const chips = $("#cat-chips");
  chips.innerHTML = "";
  const names = Object.keys(catInfo).filter((k) => !catGroups.includes(k));
  if (!names.length) {
    chips.innerHTML = `<span class="hint">${Object.keys(catInfo).length ? "모든 추천 추가됨" : "추천 없음 — 직접입력"}</span>`;
    return;
  }
  for (const ko of names) {
    const s = catInfo[ko];
    const c = document.createElement("button");
    c.className = "cat-chip" + (s.has_fragment ? "" : " no-frag");
    c.textContent = ko;
    c.title = s.has_fragment
      ? `번역조각 있음 · en: ${s.en || "-"} / ja: ${s.ja || "-"}`
      : "⚠ 번역조각 없음 (한국어만 — 번역은 별도 확보 필요)";
    c.onclick = () => addCatGroup(ko);
    chips.appendChild(c);
  }
}

function addCatGroup(name) {
  name = (name || "").trim();
  if (!name || catGroups.includes(name)) return;
  catGroups.push(name);
  normalizeGroups();
  renderRows();
  drawCatChips();
}

$("#cat-add").onclick = () => { addCatGroup($("#cat-new").value); $("#cat-new").value = ""; };
$("#cat-new").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); addCatGroup($("#cat-new").value); $("#cat-new").value = ""; }
});

// ---- 조립 표 ----
const COLS = [
  ["menu", "메뉴명"], ["price", "가격"], ["en", "영어"],
  ["ja", "일본어"], ["zh_cn", "중국어간체"], ["zh_tw", "중국어번체"],
];
// 번역 컬럼은 기본 수정 금지(읽기 전용) — "번역 수정" 토글을 켠 경우에만 편집 허용
const TR_COLS = new Set(["en", "ja", "zh_cn", "zh_tw"]);
function trEditable() { return $("#tr-edit").checked; }
function isLocked(k) { return TR_COLS.has(k) && !trEditable(); }

function renderRows() {
  const tb = $("#rows tbody"); tb.innerHTML = "";

  const makeHeader = (name) => {
    const tr = document.createElement("tr");
    tr.className = "cat-row";
    const isUncat = name === "";
    const s = catInfo[name];
    const frag = isUncat ? "" : (s
      ? (s.has_fragment ? `<span class="cr-frag ok" title="en: ${esc(s.en)} / ja: ${esc(s.ja)}">조각✓</span>`
                        : `<span class="cr-frag warn">조각없음</span>`)
      : "");
    const n = current.rows.filter((r) => (r.category || "").trim() === name).length;
    tr.innerHTML = `<td colspan="${COLS.length + 1}">` +
      `<span class="cr-name">${isUncat ? "미분류" : esc(name)}</span>` +
      `<span class="cr-cnt">${n}행</span>${frag}` +
      (isUncat ? "" : `<button class="cr-del" title="그룹 해제(행은 미분류로)">×</button>`) +
      `</td>`;
    // 그룹 헤더에 드롭 → 그 그룹으로 이동
    tr.addEventListener("dragover", (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; tr.classList.add("drop-target"); });
    tr.addEventListener("dragleave", () => tr.classList.remove("drop-target"));
    tr.addEventListener("drop", (e) => {
      e.preventDefault(); tr.classList.remove("drop-target");
      moveRowToGroup(dragFrom, name);
    });
    if (!isUncat) tr.querySelector(".cr-del").onclick = () => {
      current.rows.forEach((r) => { if ((r.category || "").trim() === name) r.category = ""; });
      catGroups = catGroups.filter((g) => g !== name);
      normalizeGroups(); renderRows(); drawCatChips();
    };
    return tr;
  };

  const renderRow = (row, i) => {
    const tr = document.createElement("tr");
    if (i === selectedRow) tr.classList.add("sel");
    tr.innerHTML =
      `<td class="col-del">` +
      `<span class="drag" draggable="true" title="드래그해서 행 이동/분류">⠿</span>` +
      `<button data-split="${i}" title="소/중/대 분할">＋</button>` +
      `<button data-del="${i}" title="삭제">×</button></td>` +
      COLS.map(([k]) =>
        `<td><input value="${esc(row[k])}" data-i="${i}" data-k="${k}"${isLocked(k) ? ' readonly tabindex="-1" title="번역은 기본 수정 불가 — 상단 [번역 수정] 토글을 켜세요"' : ""}></td>`
      ).join("");
    tb.appendChild(tr);
    tr.addEventListener("click", (e) => {
      if (e.target.tagName === "BUTTON") return;
      selectedRow = i;
      tb.querySelectorAll("tr:not(.cat-row)").forEach((t) => t.classList.toggle("sel", +t.querySelector("input")?.dataset.i === i));
    });
    // ---- 드래그로 행 이동 ----
    const handle = tr.querySelector(".drag");
    handle.addEventListener("dragstart", (e) => {
      dragFrom = i; tr.classList.add("dragging"); e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(i));
    });
    handle.addEventListener("dragend", () => {
      tr.classList.remove("dragging");
      tb.querySelectorAll("tr").forEach((t) => t.classList.remove("drop-target"));
    });
    tr.addEventListener("dragover", (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; tr.classList.add("drop-target"); });
    tr.addEventListener("dragleave", () => tr.classList.remove("drop-target"));
    tr.addEventListener("drop", (e) => { e.preventDefault(); tr.classList.remove("drop-target"); reorderRow(dragFrom, i); });
  };

  // rows는 normalizeGroups로 항상 [미분류…, 그룹1…, 그룹2…] 순으로 유지됨.
  // 미분류 헤더는 항상 표시(처음부터 그룹핑 모드) — 여기서 그룹으로 드래그해 분류.
  let i = 0;
  for (const g of ["", ...catGroups]) {
    tb.appendChild(makeHeader(g));
    while (i < current.rows.length && (current.rows[i].category || "").trim() === g) {
      renderRow(current.rows[i], i); i++;
    }
  }
  tb.querySelectorAll("input").forEach((inp) => {
    inp.oninput = () => {
      if (isLocked(inp.dataset.k)) return;  // 번역 컬럼 수정 금지(토글 OFF 시)
      current.rows[inp.dataset.i][inp.dataset.k] = inp.value;
    };
    // ↑/↓/Enter 로 같은 컬럼 위아래 이동 (가격을 보면서 아래로 쭉 입력)
    inp.addEventListener("keydown", (e) => {
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp" && e.key !== "Enter") return;
      e.preventDefault();
      const i = +inp.dataset.i, k = inp.dataset.k;
      const ni = e.key === "ArrowUp" ? i - 1 : i + 1;
      const tgt = tb.querySelector(`input[data-i="${ni}"][data-k="${k}"]`);
      if (tgt) { tgt.focus(); tgt.select(); }
    });
  });
  tb.querySelectorAll("[data-del]").forEach((b) =>
    b.onclick = () => { current.rows.splice(+b.dataset.del, 1); if (selectedRow >= current.rows.length) selectedRow = -1; renderRows(); });
  tb.querySelectorAll("[data-split]").forEach((b) =>
    b.onclick = () => {
      const r = current.rows[+b.dataset.split];
      current.rows.splice(+b.dataset.split + 1, 0,
        { category: r.category || "", menu: r.menu, price: "", en: r.en, ja: r.ja, zh_cn: r.zh_cn, zh_tw: r.zh_tw });
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
  current.rows.push({ category: "", menu: "", price: "", en: "", ja: "", zh_cn: "", zh_tw: "" });
  normalizeGroups();  // 미분류 구간(맨 위 그룹)으로 정렬 유지
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
      allow_translation_edit: trEditable(),  // 토글 ON일 때만 번역 수정 허용
    }),
  });
  await loadSidebar();
}

// 번역 수정 토글: 표를 다시 그려 readonly 상태 갱신
$("#tr-edit").addEventListener("change", () => { if (current) renderRows(); });
$("#export-all").onclick = () => { window.location = "/api/export"; };

// init
loadSettings();
loadSidebar();
