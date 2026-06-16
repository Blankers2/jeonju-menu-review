"""파이썬 없는 동료용 — 단독 실행 HTML 검수기 생성기.

사용:
  python tools/make_handoff_html.py                 # 미검수 후반 50% 배정
  python tools/make_handoff_html.py --frac 0.6
  python tools/make_handoff_html.py --out 파일.html

배정 item(드래프트 전체)을 tools/handoff_template.html 에 내장한 자기완결 HTML 생성.
동료는 설치 없이 더블클릭→검수, 진행은 브라우저(localStorage) 자동저장,
[내보내기]로 회신용 JSON 하나 다운로드. (인터넷은 메뉴 이미지 표시에 필요)
"""
import argparse
import datetime as dt
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"
TEMPLATE = ROOT / "tools" / "handoff_template.html"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frac", type=float, default=0.5)
    ap.add_argument("--out", default=str(ROOT / "메뉴검수_동료.html"))
    args = ap.parse_args()

    items = []
    for f in glob.glob(str(DRAFTS / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if not d.get("reviewed"):
            items.append(d)
    items.sort(key=lambda d: (d.get("place_id") or 0, int(d["item_id"])))
    n_col = round(len(items) * args.frac)
    assigned = items[len(items) - n_col:]
    # 내장 데이터는 필요한 필드만 (org_id 등 불필요 키 제거, 용량/깔끔)
    clean = [{
        "item_id": d["item_id"], "place_id": d.get("place_id"), "title": d.get("title", ""),
        "image_url": d.get("image_url", ""), "width": d.get("width"), "height": d.get("height"),
        "reviewed": False, "status": "pending",
        "rows": [{k: r.get(k, "") for k in ("menu", "price", "en", "ja", "zh_cn", "zh_tw")} for r in d.get("rows", [])],
        "prices": d.get("prices", []),
    } for d in assigned]

    manifest = {"created": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "owner": "colleague", "assigned": [d["item_id"] for d in assigned],
                "count": len(assigned)}

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("__MANIFEST__", json.dumps(manifest, ensure_ascii=False))
    html = html.replace("__DATA__", json.dumps(clean, ensure_ascii=False))
    out = Path(args.out)
    out.write_text(html, encoding="utf-8")

    print(f"created: {out}  ({out.stat().st_size/1e6:.2f} MB)")
    print(f"미검수 총 {len(items)} → 동료 배정 {len(assigned)}개 / 내 몫 {len(items)-len(assigned)}개")
    print("동료는 이 HTML 파일만 받아 더블클릭하면 됩니다(설치 불필요).")


if __name__ == "__main__":
    main()
