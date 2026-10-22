from pathlib import Path
from prime_gate.db.engine import BinaryDatabaseEngine
from prime_gate.db.binary_codec import BinaryCodec

REPO_ROOT = Path(__file__).resolve().parent.parent

def test_no_absolute_claims_in_readme():
    """Verify that marketing absolutisms like 100% Anti-Banned or Zero Token Waste are eliminated."""
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists(), "README.md must exist"
    readme_text = readme_path.read_text(encoding="utf-8")

    assert "100% Anti-Banned" not in readme_text, "README.md must not claim 100% Anti-Banned"
    assert "100% anti-banned" not in readme_text.lower(), "README.md must not contain lowercase 100% anti-banned"
    assert "zero token waste" not in readme_text.lower(), "README.md must not claim Zero Token Waste"


def test_disclaimer_and_risk_sections_exist():
    """Verify that Disclaimer & Risks / Risiko is present and explicitly warns against using primary accounts."""
    readme_path = REPO_ROOT / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")

    assert ("Disclaimer & Risks" in readme_text or "Disclaimer & Risiko" in readme_text), \
        "README.md must include Disclaimer & Risks section"
    assert ("NEVER" in readme_text or "JANGAN PERNAH" in readme_text), \
        "README.md must explicitly warn against using primary accounts"
    assert ("not affiliated" in readme_text.lower() or "tidak berafiliasi" in readme_text.lower()), \
        "README.md must state non-affiliation with Google/Anthropic"

    # Also verify Indonesian localization retains identical guarantees
    id_readme_path = REPO_ROOT / "locales" / "id" / "README.md"
    if id_readme_path.exists():
        id_text = id_readme_path.read_text(encoding="utf-8")
        assert "Disclaimer & Risiko" in id_text
        assert "JANGAN PERNAH" in id_text
        assert "tidak berafiliasi" in id_text.lower()


def test_known_limitations_and_threat_model_exist():
    """Verify that Known Limitations and Threat Model sections are present in README.md."""
    readme_path = REPO_ROOT / "README.md"
    readme_text = readme_path.read_text(encoding="utf-8")

    assert "Batasan yang Diketahui" in readme_text or "Known Limitations" in readme_text, \
        "README.md must document Known Limitations"
    assert "Model Ancaman" in readme_text or "Threat Model" in readme_text, \
        "README.md must document Threat Model"


def test_contributing_and_license_exist():
    """Verify that CONTRIBUTING.md and LICENSE exist and are well-formed."""
    contrib_path = REPO_ROOT / "CONTRIBUTING.md"
    license_path = REPO_ROOT / "LICENSE"

    assert contrib_path.exists(), "CONTRIBUTING.md must exist"
    assert len(contrib_path.read_text(encoding="utf-8").strip()) > 100, "CONTRIBUTING.md must not be empty"

    assert license_path.exists(), "LICENSE must exist"
    assert "MIT License" in license_path.read_text(encoding="utf-8"), "LICENSE must be MIT License"


def test_accurate_technical_database_docstrings():
    """Verify that database engine docstrings accurately reflect SQLite WAL & CRC32 integrity."""
    engine_doc = BinaryDatabaseEngine.__doc__ or ""
    assert "Compiled C binary database engine" not in engine_doc, \
        "BinaryDatabaseEngine must not falsely claim to be a compiled C binary engine"
    assert "SQLite" in engine_doc, "BinaryDatabaseEngine docstring must mention SQLite"
    assert "WAL" in engine_doc, "BinaryDatabaseEngine docstring must mention WAL mode"

    codec_doc = BinaryCodec.__doc__ or ""
    assert "integrity" in codec_doc.lower(), "BinaryCodec docstring must describe CRC32 as integrity check"


def test_dashboard_label_clarification():
    """Verify that dashboard UI refers to commercial API equivalent estimates rather than direct cost savings."""
    dash_path = REPO_ROOT / "ui" / "src" / "pages" / "DashboardPage.tsx"
    assert dash_path.exists(), "DashboardPage.tsx must exist"
    dash_text = dash_path.read_text(encoding="utf-8")

    assert "Nilai Setara API Komersial" in dash_text, \
        "DashboardPage.tsx must label economic estimate as Nilai Setara API Komersial"
    assert "Commercial API savings" not in dash_text, \
        "DashboardPage.tsx must not use inaccurate 'Commercial API savings' label"
