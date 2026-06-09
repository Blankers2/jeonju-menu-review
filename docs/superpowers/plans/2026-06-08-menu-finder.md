# Menu Finder 구현 계획 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 메뉴판 원본 이미지를 드래그앤드롭하면 OCR로 메뉴·가격 초안을 만들고, 사람이 박스↔표 연동 UI로 빠르게 검수·수정해 `place_id, 가게명, 메뉴명, 가격` CSV를 내보내는 로컬 웹앱을 만든다.

**Architecture:** 단일 FastAPI 앱. 드래그앤드롭 업로드 → 백그라운드 OCR 큐 → 순수 파이썬 모듈(StoreResolver/MenuPairer/CsvExporter)로 초안·매칭·내보내기 → 디스크 캐시(가게별 JSON) → 빌드 불필요한 순수 JS 프론트로 검수. OCR 엔진은 인터페이스로 추상화(기본 PaddleOCR, 교체 가능).

**Tech Stack:** Python 3.10+, PaddleOCR(korean), FastAPI, uvicorn, rapidfuzz, pytest. 프론트: HTML/CSS/Vanilla JS.

---

## File Structure

```
menu-finder/
  data/place_ids.csv                 # (이미 존재) place_id,title
  app/
    __init__.py
    config.py                        # 경로 상수
    models.py                        # 데이터 dataclass/타입
    store_resolver.py                # 파일명 정규화 + PlaceID 퍼지매칭
    menu_pairer.py                   # 박스 → 컬럼/행 클러스터링 → 메뉴↔가격 초안
    ocr_engine.py                    # OcrEngine 인터페이스 + PaddleOcrEngine
    draft_store.py                   # 가게별 JSON 영속화 + OCR 큐
    csv_exporter.py                  # 가게별/합본 CSV
    server.py                        # FastAPI 엔드포인트 + 정적 서빙
    static/
      index.html
      app.js
      style.css
  tests/
    test_store_resolver.py
    test_menu_pairer.py
    test_csv_exporter.py
    test_smoke.py
  storage/                           # 런타임 생성: images/, stores/
  requirements.txt
  README.md
```

**데이터 타입 (app/models.py 에서 확정, 전 태스크 공통):**

```python
# OcrBox: dict
#   {"text": str, "bbox": [x, y, w, h], "confidence": float, "polygon": [[x,y],[x,y],[x,y],[x,y]]}
# MenuRow: dict
#   {"menu": str, "price": str, "source_boxes": [int]}   # source_boxes = boxes 인덱스
# ImageData: dict
#   {"filename": str, "width": int, "height": int, "boxes": [OcrBox], "rows": [MenuRow], "reviewed": bool}
# StoreData: dict
#   {"store_key": str, "place_id": int|None, "title_extracted": str,
#    "title_confirmed": str|None, "status": "pending"|"in_progress"|"done",
#    "images": [ImageData]}
```

---

## Task 1: 프로젝트 스캐폴드 + 의존성

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py` (빈 파일)
- Create: `app/config.py`
- Create: `tests/__init__.py` (빈 파일)
- Create: `.gitignore`

- [ ] **Step 1: requirements.txt 작성**

```
fastapi>=0.110
uvicorn[standard]>=0.29
python-multipart>=0.0.9
rapidfuzz>=3.6
paddleocr>=2.7
paddlepaddle>=2.6
pytest>=8.0
pillow>=10.0
```

- [ ] **Step 2: app/config.py 작성**

```python
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PLACE_IDS_CSV = DATA_DIR / "place_ids.csv"
STORAGE_DIR = BASE_DIR / "storage"
IMAGES_DIR = STORAGE_DIR / "images"
STORES_DIR = STORAGE_DIR / "stores"
STATIC_DIR = BASE_DIR / "app" / "static"

for _d in (STORAGE_DIR, IMAGES_DIR, STORES_DIR):
    _d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 3: .gitignore 작성**

```
__pycache__/
*.pyc
storage/
.venv/
```

- [ ] **Step 4: 빈 패키지 파일 생성**

`app/__init__.py`, `tests/__init__.py` 를 빈 파일로 생성.

- [ ] **Step 5: 의존성 설치 검증**

Run: `pip install -r requirements.txt`
Expected: 설치 성공 (PaddleOCR/paddlepaddle 포함). 실패 시 README에 설치 메모 남기고 계속.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/__init__.py app/config.py tests/__init__.py .gitignore
git commit -m "chore: scaffold project and dependencies"
```

---

## Task 2: StoreResolver — 파일명 정규화

**Files:**
- Create: `app/store_resolver.py`
- Test: `tests/test_store_resolver.py`

- [ ] **Step 1: 정규화 실패 테스트 작성**

`tests/test_store_resolver.py`:

```python
from app.store_resolver import normalize_store_name


def test_strips_extension_crop_and_trailing_number():
    assert normalize_store_name("명품장어-crop.png") == "명품장어"
    assert normalize_store_name("궁한정식18-crop.png") == "궁한정식"
    assert normalize_store_name("늘채움5-crop.png") == "늘채움"

