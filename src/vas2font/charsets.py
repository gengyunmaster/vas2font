from dataclasses import dataclass


@dataclass(frozen=True)
class CharacterSet:
    identifier: str
    version: int
    characters: tuple[str, ...]


REPRESENTATIVE_100 = (
    *tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    *tuple("abcdefghijklmnopqrstuvwxyz"),
    *tuple("0123456789"),
    *tuple(".,:;!?'\"()-_/\\"),
    *tuple("一人永木水火心之女月田国明林好江语思草意问这龙赢"),
)

CHARACTER_SETS = {
    ("representative-100", 1): CharacterSet(
        identifier="representative-100",
        version=1,
        characters=REPRESENTATIVE_100,
    )
}


def get_character_set(identifier: str, version: int) -> CharacterSet:
    try:
        return CHARACTER_SETS[(identifier, version)]
    except KeyError as error:
        raise ValueError(
            f"Unsupported character set: {identifier} version {version}"
        ) from error
