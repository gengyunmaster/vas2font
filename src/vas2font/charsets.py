import string
from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterSet:
    identifier: str
    version: int
    characters: tuple[str, ...]


def decode_gb2312() -> tuple[str, ...]:
    characters = []
    for lead in range(0xA1, 0xF8):
        for trail in range(0xA1, 0xFF):
            try:
                character = bytes((lead, trail)).decode("gb2312")
            except UnicodeDecodeError:
                continue
            if not character.isspace():
                characters.append(character)
    return tuple(characters)


REPRESENTATIVE_100 = (
    *tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    *tuple("abcdefghijklmnopqrstuvwxyz"),
    *tuple("0123456789"),
    *tuple(".,:;!?'\"()-_/\\"),
    *tuple("一人永木水火心之女月田国明林好江语思草意问这龙赢"),
)
LATIN_LETTERS = (*tuple(string.ascii_uppercase), *tuple(string.ascii_lowercase))
DIGITS = tuple(string.digits)
ASCII_PUNCTUATION = tuple(string.punctuation)
ASCII_PRINTABLE = tuple(chr(codepoint) for codepoint in range(0x21, 0x7F))
GB2312_ASSIGNED = decode_gb2312()
GB2312_HAN = tuple(
    character for character in GB2312_ASSIGNED if "\u4e00" <= character <= "\u9fff"
)
GB2312_ASCII = (*ASCII_PRINTABLE, *GB2312_ASSIGNED)

CHARACTER_SETS = {
    ("representative-100", 1): CharacterSet(
        identifier="representative-100",
        version=1,
        characters=REPRESENTATIVE_100,
    ),
    ("latin-letters", 1): CharacterSet(
        identifier="latin-letters",
        version=1,
        characters=LATIN_LETTERS,
    ),
    ("digits", 1): CharacterSet(
        identifier="digits",
        version=1,
        characters=DIGITS,
    ),
    ("ascii-punctuation", 1): CharacterSet(
        identifier="ascii-punctuation",
        version=1,
        characters=ASCII_PUNCTUATION,
    ),
    ("gb2312-han", 1): CharacterSet(
        identifier="gb2312-han",
        version=1,
        characters=GB2312_HAN,
    ),
    ("gb2312-ascii", 1): CharacterSet(
        identifier="gb2312-ascii",
        version=1,
        characters=GB2312_ASCII,
    ),
}


def get_character_set(identifier: str, version: int) -> CharacterSet:
    try:
        return CHARACTER_SETS[(identifier, version)]
    except KeyError as error:
        raise ValueError(
            f"Unsupported character set: {identifier} version {version}"
        ) from error
