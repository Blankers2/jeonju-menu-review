"""시청 지시의 '페이지 삭제/중복' → 우리 item 삭제 후보 리포트(자동삭제 X, 확인용).

전역 페이지번호는 우리 순서와 안 맞으므로, **가게별 상대순서**로 매핑:
  그 가게의 페이지범위 시작(start)을 기준으로 page-start = 우리 이미지(item) 인덱스.
범위 밖(다른 가게 페이지 참조)·모호 케이스는 '수동확인'으로 표시.
메뉴 행(row) 삭제 지시(예: '이강주 유리병 삭제')는 이미지 삭제가 아니라 편집기에서 처리 → 별도 표기.
"""
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXES = ROOT / "storage" / "city_fixes.json"
DRAFTS = ROOT / "storage" / "drafts"
OUT = ROOT / "storage" / "deletion_candidates.json"

# "129페이지", "238, 239페이지" 등 페이지 앞의 숫자(콤마 나열 포함) 캡처
_PAGE_DEL = re.compile(r"([\d,\s]+?)\s*페이지")


def main():
    fixes = json.loads(FIXES.read_text(encoding="utf-8"))
    # place_id -> 우리 item 목록(순서)
    items = defaultdict(list)
    for f in glob.glob(str(DRAFTS / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        items[d["place_id"]].append((int(d["item_id"]), d["item_id"], d.get("image_url", "")))
    for pid in items:
        items[pid].sort()

    report = []
    for pid_s, fx in fixes.items():
        pid = int(pid_s)
        comments = " / ".join(fx.get("comments", []))
        if "삭제" not in comments and "중복" not in comments:
            continue
        our = items.get(pid, [])
        pages = [int(m.group(0)) for p in fx.get("pages", []) for m in re.finditer(r"\d+", p)]
        start = min(pages) if pages else None
        # 삭제/중복 문맥의 페이지 번호 추출
        del_pages = sorted(set(int(n) for m in _PAGE_DEL.finditer(comments)
                               for n in re.findall(r"\d+", m.group(1))))
        entry = {"place_id": pid, "store": fx.get("store"), "comment": comments,
                 "store_page_start": start, "our_items": [i[1] for i in our],
                 "candidates": [], "note": ""}
        if not del_pages:
            entry["note"] = "행(메뉴) 삭제이거나 페이지 불명 → 편집기에서 수동 처리"
        else:
            for dp in del_pages:
                if start is not None and 0 <= dp - start < len(our):
                    it = our[dp - start]
                    entry["candidates"].append({"page": dp, "item_id": it[1], "image_url": it[2]})
                else:
                    entry["candidates"].append({"page": dp, "item_id": None, "note": "범위밖/교차참조 → 수동확인"})
        report.append(entry)

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"삭제/중복 지시 place: {len(report)}곳  (리포트: {OUT})\n")
    for e in report:
        print(f"■ {e['store']} (p{e['place_id']}) 이미지 {len(e['our_items'])}장 {e['our_items']}")
        print(f"   지시: {e['comment'][:90]}")
        if e["candidates"]:
            for c in e["candidates"]:
                if c.get("item_id"):
                    print(f"   → 삭제후보 item {c['item_id']} (p{c['page']})")
                else:
                    print(f"   → p{c['page']}: {c['note']}")
        else:
            print(f"   → {e['note']}")


if __name__ == "__main__":
    main()
