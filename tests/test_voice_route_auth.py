from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_voice_routes_require_authenticated_owner_before_processing_audio_or_text():
    stt = (ROOT / "routes/stt_routes.py").read_text()
    tts = (ROOT / "routes/tts_routes.py").read_text()
    for source in (stt, tts):
        assert "from src.auth_helpers import require_user" in source
        assert "def _authenticated(request: Request)" in source
        assert "_authenticated(request)" in source
    assert "UploadFile" in stt
    assert "TTSRequest" in tts
