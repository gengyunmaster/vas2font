import pytest

from vas2font.api.errors import ApiError
from vas2font.api.template_service import normalize_characters


def test_custom_character_normalization():
    assert normalize_characters("永永 和人\n") == ("永", "和", "人")


def test_custom_character_rejection():
    with pytest.raises(ApiError) as error:
        normalize_characters("A\u0001B")
    assert error.value.code == "unsupported_characters"
