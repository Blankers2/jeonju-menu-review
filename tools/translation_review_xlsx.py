"""괄호 부가어 번역 검토용 xlsx 생성(자동수정 X). 사람이 확인·반영하도록.

시트: 채우기후보(현재→제안, per-item 조각 기반) / 미해결부가어(조각없음, 빈도) / 용량부분누락
출력: 번역검토_부가어.xlsx (프로젝트 루트)
"""
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"
sys.path.insert(0, str(ROOT / "tools"))
from fragment_dict import load as load_frag

LANGS = ("en", "ja", "zh_cn", "zh_tw")
_PAREN = re.compile(r"[\(（]([^)）]+)[\)）]")
_CAP_ONLY = re.compile(r"^\s*\d+(?:\.\d+)?\s*(?:公斤|千克|公升|毫升|克|升|kg|g|ml|l|ℓ|cc)\s*$", re.IGNORECASE)
_CAP = re.compile(r"(\d+(?:\.\d+)?)\s*(公斤|千克|公升|毫升|克|升|kg|g|ml|l|ℓ|cc)(?![A-Za-z])", re.IGNORECASE)
_UNIT = {"kg": "kg", "g": "g", "ml": "ml", "l": "l", "ℓ": "l", "cc": "ml", "克": "g",
         "公斤": "kg", "千克": "kg", "毫升": "ml", "升": "l", "公升": "l"}


def caps(s):
    return {f"{m.group(1)}{_UNIT.get(m.group(2).lower(), m.group(2).lower())}" for m in _CAP.finditer(s or "")}


def main():
    by_item, gd = load_frag()
    fill, unresolved, cap_partial = [], Counter(), []
    for f in sorted(glob.glob(str(DRAFTS / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        idict = {}
        for fr in by_item.get(str(d.get("item_id")), []):
            ko = (fr.get("ko") or "").strip()
            if ko:
                idict.setdefault(ko, {l: (fr.get(l) or "").strip() for l in LANGS})
        for r in d.get("rows", []):
            menu = r.get("menu") or ""
            for c in [x.strip() for x in _PAREN.findall(menu)]:
                if not c or _CAP_ONLY.match(c):
                    continue
                tr = idict.get(c)
                if not tr or not any(tr[l] for l in LANGS):
                    unresolved[c] += 1
                    continue
                row = [d["place_id"], d["item_id"], menu, c]
                for l in LANGS:
                    cur = r.get(l) or ""
                    prop = f"{cur} ({tr[l]})".strip() if tr[l] and tr[l] not in cur and cur not in tr[l] else cur
                    row += [cur, prop]
                fill.append(row)
            # 용량 부분누락(일부 언어만)
            cm = caps(menu)
            if cm:
                per = {l: caps(r.get(l) or "") for l in LANGS}
                pres = [l for l in LANGS if (r.get(l) or "") and cm <= per[l]]
                miss = [l for l in LANGS if (r.get(l) or "") and not cm <= per[l]]
                if pres and miss:
                    cap_partial.append([d["place_id"], d["item_id"], menu, ",".join(sorted(cm)),
                                        ",".join(pres), ",".join(miss)])

    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "채우기후보"
    ws.append(["place_id", "item_id", "메뉴명", "부가어",
               "en_현재", "en_제안", "ja_현재", "ja_제안",
               "zh_cn_현재", "zh_cn_제안", "zh_tw_현재", "zh_tw_제안"])
    for row in fill:
        ws.append(row)
    ws2 = wb.create_sheet("미해결부가어")
    ws2.append(["부가어", "건수", "(조각없음 → 번역팀/수동)"])
    for c, n in unresolved.most_common():
        ws2.append([c, n])
    ws3 = wb.create_sheet("용량부분누락")
    ws3.append(["place_id", "item_id", "메뉴명", "용량", "반영언어", "누락언어"])
    for row in cap_partial:
        ws3.append(row)

    out = ROOT / "번역검토_부가어.xlsx"
    wb.save(out)
    print(f"저장: {out}")
    print(f" 채우기후보 {len(fill)}행 / 미해결부가어 {len(unresolved)}종 / 용량부분누락 {len(cap_partial)}건")


if __name__ == "__main__":
    main()
