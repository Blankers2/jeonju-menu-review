import io
import zipfile

import openpyxl
from fastapi.testclient import TestClient

from app.server import server
from app import draft_store


def _make_xlsx(item_id):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["code", "Item Id", "Item Org Id", "Org Content", "Image Url",
               "11_Chinese (Simplified)(中文(简体))", "12_Chinese (Traditional)(中文(繁體))",
               "17_English(English)", "30_Japanese(日本語)"])
    ws.append(["0", item_id, "1", "갈비", f"https://img/{item_id}.png", "排骨", "排骨", "Galbi", "カルビ"])
    ws.append(["0", item_id, "2", "12,000원", "", "", "", "", ""])
    b = io.BytesIO(); wb.save(b); return b.getvalue()


def test_upload_zip_with_folders_and_gsheet(tmp_path, monkeypatch):
    monkeypatch.setattr(draft_store, "DRAFTS_DIR", tmp_path)
    c = TestClient(server)
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        z.writestr("Translation/13764_전주성갈비/place_13764_image_111225_x.xlsx", _make_xlsx("111225"))
        z.writestr("Translation/13763_명품장어/place_13763_image_111227_y.xlsx", _make_xlsx("111227"))
        z.writestr("Translation/13763_명품장어/x_999.gsheet", '{"doc_id":"abc"}')
    r = c.post("/api/upload_translations",
               files=[("files", ("Translation.zip", zb.getvalue(), "application/zip"))],
               data={"paths": ["Translation.zip"]})
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2 and body["skipped_gsheet"] == 1

    d = c.get("/api/images/111225").json()
    assert d["place_id"] == 13764 and d["title"] == "전주성갈비"
    assert d["image_url"] == "https://img/111225.png"
    assert any(row["menu"] == "갈비" and row["en"] == "Galbi" for row in d["rows"])
    assert any(p["number"] == "12,000" for p in d["prices"])
