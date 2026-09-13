from pathlib import Path

import pytest
from pypdf import PdfWriter

import truthful_cv.verifier as verifier
from truthful_cv.verifier import rendered_string_inventory, verify_pdf, verify_text


def test_verify_text_reports_forbidden_redline() -> None:
    result = verify_text("Candidate has production Kuber-\nnetes experience.", ["Kubernetes"])

    assert not result.ok
    assert result.redline_hits == ["Kubernetes"]
    assert result.errors == ["redline found: Kubernetes"]


def test_verify_text_reports_missing_required_manifest_content() -> None:
    result = verify_text(
        "Technical support across\nWindows environments with configu-\nration. Cloud-\nsupport.",
        redlines=[],
        required_texts=[
            "Technical support across Windows environments with configuration.",
            "Cloud-support.",
            "ServiceNow",
        ],
    )

    assert not result.ok
    assert result.missing_required_texts == ["ServiceNow"]

def test_verify_text_rejects_empty_or_punctuation_only_required_text() -> None:
    result = verify_text(
        "Technical support.",
        redlines=[],
        required_texts=["", "---"],
    )

    assert not result.ok
    assert result.missing_required_texts == ["", "---"]
    assert "invalid required text" in result.errors[0]


def test_rendered_inventory_uses_pdf_date_and_phone_forms() -> None:
    document = {
        "cv": {
            "phone": "+506 5555 0101",
            "sections": {
                "experience": [
                    {"start_date": "2025-12", "end_date": "2026-01"}
                ]
            },
        }
    }

    inventory = rendered_string_inventory(document, language="english")

    assert "Dec 2025" in inventory
    assert "Jan 2026" in inventory
    assert "5555" in inventory
    assert "0101" in inventory
    assert "+506 5555 0101" not in inventory


@pytest.mark.parametrize(
    ("rendered", "required"),
    [
        ("June 2025", "Jun 2025"),
        ("July 2025", "Jul 2025"),
        ("September 2025", "Sep 2025"),
        ("junio 2025", "Jun 2025"),
    ],
)
def test_verify_text_treats_rendercv_month_variants_as_equivalent(
    rendered: str, required: str
) -> None:
    result = verify_text(
        f"Jan 2025 – {rendered}",
        redlines=[],
        required_texts=["Jan 2025", required],
    )

    assert result.ok


def test_rendered_inventory_rejects_impossible_year_month_cleanly() -> None:
    document = {"cv": {"sections": {"experience": [{"start_date": "2025-99"}]}}}

    with pytest.raises(ValueError, match="invalid rendered date: 2025-99"):
        rendered_string_inventory(document)


def test_verify_pdf_enforces_page_limit(tmp_path: Path) -> None:
    pdf = tmp_path / "two-pages.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with pdf.open("wb") as stream:
        writer.write(stream)

    result = verify_pdf(pdf, redlines=[], max_pages=1)

    assert not result.ok
    assert result.page_count == 2
    assert "page limit exceeded: 2 > 1" in result.errors


def test_verify_pdf_rejects_missing_text_layer(tmp_path: Path) -> None:
    pdf = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf.open("wb") as handle:
        writer.write(handle)

    result = verify_pdf(pdf, redlines=[], min_text_chars=1)

    assert not result.ok
    assert "text layer too short: 0 < 1" in result.errors


def test_verify_pdf_propagates_unexpected_programmer_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenPage:
        def extract_text(self) -> str:
            raise RuntimeError("programmer defect")

    class BrokenReader:
        pages = [BrokenPage()]

    monkeypatch.setattr(verifier, "PdfReader", lambda _: BrokenReader())

    with pytest.raises(RuntimeError, match="programmer defect"):
        verify_pdf(Path("synthetic.pdf"), redlines=[])


def test_verify_pdf_returns_failure_for_missing_file(tmp_path: Path) -> None:
    result = verify_pdf(tmp_path / "missing.pdf", redlines=[])

    assert not result.ok
    assert result.page_count is None
    assert result.errors == ["unable to read PDF"]
