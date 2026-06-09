import re

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
