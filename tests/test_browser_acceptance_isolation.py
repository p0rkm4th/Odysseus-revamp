"""Acceptance must refuse to bind the repository's owner data directory."""

from pathlib import Path


SCRIPT = (Path(__file__).parents[1] / "scripts/browser_authenticated_acceptance.mjs").read_text()


def test_browser_acceptance_requires_a_disposable_data_directory():
    assert "APP_DATA_DIR must name a disposable data directory" in SCRIPT
    assert "APP_DATA_DIR points at owner data" in SCRIPT
    assert "path.resolve(process.cwd(), 'data')" in SCRIPT


def test_browser_acceptance_isolates_mixed_synthetic_scenarios_but_not_owner_runs():
    """Per-scenario fixture isolation permits mixed synthetic corpus runs."""
    assert "cannot mix actual_owner_read_only and synthetic scenarios" in SCRIPT
    assert "exactly one isolated fixture_profile" not in SCRIPT
    assert "fresh acceptance" in SCRIPT
    assert "prepareScenarioFixture(page, scenario)" in SCRIPT
