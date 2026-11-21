import copy
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from vas2font.charsets import get_character_set
from vas2font.template import build_template


@pytest.fixture
def notebook() -> dict:
    return json.loads(
        Path("samples/representative-100-v1/notebook.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def template_record():
    character_set = get_character_set("representative-100", 1)
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=None,
        name=character_set.identifier,
        version=1,
        manifest=build_template(character_set).to_manifest(),
        built_in=True,
        layout_version="1",
        reference_font_version="noto-sans-sc-1",
    )


@pytest.fixture
def make_upload(notebook, template_record):
    def create(position=1, source=None, filename="notebook.json"):
        return SimpleNamespace(
            id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            template_id=template_record.id,
            template=template_record,
            position=position,
            notebook=copy.deepcopy(source if source is not None else notebook),
            original_filename=filename,
        )

    return create
