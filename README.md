# Menu Finder — 메뉴 번역 조립 도구

이미지별로 이미 추출·번역된 텍스트 조각(한국어 + 영/일/중간체/중번체)을 재사용해,
사람이 메뉴 이미지를 보며 **메뉴명↔가격을 조립**하고 최종 표를 .xlsx로 내보내는 로컬 웹앱.
(OCR 자동추출은 이미지 품질 한계로 폐기 — 번역은 재작업 없이 조각에서 자동 상속.)

## 설치
    pip install -r requirements.txt

## 입력 데이터 배치
- `data/place_item_list.xlsx` — 이미지 마스터 (`place_id, item_id, title, image_width, image_height, item_status, image_url`).
- `data/translations/` — 이미지별 번역본 .xlsx 들을 이 폴더에 모아 넣기 (각 파일에 `Item Id, Item Org Id, Org Content, 11_Chinese(Simplified), 12_Chinese(Traditional), 17_English, 30_Japanese` 컬럼). 합본 단일 파일도 가능.

## 실행
    python -m uvicorn app.server:server
브라우저에서 http://127.0.0.1:8000 접속.

## 사용
1. 상단 **가져오기** → 엑셀을 읽어 item_id별 초안 생성(이미 검수/수정한 것은 보존).
2. 좌측 사이드바에서 가게(place)별로 묶인 이미지(item_id) 선택.
3. 가운데에 `image_url`로 메뉴 이미지가 표시됨(＋/− 줌, "원본 새 탭").
4. 오른쪽 표: 메뉴명/가격/영어/일본어/중국어 간체·번체. 메뉴 조각은 번역과 함께 행으로 자동 배치돼 있음.
   - 행을 클릭해 선택한 뒤 아래 **가격 조각** 칩을 클릭하면 그 행의 가격이 채워짐(숫자만).
   - 인라인 편집, `＋`로 소/중/대 분할(메뉴·번역 복제, 가격만 비움), `×`로 행 삭제, "행 추가".
5. **저장** / **검수완료 토글**. 진행률은 상단에 표시.
6. **전체 .xlsx 내보내기**로 결과 다운로드.

## 산출물
`GET /api/export` → 합본 `menu_all.xlsx`. 컬럼:
`place_id, 가게명, item_id, 메뉴명, 가격, 영어, 일본어, 중국어간체, 중국어번체, image_url`
(place_id·item_id 정렬, 가격은 숫자만 — 번역 4종은 메뉴명 기준.)

## 구조
- `app/ingest.py` — 엑셀 파싱(이미지 마스터 + 번역폴더 → item_id별 조각).
- `app/classify.py` — 조각의 가격/메뉴 분류.
- `app/draft_store.py` — item_id별 초안 생성(번역 상속)·영속화(`storage/drafts/`).
- `app/xlsx_exporter.py` — 합본 .xlsx 내보내기.
- `app/server.py` — FastAPI 엔드포인트(`/api/import`, `/api/images`, `/api/export`) + 정적 서빙.
- `app/static/` — 조립 UI (HTML/CSS/JS).

## 참고
- 메뉴명을 직접 수정해도 번역은 자동 갱신되지 않음(조각이 깨끗해 대개 불필요, 필요시 수동 편집).
- 이미지에 있으나 조각이 누락된 메뉴는 "행 추가"로 직접 입력.
