"""번역 조각 사전 — '전주시청 번역모음'(place별 xlsx)에서 한국어조각→4언어 사전 구축.

Phase B(번역 재조합 검수)의 기반. PlaceID/ItemID 기준으로 매칭된 실제 xlsx만 사용.
사용:
  python tools/fragment_dict.py <검색어>        # 해당 한국어 조각의 번역 후보 출력
  from tools.fragment_dict import load          # (by_item, global_dict)
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # `app` 임포트용
SRC = ROOT / "전주시청 번역모음"
LANGS = ("en", "ja", "zh_cn", "zh_tw")


def load(base=SRC):
    """반환: (by_item{item_id:[frag]}, global_dict{ko: {lang: 최빈translation}})."""
    from app import ingest
    by_item = ingest.load_fragments(str(base))
    votes = defaultdict(lambda: {l: Counter() for l in LANGS})
    for lst in by_item.values():
        for fr in lst:
            ko = (fr.get("ko") or "").strip()
            if not ko:
                continue
            for l in LANGS:
                v = (fr.get(l) or "").strip()
                if v:
                    votes[ko][l][v] += 1
    global_dict = {}
    for ko, lc in votes.items():
        global_dict[ko] = {l: (lc[l].most_common(1)[0][0] if lc[l] else "") for l in LANGS}
    return by_item, global_dict


def main():
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    by_item, gd = load()
    print(f"item {len(by_item)} · 고유 한국어조각 {len(gd)}")
    if not q:
        return
    if q in gd:
        print(f"\n[정확일치] '{q}':")
        for l in LANGS:
            print(f"   {l}: {gd[q][l]}")
    else:
        hits = [ko for ko in gd if q in ko][:15]
        print(f"\n[부분일치 {len(hits)}건]")
        for ko in hits:
            print(f"   {ko}  →  en:{gd[ko]['en']} | ja:{gd[ko]['ja']}")


if __name__ == "__main__":
    main()
