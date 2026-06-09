# Menu Finder

메뉴판 이미지에서 메뉴·가격을 OCR로 초안 추출하고 사람이 검수해 CSV로 내보내는 로컬 웹앱.

## 설치
    pip install -r requirements.txt

## 실행
    python -m uvicorn app.server:server
브라우저에서 http://127.0.0.1:8000 접속 → 이미지 드래그앤드롭.

## 사용
1. 메뉴판 이미지(또는 여러 장)를 화면에 드래그앤드롭 → 백그라운드 OCR.
2. 왼쪽 사이드바에서 가게 선택 → 가운데 이미지+박스, 오른쪽 표 확인.
3. 메뉴/가격 수정, 행 추가/삭제, 소·중·대는 "소/중/대" 버튼으로 행 분할.
4. 이미지가 여러 장이면 상단 탭으로 전환. 이미지의 박스를 클릭하면 대응하는 표 행이, 표 행을 클릭하면 대응 박스가 강조됨.
5. 가게명/PlaceID 확인·수정 → "이미지 검수완료" → "저장".
6. "전체 CSV 내보내기"로 결과 다운로드 (컬럼: place_id, 가게명, 메뉴명, 가격).

## 산출물
- 전체 합본 CSV: `GET /api/export` (UTF-8 BOM, Excel 호환). 가게별: `GET /api/export/{store_key}`.

## 구조
- `app/ocr_engine.py` — OCR 엔진 인터페이스 + PaddleOCR(한국어) 구현.
- `app/menu_pairer.py` — OCR 박스를 메뉴/가격 행으로 클러스터링·페어링.
- `app/store_resolver.py` — 파일명에서 가게명 추출 + PlaceID 퍼지매칭(`data/place_ids.csv`).
- `app/draft_store.py` — 가게별 초안 영속화 + 백그라운드 OCR 큐.
- `app/csv_exporter.py` — CSV 내보내기.
- `app/server.py` — FastAPI 엔드포인트 + 정적 서빙.
- `app/static/` — 검수 UI (HTML/CSS/JS).

## OCR 엔진 교체
`app/ocr_engine.py`의 `OcrEngine`를 구현하고 `app/draft_store.py`의 `_get_engine()`에서 교체.

## 참고
- PaddleOCR 3.x + Windows 환경의 oneDNN 크래시를 피하기 위해 `PaddleOcrEngine`이 MKLDNN을 비활성화합니다(`app/ocr_engine.py` 참고).
