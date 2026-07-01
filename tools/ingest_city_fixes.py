"""전주시청 수정지시 엑셀 -> storage/city_fixes.json (place_id별 코멘트/페이지/유형).

사용: python tools/ingest_city_fixes.py [--xlsx 경로]
- 업소명 → 우리 place_id 매칭(퍼지 + 오타 오버라이드). 미매칭·범위밖 리포트.
- 페이지번호는 원문 그대로 보관(전역 정합 안 됨 → 삭제 특정은 가게 상대순서로 별도 처리).
"""
import argparse
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl
from rapidfuzz import process, fuzz

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"
OUT = ROOT / "storage" / "city_fixes.json"
DEFAULT_XLSX = Path.home() / "Downloads" / "메뉴판 수정(26.6.23).xlsx"

# 업소명 오타/약칭 → 우리 place_id 수동 오버라이드
OVERRIDE = {
    "호순이김자탕": 13208, "만석꾼": 13387, "풍남문한오촌": 13429,
    "아중천민물장어": 13238,
    "메기짐": 13261,  # 섬진강 (item 103984) — 사용자 확인
}


def classify(t: str):
    t = str(t or ""); b = []
    if "카테고리" in t or "분류" in t or "구분" in t or "타이틀" in t: b.append("카테고리분류")
    if "가격" in t or "변동" in t or "싯가" in t or "시가" in t: b.append("가격확인/변동")
    if "추가" in t or "누락" in t or "기재" in t: b.append("추가/세부기재")
    if "표시" in t or "포함" in t or "기준" in t or "구분 기재" in t: b.append("주석/표시")
    if "맵기" in t or "매운" in t: b.append("맵기표기")
    if "삭제" in t or "중복" in t: b.append("삭제/중복")
    if "순서" in t: b.append("순서변경")
    if "QR" in t: b.append("범위밖:QR")
    if "네이버" in t: b.append("범위밖:외부데이터")
    return b or ["기타/모호"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(DEFAULT_XLSX))
    args = ap.parse_args()

    # place 타이틀 사전(고유)
    pid_by_title = {}
    for f in glob.glob(str(DRAFTS / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        pid_by_title.setdefault(d.get("title", ""), d.get("place_id"))
    titles = [t for t in pid_by_title if t]

    ws = openpyxl.load_workbook(args.xlsx, read_only=True, data_only=True).active
    rows = [r for r in ws.iter_rows(values_only=True)][2:]

    fixes = defaultdict(lambda: {"store": "", "place_id": None, "comments": [], "pages": [], "types": [], "memo": []})
    unmatched, out_of_scope = [], []
    for r in rows:
        if not r or not r[0]:
            continue
        name = str(r[0]).strip()
        instr = str(r[1]).strip() if r[1] else ""
        page = str(r[2]).strip() if len(r) > 2 and r[2] is not None else ""
        memo = str(r[3]).strip() if len(r) > 3 and r[3] else ""
        types = classify(instr + " " + memo)

        if name in OVERRIDE:
            pid = OVERRIDE[name]
        else:
            m = process.extractOne(name, titles, scorer=fuzz.WRatio)
            pid = pid_by_title[m[0]] if m and m[1] >= 88 else None
        if pid is None:
            unmatched.append((name, page, instr[:40]))
            continue
        if any(t.startswith("범위밖") for t in types):
            out_of_scope.append((name, [t for t in types if t.startswith("범위밖")], instr[:50]))

        e = fixes[pid]
        e["store"] = name; e["place_id"] = pid
        e["comments"].append(instr)
        if page: e["pages"].append(page)
        e["types"] = sorted(set(e["types"]) | set(types))
        if memo: e["memo"].append(memo)

    OUT.write_text(json.dumps(fixes, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"city_fixes.json 저장: place {len(fixes)}곳 (총 지시행 {sum(len(v['comments']) for v in fixes.values())})")
    print(f"\n[미매칭 {len(unmatched)}건 — 확인 필요]")
    for n, p, i in unmatched:
        print(f"   '{n}' (p{p}) : {i}")
    print(f"\n[범위 밖 {len(out_of_scope)}건]")
    for n, t, i in out_of_scope:
        print(f"   {n} {t}: {i}")


if __name__ == "__main__":
    main()
