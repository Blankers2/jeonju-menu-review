import re

_PRICE_TOKEN_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{3,}")
_HAS_LETTERS_RE = re.compile(r"[가-힣A-Za-z]{2,}")


def extract_prices(text: str) -> list[str]:
    """텍스트에서 가격 후보 토큰들을 추출. 메뉴명이면 빈 리스트."""
    cleaned = text.replace("원", " ").replace("₩", " ")
    if _HAS_LETTERS_RE.search(cleaned):
        return []
    return _PRICE_TOKEN_RE.findall(cleaned)


def is_price(text: str) -> bool:
    return len(extract_prices(text)) > 0


def _center(box):
    x, y, w, h = box["bbox"]
    return (x + w / 2.0, y + h / 2.0)


def _median_height(boxes):
    hs = sorted(b["bbox"][3] for b in boxes)
    return hs[len(hs) // 2] if hs else 20.0


def cluster_columns(boxes):
    """x중심 기준 1D 클러스터링. 갭이 평균폭의 2배 이상이면 새 컬럼.

    NOTE: 이 함수는 전체 박스 집합에서 페이지 컬럼을 감지한다.
    단순히 메뉴명-가격 사이의 수평 간격은 한 컬럼 내부 간격이므로,
    진짜 페이지 분할 갭(여러 메뉴+가격 묶음 사이)만 컬럼 경계로 취급한다.
    """
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
    """컬럼 내 y중심 기준 행 그룹핑. 간격 임계 = 중앙 글자높이*0.7."""
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


def _pair_row_by_content(row_indices, boxes):
    """행 내 박스들을 내용(메뉴/가격)으로 페어링.

    좌→우 순서로 순회하면서, 메뉴 박스가 나오면 새 그룹 시작.
    이후 가격 박스들은 직전 메뉴에 귀속.
    가격 다음 메뉴가 나오면(두 번째 페이지 컬럼) 새 그룹 시작.
    """
    ordered = sorted(row_indices, key=lambda i: _center(boxes[i])[0])
    groups = []  # list of (menu_parts, prices, src_indices)
    cur_menu, cur_prices, cur_src = [], [], []

    for i in ordered:
        text = boxes[i]["text"].strip()
        found = extract_prices(text)
        if found:
            # 가격 박스: 현재 그룹에 추가
            cur_prices.extend(found)
            cur_src.append(i)
        elif text:
            # 메뉴 박스: 이미 가격이 수집된 상태라면 새 그룹 시작
            if cur_prices:
                groups.append((list(cur_menu), list(cur_prices), list(cur_src)))
                cur_menu, cur_prices, cur_src = [], [], []
            cur_menu.append(text)
            cur_src.append(i)

    # 마지막 그룹 저장
    if cur_menu or cur_prices:
        groups.append((cur_menu, cur_prices, cur_src))

    return groups


def pair_boxes(boxes):
    """OCR 박스 → 메뉴 행 초안.

    전략:
    1. 전체를 y 기준으로 행 그룹핑 (같은 높이에 있는 박스들을 한 행으로)
    2. 각 행 내에서 x 순서 + 내용 타입(메뉴/가격)으로 페어링
       - 메뉴 다음에 가격들이 오면 해당 메뉴에 귀속
       - 가격 다음 새 메뉴가 나오면 새로운 페이지 컬럼으로 처리
    """
    if not boxes:
        return []
    rows_out = []
    # 1단계: 모든 박스를 y축 기준으로 행 그룹핑
    all_indices = list(range(len(boxes)))
    y_rows = cluster_rows(all_indices, boxes)

    for y_row in y_rows:
        groups = _pair_row_by_content(y_row, boxes)
        for menu_parts, prices, src in groups:
            menu_name = " ".join(menu_parts).strip()
            if prices:
                for p in prices:
                    rows_out.append({"menu": menu_name, "price": p, "source_boxes": list(src)})
            elif menu_name:
                rows_out.append({"menu": menu_name, "price": "", "source_boxes": list(src)})
    return rows_out
