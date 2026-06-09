from app.store_resolver import normalize_store_name


def test_strips_extension_crop_and_trailing_number():
    assert normalize_store_name("명품장어-crop.png") == "명품장어"
    assert normalize_store_name("궁한정식18-crop.png") == "궁한정식"
    assert normalize_store_name("늘채움5-crop.png") == "늘채움"

def test_strips_merged_and_bowan_suffix():
    assert normalize_store_name("소담촌1_merged.png") == "소담촌"
    assert normalize_store_name("소통한우2(보완)-crop.png") == "소통한우"

def test_strips_space_before_number():
    assert normalize_store_name("가족회관 1-crop.png") == "가족회관"

def test_plain_name():
    assert normalize_store_name("감로헌1.jpg") == "감로헌"
    assert normalize_store_name("자금성.png") == "자금성"


from app.store_resolver import load_place_index, match_place


def _index():
    return load_place_index([
        (13763, "명품장어"),
        (13269, "한가람"),
        (13198, "한가람금암점"),
        (13194, "궁"),
        (13220, "늘채움"),
    ])


def test_exact_match_returns_top_candidate_with_high_score():
    cands = match_place("명품장어", _index())
    assert cands[0]["place_id"] == 13763
    assert cands[0]["score"] >= 99

def test_ambiguous_name_returns_ranked_candidates():
    cands = match_place("한가람", _index())
    ids = [c["place_id"] for c in cands[:2]]
    assert 13269 in ids and 13198 in ids
    assert cands[0]["place_id"] == 13269

def test_no_good_match_flags_low_confidence():
    cands = match_place("궁한정식", _index())
    assert cands[0]["score"] < 90
