"""동료 분담용 슬림 핸드오프 zip 생성기.

사용:
  python tools/make_handoff.py                # 미검수 후반 50%를 동료 배정
  python tools/make_handoff.py --frac 0.6     # 동료에게 60% 배정
  python tools/make_handoff.py --out 경로.zip

포함: app/ (코드), storage/drafts/<배정분>.json, storage/handoff_manifest.json,
      requirements.txt, 동료_시작.bat, 동료_작업안내.txt
제외: storage/auto, .git, data, venv, __pycache__, docs (이미지는 URL 로드라 불필요)
배정은 미검수(reviewed=False) item을 사이드바 순(place_id,item_id)으로 정렬한 뒤 후반 N개.
이미 검수완료된 item은 패키지에서 제외(동료가 다시 안 보게).
"""
import argparse
import datetime as dt
import glob
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "storage" / "drafts"

START_BAT = """@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Menu Finder (동료 검수용)
echo   최초 1회 의존성 설치 후 서버가 켜집니다.
echo ============================================
echo.
echo [1/2] 의존성 설치 중... (최초 1회, 인터넷 필요)
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo [오류] Python 이 설치되어 있지 않거나 pip 설치에 실패했습니다.
  echo Python 3.10 이상을 https://www.python.org/downloads/ 에서 설치 후
  echo 설치 시 "Add python.exe to PATH" 를 체크하세요. 그런 다음 이 파일을 다시 실행하세요.
  pause
  exit /b 1
)
echo [2/2] 서버 시작 — 브라우저에서 http://127.0.0.1:8000
start "" http://127.0.0.1:8000
python -m uvicorn app.server:server --host 127.0.0.1 --port 8000
pause
"""

GUIDE = """[ 메뉴 검수 작업 안내 ]

준비물: Windows PC + Python 3.10 이상
  - Python 이 없으면 https://www.python.org/downloads/ 에서 설치
  - 설치 화면에서 "Add python.exe to PATH" 반드시 체크

작업 순서
  1) 받은 압축파일을 폴더에 풉니다.
  2) 폴더 안의 [동료_시작.bat] 더블클릭
     - 최초 1회는 의존성 설치로 시간이 걸립니다(인터넷 필요).
     - 자동으로 브라우저에 http://127.0.0.1:8000 가 열립니다.
  3) 왼쪽 목록에 보이는 가게(item)들만 검수합니다. (당신에게 배정된 분량만 보입니다)
     - 가운데 메뉴판 이미지를 보고, 오른쪽 표의 메뉴명/가격이 맞는지 확인·수정합니다.
     - 가격은 숫자만 입력합니다.
     - ★ 영어/일본어/중국어 번역 칸은 절대 수정하지 마세요(기본 잠금).
     - 한 가게를 끝내면 [검수완료 토글] 버튼을 누릅니다. (자동 저장됩니다)
  4) 모두 끝나면 검은 서버 창을 닫습니다.
  5) ★ 압축을 풀었던 "폴더 전체"를 다시 압축해서 회신합니다.
     (폴더 안 storage/drafts 에 작업 내용이 저장되어 있습니다)

주의
  - 목록에 없는 가게는 건드릴 수 없습니다(정상). 배정분만 하시면 됩니다.
  - 인터넷이 연결되어 있어야 메뉴판 이미지가 보입니다.
"""


def load_unreviewed_sorted():
    items = []
    for f in glob.glob(str(DRAFTS / "*.json")):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        if not d.get("reviewed"):
            items.append(d)
    items.sort(key=lambda d: (d.get("place_id") or 0, int(d["item_id"])))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frac", type=float, default=0.5, help="동료 배정 비율(후반)")
    ap.add_argument("--out", default=str(ROOT / "menu-finder-동료.zip"))
    args = ap.parse_args()

    un = load_unreviewed_sorted()
    n_col = round(len(un) * args.frac)
    assigned = un[len(un) - n_col:]
    assigned_ids = [d["item_id"] for d in assigned]

    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    manifest = {"created": stamp, "owner": "colleague",
                "assigned": assigned_ids, "count": len(assigned_ids)}

    build = ROOT / "storage" / "_handoff_build"
    if build.exists():
        shutil.rmtree(build)
    (build / "app").mkdir(parents=True)
    (build / "storage" / "drafts").mkdir(parents=True)

    # 앱 코드 (pycache 제외)
    shutil.copytree(ROOT / "app", build / "app", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # 배정분 drafts 만
    for iid in assigned_ids:
        shutil.copy(DRAFTS / f"{iid}.json", build / "storage" / "drafts" / f"{iid}.json")
    # manifest / requirements / bat / guide
    (build / "storage" / "handoff_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy(ROOT / "requirements.txt", build / "requirements.txt")
    (build / "동료_시작.bat").write_text(START_BAT, encoding="utf-8")
    (build / "동료_작업안내.txt").write_text(GUIDE, encoding="utf-8")

    out = Path(args.out)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in build.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(build))
    shutil.rmtree(build)

    size_mb = out.stat().st_size / 1e6
    print(f"created: {out}  ({size_mb:.1f} MB)")
    print(f"미검수 총 {len(un)} → 동료 배정 {len(assigned_ids)}개 / 내 몫 {len(un)-len(assigned_ids)}개")
    print(f"배정 item_id(앞 10): {assigned_ids[:10]}")


if __name__ == "__main__":
    main()
