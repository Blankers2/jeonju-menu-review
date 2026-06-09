import csv
import re

from rapidfuzz import fuzz, process

from app.config import PLACE_IDS_CSV

_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp|bmp)$", re.IGNORECASE)
_SUFFIX_RE = re.compile(r"(-crop|_merged|\(보완\))", re.IGNORECASE)
_TRAILING_NUM_RE = re.compile(r"\s*\d+$")


def normalize_store_name(filename: str) -> str:
    name = _EXT_RE.sub("", filename)
    while True:
        new = _SUFFIX_RE.sub("", name)
        if new == name:
            break
        name = new
    name = _TRAILING_NUM_RE.sub("", name)
    return name.strip()


def load_place_index(rows=None):
    """rows: [(place_id:int, title:str)]. None이면 PLACE_IDS_CSV에서 로드."""
    if rows is None:
        rows = []
        with open(PLACE_IDS_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append((int(r["place_id"]), r["title"].strip()))
    return [{"place_id": pid, "title": title} for pid, title in rows]


def match_place(store_name: str, place_index, limit: int = 5):
    """store_name과 후보 title 유사도 top-N. score 0~100.

    fuzz.ratio (plain Levenshtein ratio) 사용:
    - 정확히 일치하면 100점
    - 부분 문자열 팽창 없음 — "궁한정식" vs "궁" 같이 짧은 후보에 오버스코어 방지
    """
    choices = {i: e["title"] for i, e in enumerate(place_index)}
    results = process.extract(store_name, choices, scorer=fuzz.ratio, limit=limit)
    out = []
    for title, score, idx in results:
        e = place_index[idx]
        out.append({"place_id": e["place_id"], "title": e["title"], "score": float(score)})
    return out


AUTO_CONFIRM_SCORE = 96  # 이 이상이면 PlaceID 자동 부여
