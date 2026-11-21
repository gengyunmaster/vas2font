import copy

from vas2font.api.inspection_service import attach_previews, inspect_uploads
from vas2font.api.upload_service import merge_upload_glyphs


def test_priority_merge_and_duplicate_provenance(make_upload):
    first = make_upload(position=1, filename="corrections.json")
    second = make_upload(position=2, filename="base.json")
    merged = merge_upload_glyphs([second, first])
    assert len(merged.glyphs) == 100
    items, counts = inspect_uploads([second, first], status="duplicates")
    assert len(items) == 100
    assert counts == {"covered": 100, "missing": 0, "duplicates": 100}
    assert all(item.source_filename == "corrections.json" for item in items)
    assert all(item.duplicate_count == 2 for item in items)
    attach_previews(items[:5], [second, first])
    assert all(item.preview and item.preview.paths for item in items[:5])


def test_blank_high_priority_upload_does_not_override(make_upload, notebook):
    blank = copy.deepcopy(notebook)
    for page in blank["pages"]:
        page["strokes"] = []
    high = make_upload(position=1, source=blank)
    low = make_upload(position=2)
    merged = merge_upload_glyphs([high, low])
    assert len(merged.glyphs) == 100


def test_missing_search_and_warning_filters(make_upload, notebook):
    partial = copy.deepcopy(notebook)
    partial["pages"] = partial["pages"][:1]
    upload = make_upload(source=partial)
    missing, counts = inspect_uploads([upload], status="missing")
    assert len(missing) == 48
    assert counts["covered"] == 52
    search, _ = inspect_uploads([upload], search="U+6C38")
    assert len(search) == 1 and search[0].character == "永"
    warnings, _ = inspect_uploads([make_upload()], status="warnings")
    assert len(warnings) == 1
