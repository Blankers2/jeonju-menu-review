from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from PIL import Image


class OcrEngine(ABC):
    @abstractmethod
    def read(self, image_path: Path) -> list[dict]:
        """이미지 1장 → OcrBox 리스트.
        OcrBox = {text, bbox:[x,y,w,h], confidence, polygon:[[x,y]*4]}"""
        ...


def _poly_to_bbox(poly):
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    x, y = min(xs), min(ys)
    return [int(x), int(y), int(max(xs) - x), int(max(ys) - y)]


class PaddleOcrEngine(OcrEngine):
    """PaddleOCR 3.x compatible OCR engine.

    PaddleOCR 3.x API changes vs 2.x:
    - Constructor no longer accepts `use_angle_cls` or `show_log`; use
      `use_textline_orientation` and (no equivalent for show_log).
    - `.ocr()` is deprecated; use `.predict()` instead.
    - `.predict()` returns a list of result objects (one per image page),
      each is a dict-like object with keys:
        rec_polys  – list of polygons, each [[x,y], [x,y], [x,y], [x,y]]
        rec_texts  – list of text strings
        rec_scores – list of float confidence scores

    Windows/oneDNN workaround:
    - paddlepaddle 3.3 + oneDNN on Windows raises
      ``NotImplementedError: ConvertPirAttribute2RuntimeAttribute not support
      [pir::ArrayAttribute<pir::DoubleAttribute>]`` when the new PIR executor
      runs with MKLDNN enabled.  Setting PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=False
      forces plain-paddle run_mode (no MKLDNN) which avoids the crash.
      Must be set *before* paddlex flags module is imported.
    """

    def __init__(self, lang: str = "korean"):
        import os
        # Must be set before paddlex imports its flags module (which reads env at import time).
        # If already imported, also patch the live flag so it takes effect on next engine init.
        os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "False")
        try:
            import paddlex.utils.flags as _flags
            if getattr(_flags, "ENABLE_MKLDNN_BYDEFAULT", True):
                _flags.ENABLE_MKLDNN_BYDEFAULT = False
        except Exception:
            pass

        from paddleocr import PaddleOCR
        # 3.x: use_textline_orientation replaces use_angle_cls; no show_log param
        self._ocr = PaddleOCR(lang=lang, use_textline_orientation=True)

    def read(self, image_path: Path) -> list[dict]:
        # predict() returns a list of result objects (one per input image)
        results = self._ocr.predict(str(image_path))
        boxes = []
        for page in results:
            if page is None:
                continue
            rec_polys = page.get("rec_polys", [])
            rec_texts = page.get("rec_texts", [])
            rec_scores = page.get("rec_scores", [])
            for poly, text, conf in zip(rec_polys, rec_texts, rec_scores):
                poly = [[float(p[0]), float(p[1])] for p in poly]
                boxes.append({
                    "text": text,
                    "bbox": _poly_to_bbox(poly),
                    "confidence": float(conf),
                    "polygon": poly,
                })
        return boxes


def image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as im:
        return im.size
