from vas2font.charsets import CHARACTER_SETS
from vas2font.reference import has_reference_glyph
from vas2font.template import build_template


def test_builtin_character_set_coverage():
    expected = {
        "representative-100": 100,
        "latin-letters": 52,
        "digits": 10,
        "ascii-punctuation": 32,
        "gb2312-han": 6763,
        "gb2312-ascii": 7538,
    }
    assert {
        key[0]: len(value.characters) for key, value in CHARACTER_SETS.items()
    } == expected
    for character_set in CHARACTER_SETS.values():
        assert len(character_set.characters) == len(set(character_set.characters))


def test_gb2312_fallback_characters_are_supported():
    assert has_reference_glyph("・")
    assert has_reference_glyph("―")


def test_large_template_pagination():
    template = build_template(CHARACTER_SETS[("gb2312-han", 1)])
    assert len(template.pages) == 131
    assert sum(len(page.cells) for page in template.pages) == 6763
    assert all(cell.grid == "rice" for page in template.pages for cell in page.cells)
