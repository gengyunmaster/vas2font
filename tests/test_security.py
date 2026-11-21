from vas2font.api.security import (
    access_code_hash,
    generate_access_code,
    normalize_access_code,
)


def test_access_code_is_high_entropy_and_hashed():
    first = generate_access_code()
    second = generate_access_code()
    assert first != second
    assert len(normalize_access_code(first)) == 26
    digest = access_code_hash(first)
    assert len(digest) == 64
    assert first.replace("-", "").lower() not in digest
