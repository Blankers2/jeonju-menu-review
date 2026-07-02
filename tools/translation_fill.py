"""괄호 부가어 번역 반영 — 메뉴명의 (부가어)를 fragment_dict에서 찾아 번역 4종에 붙임.

임의번역 금지: 조각사전(전주시청 번역모음)에 '정확히 일치'하는 조각이 있을 때만 채움.
- 용량만 든 괄호(예: (200g))는 대상 아님(중국어는 이미 克 등으로 반영됨).
- 조각 없거나 복합((1인분 180g), S/M/L 등)은 건드리지 않고 기록.
- 이미 해당 언어에 그 번역이 들어있으면 건너뜀.
사용: python tools/translation_fill.py            # 드라이런
      python tools/translation_fill.py --apply    # 백업 후 적용
"""
import argparse
import datetime as dt
import glob
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"
sys.path.insert(0, str(ROOT / "tools"))
from fragment_dict import load as load_frag

LANGS = ("en", "ja", "zh_cn", "zh_tw")
_PAREN = re.compile(r"[\(（]([^)）]+)[\)）]")
_CAP_ONLY = re.compile(r"^\s*\d+(?:\.\d+)?\s*(?:公斤|千克|公升|毫升|克|升|kg|g|ml|l|ℓ|cc)\s*$", re.IGNORECASE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    by_item, gd = load_frag()

    def item_dict(iid):
        m = {}
        for fr in by_item.get(str(iid), []):
            ko = (fr.get("ko") or "").strip()
            if ko:
                m.setdefault(ko, {l: (fr.get(l) or "").strip() for l in LANGS})
        return m

    proposals = []      # (path, draft, [(row_idx, content, {lang:newval})])
    unresolved = Counter()
    fill_rows = 0

    for f in sorted(glob.glob(str(DRAFTS / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        idict = item_dict(d.get("item_id"))
        row_changes = []
        for i, r in enumerate(d.get("rows", [])):
            menu = r.get("menu") or ""
            contents = [c.strip() for c in _PAREN.findall(menu)]
            for c in contents:
                if not c or _CAP_ONLY.match(c):
                    continue
                tr = idict.get(c)  # 자기 아이템 시트 조각만(문맥 보존). 전역 최빈은 오역 위험이라 미사용.
                if not tr or not any(tr[l] for l in LANGS):
                    unresolved[c] += 1
                    continue
                newvals = {}
                for l in LANGS:
                    cur = r.get(l) or ""
                    frag = tr[l]
                    # 중복 방지: 번역/조각이 이미 반영돼 있으면 스킵
                    if frag and frag not in cur and cur not in frag:
                        newvals[l] = f"{cur} ({frag})".strip()
                if newvals:
                    row_changes.append((i, c, newvals))
        if row_changes:
            proposals.append((f, d, row_changes))
            fill_rows += len(set(rc[0] for rc in row_changes))

    print(f"채울 수 있는 행: {fill_rows} (item {len(proposals)})")
    print(f"조각 없어 못 채움(부가어 종류 {len(unresolved)}):")
    for c, n in unresolved.most_common(20):
        print(f"   ({c}) x{n}")
    print("\n[적용 예시]")
    shown = 0
    for f, d, changes in proposals:
        for i, c, nv in changes:
            if shown >= 8:
                break
            print(f"   {d['place_id']}/{d['item_id']} '{d['rows'][i]['menu']}' ({c}) → en: {nv.get('en','-')}")
            shown += 1
        if shown >= 8:
            break

    if not args.apply:
        print("\n드라이런. 적용: --apply")
        return

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copytree(DRAFTS, ROOT / "storage" / f"drafts_backup_{stamp}")
    changed = 0
    for f, d, changes in proposals:
        for i, c, nv in changes:
            for l, v in nv.items():
                d["rows"][i][l] = v
                changed += 1
        Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n적용 완료: {changed}개 필드 갱신. 백업: drafts_backup_{stamp}")


if __name__ == "__main__":
    main()
