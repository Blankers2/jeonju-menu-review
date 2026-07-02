"""드래프트 최종 정리: 파일명 placeid_itemid.json, 삭제업소 백업 이동, 시트1 타이틀 적용.

- 삭제 place(시트1 131업소에 없음): 13273, 13408, 13426, 13428 → storage/drafts_removed_<stamp>/ 로 이동.
- 나머지(131 place)는 title=시트1 기준으로 세팅, 파일명 <place_id>_<item_id>.json 으로 변경.
- 실행 전 storage/drafts 전체 백업.
사용: python tools/rename_and_prune.py --apply   (미지정 시 드라이런)
"""
import argparse
import datetime as dt
import glob
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"
sys.path.insert(0, str(ROOT / "tools"))
from apply_titles import TITLES  # 133 authoritative titles

DELETE_PLACES = {13273, 13408, 13426, 13428}  # 시트1(131)에 없는 업소


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    files = sorted(glob.glob(str(DRAFTS / "*.json")))
    keep, remove = [], []
    for f in files:
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        (remove if d.get("place_id") in DELETE_PLACES else keep).append((Path(f), d))

    keep_places = {d["place_id"] for _, d in keep}
    missing_title = sorted(p for p in keep_places if p not in TITLES)
    print(f"드라이런? {not args.apply}")
    print(f"유지: item {len(keep)} / place {len(keep_places)}")
    print(f"삭제(이동): item {len(remove)} → {sorted({d['place_id'] for _,d in remove})}")
    for p, d in remove:
        print(f"    - {d['place_id']} {d.get('title')} item {d['item_id']}")
    if missing_title:
        print(f"⚠ 시트1 타이틀 없는 유지 place: {missing_title} (확인 필요)")

    if not args.apply:
        print("\n드라이런. 적용하려면 --apply")
        return

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ROOT / "storage" / f"drafts_backup_{stamp}"
    shutil.copytree(DRAFTS, backup)
    removed_dir = ROOT / "storage" / f"drafts_removed_{stamp}"
    removed_dir.mkdir(parents=True, exist_ok=True)

    for p, d in remove:
        shutil.move(str(p), str(removed_dir / p.name))
    renamed = 0
    for p, d in keep:
        pid = d["place_id"]; iid = str(d["item_id"])
        if pid in TITLES:
            d["title"] = TITLES[pid]
        new = DRAFTS / f"{pid}_{iid}.json"
        new.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        if p.resolve() != new.resolve():
            p.unlink()
        renamed += 1
    print(f"\n백업: {backup}")
    print(f"삭제 이동: {len(remove)} → {removed_dir}")
    print(f"유지·리네임: {renamed}  (파일명 placeid_itemid.json, 시트1 타이틀 적용)")
    print(f"최종 drafts 파일수: {len(list(DRAFTS.glob('*.json')))}")


if __name__ == "__main__":
    main()
