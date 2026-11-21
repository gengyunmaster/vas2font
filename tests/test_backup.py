from types import SimpleNamespace

from vas2font.api.backup_service import build_backup


def test_backup_contains_sources_but_no_access_code(make_upload, template_record):
    project = SimpleNamespace(
        font_family="Portable Font",
        font_version="2.0",
        pipeline_version="1",
    )
    upload = make_upload()
    backup = build_backup(project, [template_record], [upload])
    assert backup["project"]["font_family"] == "Portable Font"
    assert len(backup["templates"]) == 1
    assert len(backup["uploads"]) == 1
    assert "access_code" not in str(backup)
    assert "access_code_hash" not in str(backup)
