"""시청 수정지시(26.6.23) 중 자동 반영 가능한 건 적용 — 드라이런 기본, --apply 시 백업 후 실행.

대상(코멘트 원문 기반, 데이터로 확인된 것만 명시 규칙으로 하드코딩 — 임의 해석 없음):
 - 페이지(item) 삭제: "N페이지 삭제" 지시 중 deletion_candidates에서 item 특정된 건.
   삭제 전 place의 다른 item과 (menu,price) 중복률을 증거로 출력. place가 비면 중단.
 - 행 복사: 소통한우 — 176p 삭제 전 '한우사골떡국'(번역 포함)을 175p로 이동.
 - 행 삭제: 특정 메뉴 삭제 지시(정확일치로만 매칭 — '짬뽕' 지시가 '낙지짬뽕'을 지우지 않게).
 - 가격 기재: 기존 행에 명시가 지시(왕본참치 '연어 초밥' 28,000원).
교차참조(다른 가게 페이지와 중복) 3건 등 나머지는 리포트만 — 편집기 2차 검수에서 수동.
사용: python tools/apply_city_fixes.py           # 드라이런
      python tools/apply_city_fixes.py --apply   # 백업 후 적용
"""
import argparse
import datetime as dt
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"

# "N페이지 삭제" → item (storage/deletion_candidates.json에서 상대순서로 특정된 것)
ITEM_DELETES = [
    # (place_id, item_id, 지시 요약)
    (13266, "103947", "129페이지 삭제(128과 중복)"),
    (13397, "105720", "176페이지 삭제(한우사골떡국은 175로 이동)"),
    (13407, "105755", "202페이지 삭제"),
    (13413, "105743", "209페이지 삭제(210 중복)"),
    (13425, "105689", "229페이지 삭제"),
    (13430, "105733", "238페이지 삭제"),
    (13430, "105742", "239페이지 삭제"),
]
# 삭제 전 행 이동: (from_item, menu정확일치, to_item)
ROW_COPIES = [
    ("105720", "한우사골떡국", "105710"),
]
# 메뉴 행 삭제(정확일치)
ROW_DELETES = [
    (13277, "104054", "양념소금장어구이 (100g)", "양념소금장어구이 100g 삭제"),
    (13388, "105764", "새우볶음밥", "새우볶음밥 삭제"),
    (13388, "105767", "짬뽕", "짬뽕 삭제"),
    (13421, "105761", "이강주 (유리병)", "이강주 유리병 삭제"),
]
# 기존 행 가격 기재
PRICE_SETS = [
    (13247, "103978", "연어 초밥", "28,000", "연어초밥 가격 기재 28,000원"),
]
# 자동 불가 → 편집기 수동 (리포트에만 표시)
MANUAL_NOTES = [
    "13232 꽃마름중화산점: 77페이지(교차참조)와 중복 — 시청 PDF 대조 필요",
    "13236 육일식당: 82페이지(교차참조)와 중복 — 시청 PDF 대조 필요",
    "13272 샤브향중화산점: 140페이지 삭제 — 상대순서 미확정, 이미지 확인 필요",
    "그 외 추가기재/카테고리분류/순서변경/맵기 등은 편집기 배너 보며 2차 검수",
]


def load_item(iid: str) -> tuple[Path, dict]:
    hits = list(DRAFTS.glob(f"*_{iid}.json"))
    if not hits:
        raise SystemExit(f"item {iid} 파일 없음")
    return hits[0], json.loads(hits[0].read_text(encoding="utf-8"))


def save_item(path: Path, d: dict) -> None:
    d["edited"] = True
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def dup_ratio(pid: int, iid: str) -> float:
    """삭제 대상 item의 (menu,price)가 같은 place의 나머지 item에 얼마나 있는지."""
    _, d = load_item(iid)
    mine = {(r.get("menu", "").strip(), str(r.get("price", "")).strip()) for r in d["rows"]}
    others = set()
    for p in DRAFTS.glob(f"{pid}_*.json"):
        o = json.loads(p.read_text(encoding="utf-8"))
        if str(o["item_id"]) != str(iid):
            others |= {(r.get("menu", "").strip(), str(r.get("price", "")).strip()) for r in o["rows"]}
    return (len(mine & others) / len(mine)) if mine else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    # 안전: 삭제 후 place가 비지 않는지
    for pid, iid, why in ITEM_DELETES:
        remain = [p for p in DRAFTS.glob(f"{pid}_*.json") if not p.name.endswith(f"_{iid}.json")]
        if not remain:
            raise SystemExit(f"place {pid}: item {iid} 삭제 시 place가 빔 — 중단")

    print("== 1) 행 이동(삭제 전 복사) ==")
    for src, menu, dst in ROW_COPIES:
        _, ds = load_item(src)
        pdst, dd = load_item(dst)
        row = next((r for r in ds["rows"] if r.get("menu", "").strip() == menu), None)
        already = any(r.get("menu", "").strip() == menu for r in dd["rows"])
        if row is None:
            state = "원본 없음!"
        elif already:
            state = "이미 있음(스킵)"
        else:
            state = f"복사 예정 (가격 {row.get('price')}, 번역 포함)"
        print(f"  {src} '{menu}' -> {dst} : {state}")
        if args.apply and row and not already:
            dd["rows"].append(dict(row))
            save_item(pdst, dd)

    print("== 2) 페이지(item) 삭제 ==")
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    removed_dir = ROOT / "storage" / f"drafts_removed_{stamp}"
    for pid, iid, why in ITEM_DELETES:
        r = dup_ratio(pid, iid)
        path, d = load_item(iid)
        print(f"  {pid}/{iid} ({len(d['rows'])}행) — {why} · 잔여 item과 중복률 {r:.0%}")
        if args.apply:
            removed_dir.mkdir(exist_ok=True)
            shutil.move(str(path), str(removed_dir / path.name))

    print("== 3) 메뉴 행 삭제(정확일치) ==")
    for pid, iid, menu, why in ROW_DELETES:
        path, d = load_item(iid)
        hits = [r for r in d["rows"] if r.get("menu", "").strip() == menu]
        print(f"  {pid}/{iid} '{menu}' — {why} : {len(hits)}행 매칭")
        if args.apply and hits:
            d["rows"] = [r for r in d["rows"] if r.get("menu", "").strip() != menu]
            save_item(path, d)

    print("== 4) 가격 기재 ==")
    for pid, iid, menu, price, why in PRICE_SETS:
        path, d = load_item(iid)
        row = next((r for r in d["rows"] if r.get("menu", "").strip() == menu), None)
        cur = row.get("price", "") if row else None
        print(f"  {pid}/{iid} '{menu}' {cur!r} -> {price!r} — {why}" + ("" if row else " · 행 없음!"))
        if args.apply and row:
            row["price"] = price
            save_item(path, d)

    print("== 5) 수동 확인 필요(자동 제외) ==")
    for n in MANUAL_NOTES:
        print(f"  - {n}")

    if args.apply:
        print(f"\n적용 완료. 삭제 item은 {removed_dir.name}/ 로 이동.")
    else:
        print("\n드라이런. 적용: --apply (적용 시 drafts 전체 백업 후 실행)")


if __name__ == "__main__":
    import sys
    if "--apply" in sys.argv:
        _stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copytree(DRAFTS, ROOT / "storage" / f"drafts_backup_{_stamp}")
        print(f"백업 완료: drafts_backup_{_stamp}/")
    main()