def test_strips_merged_and_bowan_suffix():
    assert normalize_store_name("소담촌1_merged.png") == "소담촌"
    assert normalize_store_name("소통한우2(보완)-crop.png") == "소통한우"

def test_strips_space_before_number():
    assert normalize_store_name("가족회관 1-crop.png") == "가족회관"

def test_plain_name():
    assert normalize_store_name("감로헌1.jpg") == "감로헌"
    assert normalize_store_name("자금성.png") == "자금성"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_store_resolver.py -v`
Expected: FAIL (ImportError: normalize_store_name).

- [ ] **Step 3: normalize_store_name 구현**

`app/store_resolver.py`:

```python
import re

_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp|bmp)$", re.IGNORECASE)
_SUFFIX_RE = re.compile(r"(-crop|_merged|\(보완\))", re.IGNORECASE)
# 끝에 붙은 공백+일련번호 제거 (예: "가족회관 1", "궁한정식18")
_TRAILING_NUM_RE = re.compile(r"\s*\d+$")


def normalize_store_name(filename: str) -> str:
    name = _EXT_RE.sub("", filename)
    # 접미사는 여러 번 붙을 수 있으니 반복 제거
    while True:
        new = _SUFFIX_RE.sub("", name)
        if new == name:
            break
        name = new
    name = _TRAILING_NUM_RE.sub("", name)
    return name.strip()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_store_resolver.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app/store_resolver.py tests/test_store_resolver.py
git commit -m "feat: filename normalization for store grouping"
```

---

## Task 3: StoreResolver — PlaceID 퍼지매칭

**Files:**
- Modify: `app/store_resolver.py`
- Test: `tests/test_store_resolver.py`

- [ ] **Step 1: 매칭 실패 테스트 추가**

`tests/test_store_resolver.py` 하단에 추가:

```python
from app.store_resolver import load_place_index, match_place


def _index():
    return load_place_index([
        (13763, "명품장어"),
        (13269, "한가람"),
        (13198, "한가람금암점"),
        (13194, "궁"),
        (13220, "늘채움"),
    ])


def test_exact_match_returns_top_candidate_with_high_score():
    cands = match_place("명품장어", _index())
    assert cands[0]["place_id"] == 13763
    assert cands[0]["score"] >= 99

def test_ambiguous_name_returns_ranked_candidates():
    # "한가람"은 "한가람"과 "한가람금암점" 둘 다 후보로
    cands = match_place("한가람", _index())
    ids = [c["place_id"] for c in cands[:2]]
    assert 13269 in ids and 13198 in ids
    # 정확히 같은 이름이 1순위
    assert cands[0]["place_id"] == 13269

def test_no_good_match_flags_low_confidence():
    # "궁한정식"은 목록에 없음 -> "궁"이 부분매칭되지만 확신 낮아야 함
    cands = match_place("궁한정식", _index())
    assert cands[0]["score"] < 90  # 자동확정 금지 임계 아래
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_store_resolver.py -v`
Expected: FAIL (ImportError: load_place_index).

- [ ] **Step 3: 매칭 함수 구현 (store_resolver.py 에 추가)**

```python
import csv
from pathlib import Path
from rapidfuzz import fuzz, process

from app.config import PLACE_IDS_CSV


