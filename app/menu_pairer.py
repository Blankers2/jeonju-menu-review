import re

# Matches phone-like sequences: digit groups joined by hyphens or dots
# e.g. 063-123-4567, 251-3535, 063.251.3535
_PHONE_RE = re.compile(r"\d{2,4}[-.]\d{3,4}(?:[-.]\d{3,4})?")

# Matches price tokens: comma-grouped numbers OR bare runs of 4+ digits
_SPLIT_PRICE_RE = re.compile(r"\d{1,3}(?:,\d{3})+|\d{4,}")
# Characters to strip from menu_part ends after price removal
_JUNK_STRIP_RE = re.compile(r"^[\s·.\-/원]+|[\s·.\-/원]+$")


def split_menu_price(text: str) -> tuple[str, list[str]]:
    """한 OCR 박스의 텍스트를 (메뉴명, 가격토큰 리스트)로 분리.

    - 가격 토큰: 콤마그룹 숫자 또는 4자리 이상 연속 숫자
    - 전화번호 패턴(숫자-숫자-숫자)은 가격으로 인식하지 않음
    - 가격 토큰에 바로 붙은 앞 '₩' 또는 뒤 '원' 도 제거
    - 나머지 텍스트가 menu_part (공백 정규화, 불필요한 구분자 제거)
    - 작은 숫자(3자리 이하)는 메뉴명에 그대로 보존
    """
    # Mask phone-like sequences before price extraction
    masked = _PHONE_RE.sub(" ", text)

    prices = _SPLIT_PRICE_RE.findall(masked)

    # Remove each price token and adjacent currency symbols from text
    menu_part = text
    for token in prices:
        # Remove ₩TOKEN원, ₩TOKEN, TOKEN원, TOKEN — in that order of specificity
        menu_part = re.sub(r"₩?" + re.escape(token) + r"원?", "", menu_part)

    # Also remove masked phone-like sequences from menu_part
    # (keep original phone text in menu_part — it is not a price token,
    #  so the menu text naturally retains it; no further action needed)

    # Strip junk separators from ends and collapse internal whitespace
    menu_part = _JUNK_STRIP_RE.sub("", menu_part)
    menu_part = re.sub(r"\s{2,}", " ", menu_part).strip()

    return (menu_part, prices)


def extract_prices(text: str) -> list[str]:
    """텍스트에서 가격 후보 토큰들을 추출. split_menu_price에 위임."""
    return split_menu_price(text)[1]


def is_price(text: str) -> bool:
    return len(extract_prices(text)) > 0


def _center(box):
    x, y, w, h = box["bbox"]
    return (x + w / 2.0, y + h / 2.0)


def _median_height(boxes):
    hs = sorted(b["bbox"][3] for b in boxes)
    return hs[len(hs) // 2] if hs else 20.0


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

    좌→우 순서로 순회하면서, split_menu_price 로 각 박스를 분해.
    - menu_part 가 있고 이미 가격이 수집된 상태면 → 새 그룹 시작
    - menu_part 를 현재 그룹 메뉴에 추가, prices 를 현재 그룹 가격에 추가
    - 병합 박스(menu+price 동시)도 자연스럽게 처리됨
    """
    ordered = sorted(row_indices, key=lambda i: _center(boxes[i])[0])
    groups = []  # list of (menu_parts, prices, src_indices)
    cur_menu, cur_prices, cur_src = [], [], []

    for i in ordered:
        text = boxes[i]["text"].strip()
        if not text:
            continue
        menu_part, prices = split_menu_price(text)

        if menu_part and cur_prices:
            # 새 메뉴가 나왔고 이미 가격이 수집됨 → 이전 그룹 마감
            groups.append((list(cur_menu), list(cur_prices), list(cur_src)))
            cur_menu, cur_prices, cur_src = [], [], []

        if menu_part:
            cur_menu.append(menu_part)
        cur_prices.extend(prices)
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
