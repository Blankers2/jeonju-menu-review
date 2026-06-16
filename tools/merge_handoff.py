"""동료가 회신한 폴더/zip/JSON을 마스터 drafts로 안전 병합.

사용:
  python tools/merge_handoff.py <회신_폴더_또는_zip_또는_json경로>   # 드라이런(미적용)
  python tools/merge_handoff.py <경로> --apply                     # 실제 병합(백업 후 적용)

회신본 형태:
  - 폴더/zip: storage/drafts/<id>.json + storage/handoff_manifest.json  (파이썬 서버 방식)
  - .json:    {manifest:{assigned,...}, drafts:[draft,...]}             (브라우저 HTML 내보내기)

규칙:
- 회신본 안의 storage/handoff_manifest.json 의 assigned 목록만 병합 대상.
- 그 item_id 의 storage/drafts/<id>.json 을 마스터로 복사.
- 적용 전 마스터 drafts 를 storage/drafts_backup_<stamp>/ 로 백업.
- 리포트: 배정 N, 회신본에 누락된 id, 회신 후 검수완료된 개수, 충돌(내가 그 사이 같은 id를
  reviewed 처리한 경우) 경고.
"""
import argparse
import datetime as dt
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"


def resolve_incoming(path: Path) -> Path:
    """폴더면 그대로, zip이면 임시폴더에 풀어서 루트 반환."""
    if path.is_dir():
        return path
    if path.suffix.lower() == ".zip":
        tmp = Path(tempfile.mkdtemp(prefix="handoff_in_"))
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        return tmp
    raise SystemExit(f"폴더 또는 .zip 경로여야 합니다: {path}")


def find_file(base: Path, name: str) -> Path | None:
    hits = list(base.rglob(name))
    return hits[0] if hits else None


def merge_records(assigned, get_draft, label, apply):
    """assigned id별로 get_draft(id)->dict|None 을 받아 병합. 공통 리포트/적용 로직."""
    missing, conflicts, ok, done_cnt = [], [], [], 0
    for iid in assigned:
        d = get_draft(iid)
        if d is None:
            missing.append(iid); continue
        if d.get("reviewed"):
            done_cnt += 1
        mine = DRAFTS / f"{iid}.json"
        if mine.exists() and json.loads(mine.read_text(encoding="utf-8")).get("reviewed"):
            conflicts.append(iid)
        ok.append((iid, d))

    print(f"=== 병합 리포트 ({'APPLY' if apply else 'DRY-RUN'}) · {label} ===")
    print(f"매니페스트 배정: {len(assigned)}개 | 회신본에서 찾음: {len(ok)}개 | 검수완료: {done_cnt}개")
    if missing:
        print(f"⚠ 누락 {len(missing)}개: {missing[:10]}{'...' if len(missing)>10 else ''}")
    if conflicts:
        print(f"⚠ 충돌(내 마스터도 이미 검수완료) {len(conflicts)}개: {conflicts} → 동료본으로 덮어씀")
    if not apply:
        print("\n드라이런입니다. 실제 적용하려면 --apply 를 붙이세요.")
        return
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ROOT / "storage" / f"drafts_backup_{stamp}"
    shutil.copytree(DRAFTS, backup)
    for iid, d in ok:
        (DRAFTS / f"{iid}.json").write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n적용 완료: {len(ok)}개 병합. 백업: {backup}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("incoming", help="동료 회신 폴더/zip/json")
    ap.add_argument("--apply", action="store_true", help="실제 병합(기본은 드라이런)")
    args = ap.parse_args()

    inc = Path(args.incoming)
    # --- 브라우저 HTML 내보내기 JSON 회신본 ---
    if inc.is_file() and inc.suffix.lower() == ".json":
        bundle = json.loads(inc.read_text(encoding="utf-8"))
        assigned = bundle.get("manifest", {}).get("assigned") or [d["item_id"] for d in bundle.get("drafts", [])]
        by_id = {str(d["item_id"]): d for d in bundle.get("drafts", [])}
        merge_records(assigned, lambda i: by_id.get(str(i)), "JSON 내보내기", args.apply)
        return

    # --- 폴더/zip 회신본 ---
    base = resolve_incoming(inc)
    man_path = find_file(base, "handoff_manifest.json")
    if not man_path:
        raise SystemExit("handoff_manifest.json 을 찾을 수 없습니다. 올바른 회신본인지 확인하세요.")
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    assigned = manifest.get("assigned", [])
    in_drafts = man_path.parent / "drafts"

    def get_draft(iid):
        src = in_drafts / f"{iid}.json"
        return json.loads(src.read_text(encoding="utf-8")) if src.exists() else None

    merge_records(assigned, get_draft, f"폴더/zip (생성 {manifest.get('created')})", args.apply)


if __name__ == "__main__":
    main()
