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
