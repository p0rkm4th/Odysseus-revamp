from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_version_exposes_source_build_frontend_and_migration_identity():
    source = (ROOT / "app.py").read_text()
    for field in ("source_commit", "build_id", "build_time", "image_id", "frontend_build_id", "migration_head"):
        assert f'"{field}"' in source


def test_candidate_image_and_frontend_verification_are_source_attributable():
    dockerfile = (ROOT / "Dockerfile").read_text()
    build = (ROOT / "scripts/build_candidate.sh").read_text()
    frontend = (ROOT / "scripts/verify_frontend.sh").read_text()
    for value in ("ODYSSEUS_SOURCE_COMMIT", "ODYSSEUS_BUILD_ID", "ODYSSEUS_BUILD_TIME", "ODYSSEUS_FRONTEND_BUILD_ID"):
        assert value in dockerfile and value in build
    assert "org.opencontainers.image.revision" in dockerfile
    assert "node --check" in frontend
    assert '"test:frontend"' in (ROOT / "package.json").read_text()
    assert ".odysseus-source-commit" in dockerfile
    overlay = (ROOT / "docker" / "Dockerfile.source-overlay").read_text()
    assert "ODYSSEUS_BASE_IMAGE" in overlay
    assert ".odysseus-source-commit" in overlay


def test_frontend_html_carries_build_identity_marker():
    helper = (ROOT / "src/app_helpers.py").read_text()
    html = (ROOT / "static/index.html").read_text()
    assert "ODYSSEUS_FRONTEND_BUILD_ID" in helper
    assert "odysseus-frontend-build-id" in html
