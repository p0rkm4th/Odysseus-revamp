from pathlib import Path

import pytest
from fastapi import HTTPException

from routes.research.research_routes import _extract_research_attachment_evidence


class _UploadHandler:
    def __init__(self, path, *, owner="alice"):
        self.path = str(path)
        self.owner = owner

    def validate_upload_id(self, value):
        return value == "upload-1"

    def resolve_upload(self, value, *, owner, auth_manager=None, allow_admin=False):
        if value != "upload-1" or owner != self.owner:
            return None
        return {"path": self.path, "name": "seed.txt", "mime": "text/plain"}

    def _inside_upload_dir(self, value):
        return value == self.path

    def is_image_file(self, _name, _mime):
        return False

    def is_document_file(self, _name, mime):
        return mime.startswith("text/")


def test_research_attachment_evidence_is_bounded_and_untrusted(tmp_path):
    path = tmp_path / "seed.txt"
    path.write_text("Public clue supplied by the owner.", encoding="utf-8")
    result = _extract_research_attachment_evidence(
        upload_handler=_UploadHandler(path), owner="alice", attachment_ids=["upload-1"],
    )
    assert "UNTRUSTED ATTACHMENT EVIDENCE" in result
    assert "upload_ref=upload-1" in result
    assert "Public clue supplied by the owner." in result


def test_research_attachment_evidence_preserves_owner_boundary(tmp_path):
    path = tmp_path / "seed.txt"
    path.write_text("private", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        _extract_research_attachment_evidence(
            upload_handler=_UploadHandler(path), owner="bob", attachment_ids=["upload-1"],
        )
    assert exc.value.status_code == 404


def test_osint_intake_uploads_selected_files_and_passes_opaque_refs():
    source = (Path(__file__).resolve().parents[1] / "static/js/osint.js").read_text()
    assert "fetch('/api/upload'" in source
    assert "attachment_ids:attachmentIds" in source
    assert "bounded extraction as untrusted evidence" in source


def test_research_start_response_does_not_echo_extracted_attachment_content():
    source = (Path(__file__).resolve().parents[1] / "routes/research/research_routes.py").read_text()
    assert '"query": body.query' in source
    assert '"attachment_count": len(body.attachment_ids)' in source