def load_place_index(rows=None):
    """rows: [(place_id:int, title:str)]. None이면 PLACE_IDS_CSV에서 로드."""
    if rows is None:
        rows = []
        with open(PLACE_IDS_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append((int(r["place_id"]), r["title"].strip()))
    return [{"place_id": pid, "title": title} for pid, title in rows]


def match_place(store_name: str, place_index, limit: int = 5):
    """store_name과 후보 title 유사도 top-N. score 0~100."""
    choices = {i: e["title"] for i, e in enumerate(place_index)}
    results = process.extract(
        store_name, choices, scorer=fuzz.WRatio, limit=limit
    )
    out = []
    for title, score, idx in results:
        e = place_index[idx]
        out.append({"place_id": e["place_id"], "title": e["title"], "score": float(score)})
    return out


AUTO_CONFIRM_SCORE = 96  # 이 이상이면 PlaceID 자동 부여
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_store_resolver.py -v`
Expected: PASS (7 tests). `test_no_good_match_flags_low_confidence`가 통과하지 않으면 scorer를 `fuzz.ratio`로 바꿔 재시도하고 임계값을 코드와 일치시킨다.

- [ ] **Step 5: Commit**

```bash
git add app/store_resolver.py tests/test_store_resolver.py
git commit -m "feat: PlaceID fuzzy matching with confidence threshold"
```

---

## Task 4: MenuPairer — 가격 분류

**Files:**
- Create: `app/menu_pairer.py`
- Test: `tests/test_menu_pairer.py`

- [ ] **Step 1: 가격 판별 테스트 작성**

`tests/test_menu_pairer.py`:

```python
from app.menu_pairer import is_price, extract_prices


def test_is_price_various_formats():
    assert is_price("10,000원")
    assert is_price("10000")
    assert is_price("5,000")
    assert is_price("₩12,000")
    assert not is_price("장어탕")
    assert not is_price("식사류")

def test_extract_multiple_prices_in_one_cell():
    # 소/중/대가 한 박스에 묶인 경우
    assert extract_prices("10,000 / 13,000 / 16,000") == ["10,000", "13,000", "16,000"]
    assert extract_prices("8000") == ["8000"]
    assert extract_prices("장어탕") == []
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_menu_pairer.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: 가격 함수 구현**

`app/menu_pairer.py`:

```python
import re

# 3자리 이상 숫자(콤마 허용). "30포", "200g" 같은 수량과 구분 위해 최소 3자리.
_PRICE_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{3,}")
_HAS_LETTERS_RE = re.compile(r"[가-힣A-Za-z]{2,}")


def extract_prices(text: str) -> list[str]:
    """텍스트에서 가격 후보 토큰들을 추출. 메뉴명이면 빈 리스트."""
    # 글자가 많이 섞인 메뉴명(예: "장어탕")은 가격 아님.
    # 단, "10,000원"의 '원' 한 글자는 허용.
    cleaned = text.replace("원", " ").replace("₩", " ")
    if _HAS_LETTERS_RE.search(cleaned):
        return []
    return _PRICE_TOKEN_RE.findall(cleaned)


def is_price(text: str) -> bool:
    return len(extract_prices(text)) > 0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_menu_pairer.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/menu_pairer.py tests/test_menu_pairer.py
git commit -m "feat: price detection and multi-price extraction"
```

---

## Task 5: MenuPairer — 컬럼/행 클러스터링 + 페어링

**Files:**
- Modify: `app/menu_pairer.py`
- Test: `tests/test_menu_pairer.py`

- [ ] **Step 1: 페어링 실패 테스트 추가**

`tests/test_menu_pairer.py` 하단에 추가:

```python
from app.menu_pairer import pair_boxes


def _box(text, x, y, w=80, h=20):
    return {"text": text, "bbox": [x, y, w, h], "confidence": 0.9,
            "polygon": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]}


def test_single_column_pairs_menu_and_price():
    boxes = [
        _box("장어탕", 50, 100), _box("10,000원", 300, 102),
        _box("계란탕", 50, 140), _box("4,000원", 300, 141),
    ]
    rows = pair_boxes(boxes)
    assert {"menu": "장어탕", "price": "10,000"} in [
        {"menu": r["menu"], "price": r["price"]} for r in rows]
    assert {"menu": "계란탕", "price": "4,000"} in [
        {"menu": r["menu"], "price": r["price"]} for r in rows]

def test_two_columns_kept_separate():
    boxes = [
        _box("장어탕", 50, 100), _box("10,000원", 300, 100),
        _box("소주", 600, 100), _box("4,000원", 850, 100),
    ]
    rows = pair_boxes(boxes)
    pairs = {(r["menu"], r["price"]) for r in rows}
    assert ("장어탕", "10,000") in pairs
    assert ("소주", "4,000") in pairs
    # 장어탕이 소주 가격과 잘못 묶이면 안 됨
    assert ("장어탕", "4,000") not in pairs

def test_multi_price_row_expands_to_multiple_rows():
    boxes = [
        _box("냉면", 50, 100),
        _box("8,000", 250, 100), _box("9,000", 350, 100), _box("10,000", 450, 100),
    ]
    rows = pair_boxes(boxes)
    cold = [r for r in rows if r["menu"] == "냉면"]
    assert len(cold) == 3
    assert sorted(r["price"] for r in cold) == ["10,000", "8,000", "9,000"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_menu_pairer.py -v`
Expected: FAIL (ImportError: pair_boxes).

- [ ] **Step 3: 클러스터링 + 페어링 구현 (menu_pairer.py 에 추가)**

```python
def _center(box):
    x, y, w, h = box["bbox"]
    return (x + w / 2.0, y + h / 2.0)


def _median_height(boxes):
    hs = sorted(b["bbox"][3] for b in boxes)
    return hs[len(hs) // 2] if hs else 20.0


def cluster_columns(boxes):
    """x중심 기준 1D 클러스터링. 갭이 평균폭의 2배 이상이면 새 컬럼."""
    if not boxes:
        return []
    indexed = sorted(range(len(boxes)), key=lambda i: _center(boxes[i])[0])
    avg_w = sum(b["bbox"][2] for b in boxes) / len(boxes)
    gap = avg_w * 2.0
    columns, cur = [], [indexed[0]]
    for prev, idx in zip(indexed, indexed[1:]):
        if _center(boxes[idx])[0] - _center(boxes[prev])[0] > gap:
            columns.append(cur); cur = [idx]
        else:
            cur.append(idx)
    columns.append(cur)
    return columns


def cluster_rows(col_indices, boxes):
    """컬럼 내 y중심 기준 행 그룹핑. 간격 임계 = 중앙 글자높이*0.7 (기울기/좁은간격 허용)."""
    if not col_indices:
        return []
    tol = _median_height([boxes[i] for i in col_indices]) * 0.7
    ordered = sorted(col_indices, key=lambda i: _center(boxes[i])[1])
    rows, cur = [], [ordered[0]]
    for prev, idx in zip(ordered, ordered[1:]):
        if _center(boxes[idx])[1] - _center(boxes[prev])[1] > tol:
            rows.append(cur); cur = [idx]
        else:
            cur.append(idx)
    rows.append(cur)
    return rows


def pair_boxes(boxes):
    """OCR 박스 → 메뉴 행 초안. 컬럼 분리 → 행 그룹 → 메뉴/가격 페어링."""
    rows_out = []
    for col in cluster_columns(boxes):
        for row_idx in cluster_rows(col, boxes):
            row_idx_sorted = sorted(row_idx, key=lambda i: _center(boxes[i])[0])
            menu_parts, prices, src = [], [], []
            for i in row_idx_sorted:
                text = boxes[i]["text"].strip()
                found = extract_prices(text)
                if found:
                    prices.extend(found); src.append(i)
                elif text:
                    menu_parts.append(text); src.append(i)
            menu_name = " ".join(menu_parts).strip()
            if prices:
                for p in prices:
                    rows_out.append({"menu": menu_name, "price": p, "source_boxes": list(src)})
            elif menu_name:
                rows_out.append({"menu": menu_name, "price": "", "source_boxes": list(src)})
    return rows_out
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_menu_pairer.py -v`
Expected: PASS (5 tests). `test_two_columns_kept_separate` 실패 시 `cluster_columns`의 `gap` 배수를 조정(2.0→1.5)하고 테스트의 x좌표 간격과 정합되게 맞춘다.

- [ ] **Step 5: Commit**

```bash
git add app/menu_pairer.py tests/test_menu_pairer.py
git commit -m "feat: column/row clustering and menu-price pairing"
```

---

## Task 6: CsvExporter

**Files:**
- Create: `app/csv_exporter.py`
- Test: `tests/test_csv_exporter.py`

- [ ] **Step 1: 내보내기 실패 테스트 작성**

`tests/test_csv_exporter.py`:

```python
import csv
from app.csv_exporter import store_to_rows, write_combined_csv


def _store():
    return {
        "store_key": "명품장어", "place_id": 13763,
        "title_extracted": "명품장어", "title_confirmed": "명품장어",
        "status": "done",
        "images": [
            {"filename": "명품장어-crop.png", "width": 600, "height": 320,
             "boxes": [], "reviewed": True,
             "rows": [
                 {"menu": "장어탕", "price": "10,000", "source_boxes": []},
                 {"menu": "계란탕", "price": "4,000", "source_boxes": []},
             ]},
        ],
    }


def test_store_to_rows_uses_confirmed_title_and_place_id():
    rows = store_to_rows(_store())
    assert rows[0] == {"place_id": 13763, "가게명": "명품장어",
                       "메뉴명": "장어탕", "가격": "10,000"}
    assert len(rows) == 2

def test_skips_empty_menu_rows():
    s = _store()
    s["images"][0]["rows"].append({"menu": "", "price": "", "source_boxes": []})
    assert len(store_to_rows(s)) == 2

def test_write_combined_csv(tmp_path):
    out = tmp_path / "all.csv"
    write_combined_csv([_store()], out)
    with open(out, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["place_id"] == "13763"
    assert rows[0]["가게명"] == "명품장어"
    assert rows[0]["메뉴명"] == "장어탕"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_csv_exporter.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: CsvExporter 구현**

`app/csv_exporter.py`:

```python
import csv
from pathlib import Path

FIELDS = ["place_id", "가게명", "메뉴명", "가격"]


def store_to_rows(store: dict) -> list[dict]:
    title = store.get("title_confirmed") or store.get("title_extracted") or ""
    place_id = store.get("place_id")
    out = []
    for img in store.get("images", []):
        for row in img.get("rows", []):
            menu = (row.get("menu") or "").strip()
            price = (row.get("price") or "").strip()
            if not menu and not price:
                continue
            out.append({"place_id": place_id, "가게명": title,
                        "메뉴명": menu, "가격": price})
    return out


def write_store_csv(store: dict, path: Path) -> None:
    _write(store_to_rows(store), path)


def write_combined_csv(stores: list[dict], path: Path) -> None:
    rows = []
    for s in stores:
        rows.extend(store_to_rows(s))
    _write(rows, path)


def _write(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: Excel 한글 깨짐 방지
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_csv_exporter.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add app/csv_exporter.py tests/test_csv_exporter.py
git commit -m "feat: CSV export (per-store and combined, Excel-safe)"
```

---

## Task 7: OcrEngine 인터페이스 + PaddleOcrEngine

**Files:**
- Create: `app/ocr_engine.py`

> OCR은 외부 라이브러리/모델 의존이라 단위 TDD 대신 인터페이스 정의 + 스모크(Task 10)로 검증.

- [ ] **Step 1: ocr_engine.py 작성**

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image


class OcrEngine(ABC):
    @abstractmethod
    def read(self, image_path: Path) -> list[dict]:
        """이미지 1장 → OcrBox 리스트.
        OcrBox = {text, bbox:[x,y,w,h], confidence, polygon:[[x,y]*4]}"""
        ...


def _poly_to_bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    x, y = min(xs), min(ys)
    return [int(x), int(y), int(max(xs) - x), int(max(ys) - y)]


class PaddleOcrEngine(OcrEngine):
    def __init__(self, lang: str = "korean"):
        from paddleocr import PaddleOCR  # 지연 임포트(설치 무거움)
        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def read(self, image_path: Path) -> list[dict]:
        result = self._ocr.ocr(str(image_path), cls=True)
        boxes = []
        # PaddleOCR 반환: [ [ [poly, (text, conf)], ... ] ]  (페이지 1개)
        page = result[0] if result and result[0] is not None else []
        for poly, (text, conf) in page:
            poly = [[float(p[0]), float(p[1])] for p in poly]
            boxes.append({
                "text": text, "bbox": _poly_to_bbox(poly),
                "confidence": float(conf), "polygon": poly,
            })
        return boxes


def image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as im:
        return im.size  # (width, height)
```

- [ ] **Step 2: 임포트 확인**

Run: `python -c "from app.ocr_engine import OcrEngine, PaddleOcrEngine, image_size; print('ok')"`
Expected: `ok` (PaddleOcrEngine 인스턴스화는 모델 다운로드를 유발하므로 여기선 임포트만 확인).

- [ ] **Step 3: Commit**

```bash
git add app/ocr_engine.py
git commit -m "feat: OcrEngine interface and PaddleOCR implementation"
```

---

## Task 8: DraftStore — 영속화 + OCR 큐

**Files:**
- Create: `app/draft_store.py`
- Test: `tests/test_smoke.py` (일부)

- [ ] **Step 1: 저장/로드 실패 테스트 작성**

`tests/test_smoke.py`:

```python
from app import draft_store


def test_save_and_load_store(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_store, "STORES_DIR", tmp_path)
    store = {"store_key": "명문", "place_id": 13426,
             "title_extracted": "명문", "title_confirmed": None,
             "status": "pending", "images": []}
    draft_store.save_store(store)
    loaded = draft_store.load_store("명문")
    assert loaded["place_id"] == 13426
    assert "명문" in [s["store_key"] for s in draft_store.list_stores()]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_smoke.py::test_save_and_load_store -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: draft_store.py 구현**

```python
import json
import threading
import queue
from pathlib import Path

from app.config import STORES_DIR, IMAGES_DIR
from app.store_resolver import (
    normalize_store_name, load_place_index, match_place, AUTO_CONFIRM_SCORE,
)
from app.menu_pairer import pair_boxes
from app.ocr_engine import image_size


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._-가-힣" else "_" for c in name)


def store_path(store_key: str) -> Path:
    return STORES_DIR / f"{_safe(store_key)}.json"


def save_store(store: dict) -> None:
    p = store_path(store["store_key"])
    p.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def load_store(store_key: str) -> dict | None:
    p = store_path(store_key)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_stores() -> list[dict]:
    out = []
    for p in sorted(STORES_DIR.glob("*.json")):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


# ---- OCR 큐 (백그라운드 단일 워커) ----
_job_q: "queue.Queue[tuple[str, Path]]" = queue.Queue()
_progress = {"total": 0, "done": 0}
_lock = threading.Lock()
_place_index = None
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from app.ocr_engine import PaddleOcrEngine
        _engine = PaddleOcrEngine()
    return _engine


def _get_index():
    global _place_index
    if _place_index is None:
        _place_index = load_place_index()
    return _place_index


def enqueue_image(filename: str, path: Path) -> None:
    with _lock:
        _progress["total"] += 1
    _job_q.put((filename, path))


def progress() -> dict:
    with _lock:
        return dict(_progress)


def _ensure_store(store_key: str) -> dict:
    store = load_store(store_key)
    if store:
        return store
    cands = match_place(store_key, _get_index())
    place_id = cands[0]["place_id"] if cands and cands[0]["score"] >= AUTO_CONFIRM_SCORE else None
    title = cands[0]["title"] if place_id else store_key
    return {"store_key": store_key, "place_id": place_id,
            "title_extracted": title, "title_confirmed": None,
            "status": "pending", "candidates": cands, "images": []}


def _process(filename: str, path: Path) -> None:
    store_key = normalize_store_name(filename)
    store = _ensure_store(store_key)
    boxes = _get_engine().read(path)
    w, h = image_size(path)
    store["images"] = [im for im in store["images"] if im["filename"] != filename]
    store["images"].append({
        "filename": filename, "width": w, "height": h,
        "boxes": boxes, "rows": pair_boxes(boxes), "reviewed": False,
    })
    save_store(store)


def _worker() -> None:
    while True:
        filename, path = _job_q.get()
        try:
            _process(filename, path)
        except Exception as e:  # 실패해도 큐 진행
            print(f"[OCR ERROR] {filename}: {e}")
        finally:
            with _lock:
                _progress["done"] += 1
            _job_q.task_done()


def start_worker() -> None:
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_smoke.py::test_save_and_load_store -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/draft_store.py tests/test_smoke.py
git commit -m "feat: draft persistence and background OCR queue"
```

---

## Task 9: FastAPI 서버 + 엔드포인트

**Files:**
- Create: `app/server.py`

- [ ] **Step 1: server.py 작성**

```python
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import IMAGES_DIR, STATIC_DIR, STORAGE_DIR
from app import draft_store
from app.csv_exporter import write_store_csv, write_combined_csv, store_to_rows
from app.store_resolver import load_place_index

server = FastAPI(title="Menu Finder")


@server.on_event("startup")
def _startup():
    draft_store.start_worker()


@server.post("/api/upload")
async def upload(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        dest = IMAGES_DIR / f.filename
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        draft_store.enqueue_image(f.filename, dest)
        saved.append(f.filename)
    return {"queued": saved}


@server.get("/api/progress")
def get_progress():
    return draft_store.progress()


@server.get("/api/places")
def get_places():
    return load_place_index()


@server.get("/api/stores")
def get_stores():
    out = []
    for s in draft_store.list_stores():
        total = sum(len(i["rows"]) for i in s["images"])
        reviewed = sum(1 for i in s["images"] if i["reviewed"])
        out.append({"store_key": s["store_key"], "place_id": s.get("place_id"),
                    "title": s.get("title_confirmed") or s.get("title_extracted"),
                    "images": len(s["images"]), "reviewed_images": reviewed,
                    "rows": total, "status": s.get("status", "pending")})
    return out


@server.get("/api/stores/{store_key}")
def get_store(store_key: str):
    s = draft_store.load_store(store_key)
    if not s:
        raise HTTPException(404, "store not found")
    return s


@server.put("/api/stores/{store_key}")
def update_store(store_key: str, payload: dict):
    s = draft_store.load_store(store_key)
    if not s:
        raise HTTPException(404, "store not found")
    for k in ("place_id", "title_confirmed", "status", "images"):
        if k in payload:
            s[k] = payload[k]
    draft_store.save_store(s)
    return s


@server.get("/api/image/{filename}")
def get_image(filename: str):
    p = IMAGES_DIR / filename
    if not p.exists():
        raise HTTPException(404, "image not found")
    return FileResponse(p)


@server.get("/api/export")
def export_all():
    stores = draft_store.list_stores()
    out = STORAGE_DIR / "menu_all.csv"
    write_combined_csv(stores, out)
    return FileResponse(out, filename="menu_all.csv", media_type="text/csv")


@server.get("/api/export/{store_key}")
def export_store(store_key: str):
    s = draft_store.load_store(store_key)
    if not s:
        raise HTTPException(404, "store not found")
    out = STORAGE_DIR / f"menu_{store_key}.csv"
    write_store_csv(s, out)
    return FileResponse(out, filename=f"menu_{store_key}.csv", media_type="text/csv")


server.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

- [ ] **Step 2: 서버 임포트 확인**

Run: `python -c "from app.server import server; print([r.path for r in server.routes][:5])"`
Expected: 라우트 경로 리스트 출력(에러 없음).

- [ ] **Step 3: Commit**

```bash
git add app/server.py
git commit -m "feat: FastAPI endpoints for upload, stores, export"
```

---

## Task 10: 프론트엔드 — 드래그앤드롭 + 검수 UI

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/style.css`
- Create: `app/static/app.js`

> 프론트는 빌드 도구 없이 순수 JS. 검증은 Task 11 수동 스모크.

- [ ] **Step 1: index.html 작성**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Menu Finder</title>
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <header>
    <strong>Menu Finder</strong>
    <span id="progress">대기</span>
    <button id="export-all">전체 CSV 내보내기</button>
  </header>
  <div id="drop" class="drop">여기로 이미지(또는 폴더)를 드래그앤드롭</div>
  <main>
    <aside id="sidebar"></aside>
    <section id="viewer">
      <div id="img-wrap"><img id="img" alt="" /><canvas id="overlay"></canvas></div>
    </section>
    <section id="editor">
      <div class="store-head">
        <label>가게명 <input id="title" type="text" /></label>
        <label>PlaceID <input id="placeid" list="places" type="text" /></label>
        <datalist id="places"></datalist>
      </div>
      <table id="rows"><thead><tr><th>메뉴명</th><th>가격</th><th></th></tr></thead>
        <tbody></tbody></table>
      <div class="actions">
        <button id="add-row">+ 행 추가</button>
        <button id="mark-done">이미지 검수완료</button>
        <button id="save">저장</button>
      </div>
    </section>
  </main>
  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: style.css 작성**

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; }
header { display: flex; gap: 16px; align-items: center; padding: 8px 16px; background: #1f2937; color: #fff; }
header button { margin-left: auto; }
.drop { margin: 12px 16px; padding: 24px; border: 2px dashed #94a3b8; border-radius: 8px; text-align: center; color: #64748b; }
.drop.hot { background: #eef2ff; border-color: #6366f1; }
main { display: grid; grid-template-columns: 220px 1fr 380px; gap: 8px; padding: 0 12px 16px; height: calc(100vh - 140px); }
#sidebar { overflow: auto; border-right: 1px solid #e5e7eb; }
.store-item { padding: 8px; cursor: pointer; border-bottom: 1px solid #f1f5f9; font-size: 14px; }
.store-item:hover { background: #f8fafc; }
.store-item.active { background: #e0e7ff; }
#viewer { overflow: auto; }
#img-wrap { position: relative; display: inline-block; }
#img { max-width: 100%; display: block; }
#overlay { position: absolute; left: 0; top: 0; pointer-events: none; }
#editor { overflow: auto; }
.store-head { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
.store-head input { width: 100%; padding: 4px; }
table { width: 100%; border-collapse: collapse; }
th, td { border: 1px solid #e5e7eb; padding: 2px; }
td input { width: 100%; border: none; padding: 4px; }
tr.sel { background: #fef9c3; }
.actions { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
```

- [ ] **Step 3: app.js 작성**

```javascript
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
  renderImage();
  renderRows();
}

function curImage() { return current.images[curImageIdx]; }

function renderImage() {
  const img = $("#img");
  img.onload = drawBoxes;
  img.src = `/api/image/${encodeURIComponent(curImage().filename)}`;
}

function drawBoxes() {
  const img = $("#img"), cv = $("#overlay");
  const scale = img.clientWidth / curImage().width;
  cv.width = img.clientWidth; cv.height = img.clientHeight;
  const ctx = cv.getContext("2d");
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.strokeStyle = "#6366f1"; ctx.lineWidth = 1;
  curImage().boxes.forEach((b, i) => {
    const [x, y, w, h] = b.bbox;
    ctx.strokeRect(x * scale, y * scale, w * scale, h * scale);
  });
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
```

- [ ] **Step 4: Commit**

```bash
git add app/static/index.html app/static/style.css app/static/app.js
git commit -m "feat: drag-and-drop review UI (image overlay + editable table)"
```

---

## Task 10.5: 이미지 전환 UI + 박스↔행 양방향 클릭 연동

**Files:**
- Modify: `app/static/index.html` (이미지 탭 컨테이너 추가)
- Modify: `app/static/app.js`

> 한 가게가 여러 장(예: 궁한정식 18장)이므로 이미지 전환은 필수. 박스↔행 연동은 스펙의 핵심 검수 UX.

- [ ] **Step 1: index.html에 이미지 탭 영역 추가**

`<section id="viewer">` 의 `<div id="img-wrap">` **앞**에 다음 줄을 추가:

```html
      <div id="img-tabs"></div>
```

- [ ] **Step 2: 이미지 탭 렌더링 + 전환 (app.js)**

`renderImage` 함수 **위**에 추가하고, `openStore`의 `renderImage(); renderRows();` 호출 직전에 `renderTabs();`를 추가:

```javascript
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
```

`openStore` 안의 렌더 호출부를 다음으로 교체:

```javascript
  renderTabs();
  renderImage();
  renderRows();
```

- [ ] **Step 3: 박스↔행 양방향 클릭 연동 (app.js)**

`drawBoxes`를 아래로 교체(박스에 인덱스 보관 + 클릭 히트테스트):

```javascript
let _boxRects = [];  // 화면 좌표 캐시
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
let _highlightBoxes = new Set();

// 캔버스 클릭 → 포함하는 박스 찾기 → 해당 박스를 쓰는 행 강조
$("#overlay").addEventListener("click", (ev) => {
  const rect = ev.target.getBoundingClientRect();
  const px = ev.clientX - rect.left, py = ev.clientY - rect.top;
  const hit = _boxRects.find((r) => px >= r.x && px <= r.x + r.w && py >= r.y && py <= r.y + r.h);
  if (!hit) return;
  const rowIdx = curImage().rows.findIndex((row) => (row.source_boxes || []).includes(hit.i));
  selectRow(rowIdx, false);
});

function selectRow(rowIdx, scrollImage) {
  document.querySelectorAll("#rows tbody tr").forEach((tr, i) =>
    tr.classList.toggle("sel", i === rowIdx));
  _highlightBoxes = new Set(rowIdx >= 0 ? (curImage().rows[rowIdx].source_boxes || []) : []);
  drawBoxes();
}
```

`renderRows` 안에서 각 `<tr>` 생성 직후(예: `tb.appendChild(tr);` 다음 줄)에 행 클릭 핸들러를 추가:

```javascript
    tr.addEventListener("click", (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
      selectRow(i, true);
    });
```

- [ ] **Step 4: 탭/선택 스타일 추가 (style.css)**

`style.css` 하단에 추가:

```css
#img-tabs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.tab { padding: 2px 8px; border: 1px solid #cbd5e1; background: #fff; cursor: pointer; }
.tab.active { background: #6366f1; color: #fff; }
```

- [ ] **Step 5: 수동 확인**

Run: `uvicorn app.server:server` 후 여러 장 가게(예: 케이스모음 인페인팅 제외 원본 여러 장 또는 실폴더 `궁한정식*`) 업로드.
Expected: 탭으로 이미지 전환됨. 이미지의 박스 클릭 시 대응 표 행이 노란색 강조, 행 클릭 시 대응 박스가 빨간색 강조.

- [ ] **Step 6: Commit**

```bash
git add app/static/index.html app/static/app.js app/static/style.css
git commit -m "feat: image tabs and bidirectional box<->row highlighting"
```

---

## Task 11: 통합 스모크 + README

**Files:**
- Modify: `tests/test_smoke.py`
- Create: `README.md`

- [ ] **Step 1: 페어링 통합 스모크 테스트 추가 (OCR 없이)**

`tests/test_smoke.py` 하단에 추가:

```python
from app.menu_pairer import pair_boxes
from app.csv_exporter import store_to_rows


def test_pairing_to_export_endtoend():
    boxes = [
        {"text": "장어탕", "bbox": [50, 100, 80, 20], "confidence": 0.9, "polygon": []},
        {"text": "10,000원", "bbox": [300, 100, 80, 20], "confidence": 0.9, "polygon": []},
    ]
    rows = pair_boxes(boxes)
    store = {"store_key": "x", "place_id": 1, "title_extracted": "x",
             "title_confirmed": "x", "status": "done",
             "images": [{"filename": "x.png", "width": 600, "height": 320,
                         "boxes": boxes, "rows": rows, "reviewed": True}]}
    exported = store_to_rows(store)
    assert {"place_id": 1, "가게명": "x", "메뉴명": "장어탕", "가격": "10,000"} in exported
```

- [ ] **Step 2: 전체 테스트 통과 확인**

Run: `pytest -v`
Expected: 모든 테스트 PASS.

- [ ] **Step 3: README.md 작성**

```markdown
# Menu Finder

메뉴판 이미지에서 메뉴·가격을 OCR로 초안 추출하고 사람이 검수해 CSV로 내보내는 로컬 웹앱.

## 설치
    pip install -r requirements.txt

## 실행
    uvicorn app.server:server --reload
브라우저에서 http://127.0.0.1:8000 접속 → 이미지 드래그앤드롭.

## 사용
1. 메뉴판 이미지(또는 여러 장)를 화면에 드래그앤드롭 → 백그라운드 OCR.
2. 왼쪽 사이드바에서 가게 선택 → 왼쪽 이미지+박스, 오른쪽 표 확인.
3. 메뉴/가격 수정, 행 추가/삭제, 소·중·대는 "소/중/대" 버튼으로 행 분할.
4. 가게명/PlaceID 확인·수정 → "이미지 검수완료" → "저장".
5. "전체 CSV 내보내기"로 결과 다운로드.

## OCR 엔진 교체
`app/ocr_engine.py`의 `OcrEngine`를 구현하고 `draft_store._get_engine()`에서 교체.
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_smoke.py README.md
git commit -m "test: end-to-end smoke; docs: README"
```

- [ ] **Step 5: 수동 스모크(실데이터)**

Run: `uvicorn app.server:server` 후 브라우저에서 `케이스모음/명품장어.png`, `한가람.png` 드래그앤드롭.
Expected: OCR 완료 후 사이드바에 가게 등장, 표에 메뉴/가격 초안 표시, 박스 오버레이 표시, CSV 내보내기 동작.

---

## Self-Review (작성자 점검)

**Spec coverage:**
- 원본만 사용 ✓(업로드된 이미지 그대로 OCR) · PaddleOCR 교체가능 ✓(Task7 인터페이스) · 드래그앤드롭 ✓(Task10) · 백그라운드 OCR 큐+진행률 ✓(Task8,9) · 디스크 캐시 ✓(Task8) · 컬럼/행 클러스터링+기울기 허용 ✓(Task5) · 가격 숫자패턴 분류 ✓(Task4) · 소/중/대 행분할 ✓(Task5 자동 + Task10 버튼) · 박스 오버레이 ✓(Task10) · 가게명 자동추출+수정 ✓(Task2,10) · PlaceID 퍼지매칭 후보 ✓(Task3,8) · CSV `place_id,가게명,메뉴명,가격` ✓(Task6) · 합본 CSV ✓(Task6,9).
- 박스↔행 양방향 클릭 하이라이트 ✓(Task10.5) · 다중 이미지 전환 탭 ✓(Task10.5).
- 인페인팅 보강은 스펙상 MVP 밖 → 계획에서도 제외(일치).

**Placeholder scan:** "TODO/TBD/적절히" 없음. 코드 단계마다 실제 코드 포함.

**Type consistency:** OcrBox(text/bbox/confidence/polygon), MenuRow(menu/price/source_boxes), StoreData(store_key/place_id/title_extracted/title_confirmed/status/images) — Task4~10 전반 일치 확인. `pair_boxes`, `store_to_rows`, `match_place`, `normalize_store_name` 시그니처 호출부 일치.

**후속 보강(별도 작업, MVP 이후):**
- 이미지 줌/팬(현재 박스 클릭 히트테스트는 표시 배율 기준이라 동작하나, 큰 메뉴판 확대보기는 별도).
- 행 드래그 재정렬.
- 인페인팅 기반 분류 보강(스펙 6장).
