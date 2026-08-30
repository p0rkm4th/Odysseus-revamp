"""Keep the Docker Chroma volume aligned with the image's persistence path."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_all_compose_variants_mount_chroma_persistence_path():
    for name in (
        "docker-compose.yml",
        "docker-compose.gpu-nvidia.yml",
        "docker-compose.gpu-amd.yml",
    ):
        text = (ROOT / name).read_text()
        assert "chromadb-data:/data" in text, name
        assert "chromadb-data:/chroma/chroma" not in text, name
