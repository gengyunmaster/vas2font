from fontTools.ttLib import TTFont

from vas2font.api.upload_service import merge_upload_glyphs
from vas2font.font import build_font


def test_font_build_includes_whitespace_metadata_and_progress(make_upload, tmp_path):
    extraction = merge_upload_glyphs([make_upload()])
    stages = []
    output = tmp_path / "font.otf"
    build_font(
        extraction,
        output,
        "Regression Font",
        font_version="2.5",
        progress_callback=lambda stage, progress: stages.append((stage, progress)),
    )
    with TTFont(output) as font:
        assert font["name"].getDebugName(1) == "Regression Font"
        assert font["name"].getDebugName(5) == "Version 2.5"
        assert len(font.getBestCmap()) == 102
        assert 0x20 in font.getBestCmap() and 0xA0 in font.getBestCmap()
    assert stages[0] == ("Outlining handwriting", 15)
    assert stages[-1] == ("Font ready", 100)
    assert any(stage == "Writing OpenType tables" for stage, _ in stages)
