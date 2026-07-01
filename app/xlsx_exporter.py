"""조립 드래프트 -> 최종 합본 .xlsx."""
from pathlib import Path

import openpyxl

HEADERS = ["place_id", "가게명", "item_id", "분류", "메뉴명", "가격",
           "영어", "일본어", "중국어간체", "중국어번체", "image_url"]


def draft_to_rows(draft: dict) -> list[list]:
    """드래프트 -> 출력 행 리스트. 메뉴/가격이 모두 빈 행은 제외."""
    out = []
    for r in draft.get("rows", []):
        menu = (r.get("menu") or "").strip()
        price = (r.get("price") or "").strip()
        if not menu and not price:
            continue
        out.append([
            draft.get("place_id"), draft.get("title", ""), draft.get("item_id", ""),
            r.get("category", ""), menu, price,
            r.get("en", ""), r.get("ja", ""), r.get("zh_cn", ""), r.get("zh_tw", ""),
            draft.get("image_url", ""),
        ])
    return out


def _sort_key(draft: dict):
    pid = draft.get("place_id")
    try:
        iid = int(draft.get("item_id"))
    except (TypeError, ValueError):
        iid = 0
    return (pid if pid is not None else 1 << 30, iid)


def write_workbook(drafts: list[dict], path: Path) -> int:
    """drafts -> xlsx. 반환: 기록한 데이터 행 수."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "menu"
    ws.append(HEADERS)
    n = 0
    for draft in sorted(drafts, key=_sort_key):
        for row in draft_to_rows(draft):
            ws.append(row)
            n += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return n
