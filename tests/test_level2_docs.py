from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_level2_commands_and_limits_are_documented() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    spanish = (ROOT / "docs" / "GUIA_USO_ES.md").read_text(encoding="utf-8")
    security = (ROOT / "docs" / "security.md").read_text(encoding="utf-8")
    for command in ("vacancy ingest", "vacancy assess", "vacancy finalize"):
        assert command in readme
        assert command in spanish
    assert "--paste-file" in spanish
    assert "--visual-approved" in spanish
    assert "no es una prueba" in spanish
    assert "no envía solicitudes" in spanish
    assert "IP literals" in security
    assert "manual redirect" in security
    assert "LinkedIn, Indeed, and Glassdoor" in security
