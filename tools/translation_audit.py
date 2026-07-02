"""번역 재조합 검수 (드라이런) — 메모리 규칙 기반, 자동수정 없이 리포트만.

점검:
 1) 용량표기(100g/375ml 등):
    - 원문 메뉴명에만 있음 → 정상(무보고)
    - 번역에만 있음 → 보고(원문+번역 둘다 필요)
    - 일부 언어에만 있음/불일치 → '기타 용량 케이스'로 보고(사용자 기준 필요)
 2) 괄호 부가정보: 메뉴명에 (…)가 있는데 특정 언어 번역엔 괄호가 없음 → 번역 누락 의심
 3) 가격 '싯가'/'-' 는 오류 아님 → 제외
번역은 임의생성 금지. 여기선 '탐지·보고'만 하고, 실제 보정은 조각사전으로 승인 후 별도 적용.
사용: python tools/translation_audit.py
"""
import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"
OUT = ROOT / "storage" / "translation_audit.json"
LANGS = ("en", "ja", "zh_cn", "zh_tw")

# 용량 단위: 로마자 + 중국어(克=g, 公斤/千克=kg, 毫升=ml, 升=l) + 일본어 그램 표기.
# 뒤에 로마자가 오면 단위 아님. 중국어 단위는 정규화해 "200g"=="200克" 로 동일 취급.
_UNIT = {"kg": "kg", "g": "g", "ml": "ml", "l": "l", "ℓ": "l", "cc": "ml",
         "克": "g", "公斤": "kg", "千克": "kg", "毫升": "ml", "升": "l", "公升": "l"}
_CAP = re.compile(r"(\d+(?:\.\d+)?)\s*(公斤|千克|公升|毫升|克|升|kg|g|ml|l|ℓ|cc)(?![A-Za-z])", re.IGNORECASE)
_PAREN = re.compile(r"[\(（][^)）]+[\)）]")
_CAP_ONLY_UNIT = r"(?:公斤|千克|公升|毫升|克|升|kg|g|ml|l|ℓ|cc)"
_PAREN_CAP_ONLY = re.compile(rf"^[\(（]\s*\d+(?:\.\d+)?\s*{_CAP_ONLY_UNIT}\s*[\)）]$", re.IGNORECASE)


def caps(s):
    out = set()
    for m in _CAP.finditer(s or ""):
        out.add(f"{m.group(1)}{_UNIT.get(m.group(2).lower(), m.group(2).lower())}")
    return out


def main():
    cap_tr_only, cap_other, paren_missing = [], [], []
    total_rows = 0
    for f in glob.glob(str(DRAFTS / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for r in d.get("rows", []):
            menu = r.get("menu", "") or ""
            if not menu.strip():
                continue
            total_rows += 1
            tr = {l: (r.get(l) or "") for l in LANGS}
            # --- 용량표기 ---
            cm = caps(menu)
            per_lang = {l: caps(tr[l]) for l in LANGS}
            union_tr = set().union(*per_lang.values()) if per_lang else set()
            ref = {"place_id": d["place_id"], "item_id": d["item_id"],
                   "menu": menu, "en": tr["en"]}
            # ② 번역에만 있는 용량(원문엔 없음) → 원문+번역 둘다 필요. 단 '100g'는 per-100g 단가표기 흔해 제외.
            extra = {c for c in (union_tr - cm) if c != "100g"}
            if extra:
                cap_tr_only.append({**ref, "번역전용용량": sorted(extra), "원문용량": sorted(cm)})
            elif cm:
                present = [l for l in LANGS if tr[l] and cm <= per_lang[l]]
                missing = [l for l in LANGS if tr[l] and not (cm <= per_lang[l])]
                # ③ 일부 언어만 용량 반영(전 언어 누락=원문only=정상이라 제외)
                if present and missing:
                    cap_other.append({**ref, "원문용량": sorted(cm), "반영언어": present, "누락언어": missing})
            # --- 비-용량 괄호 부가어(코스/옵션 등)가 번역에 없음 ---
            pm = _PAREN.findall(menu)
            non_cap_paren = [p for p in pm if not _PAREN_CAP_ONLY.match(p)]
            if non_cap_paren:
                nop = [l for l in LANGS if tr[l] and not _PAREN.search(tr[l])]
                if nop:
                    paren_missing.append({**ref, "부가어": non_cap_paren, "괄호없는언어": nop})

    report = {"total_rows": total_rows,
              "capacity_translation_only": cap_tr_only,
              "capacity_partial_or_other": cap_other,
              "paren_missing": paren_missing}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"검사 행: {total_rows}")
    print(f"[1a] 번역에만 용량표기(원문에 추가 필요): {len(cap_tr_only)}")
    for x in cap_tr_only[:8]:
        print(f"    p{x['place_id']}/{x['item_id']} '{x['menu']}' 번역전용{x['번역전용용량']} en='{x['en'][:40]}'")
    print(f"[1b] 원문 용량이 일부 언어만 반영(기타→기준 필요): {len(cap_other)}")
    for x in cap_other[:8]:
        print(f"    p{x['place_id']}/{x['item_id']} '{x['menu']}' 용량{x['원문용량']} 반영{x['반영언어']}/누락{x['누락언어']}")
    print(f"[2] 메뉴명 괄호(…)가 번역에 없음(누락 의심): {len(paren_missing)}")
    for x in paren_missing[:8]:
        print(f"    p{x['place_id']}/{x['item_id']} '{x['menu']}' 괄호없음{x['괄호없는언어']} en='{x['en'][:40]}'")
    print(f"\n리포트: {OUT} (자동수정 없음)")


if __name__ == "__main__":
    main()
