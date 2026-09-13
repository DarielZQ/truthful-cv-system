from pathlib import Path
import re

from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PyPdfError


class VerificationResult(BaseModel):
    ok: bool
    page_count: int | None = None
    text_chars: int = 0
    redline_hits: list[str]
    missing_required_texts: list[str] = Field(default_factory=list)
    errors: list[str]


def rendered_string_inventory(
    document: dict[str, object], language: str = "english"
) -> list[str]:
    """Return deterministic strings expected in RenderCV's PDF text layer."""
    inventory: list[str] = []

    english_months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    spanish_months = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
    months = spanish_months if language == "spanish" else english_months

    def add(value: object, key: str | None = None) -> None:
        if isinstance(value, str):
            date_match = re.fullmatch(r"(\d{4})-(\d{2})", value)
            if key == "phone":
                groups = re.findall(r"\d+", value)
                if value.lstrip().startswith("+") and len(groups) > 1:
                    groups = groups[1:]
                inventory.extend(groups)
            elif date_match:
                year, month = date_match.groups()
                month_number = int(month)
                if month_number not in range(1, 13):
                    raise ValueError(f"invalid rendered date: {value}")
                inventory.append(f"{months[month_number - 1]} {year}")
            elif _normalize_for_coverage(value):
                inventory.append(value)
        elif isinstance(value, int):
            inventory.append(str(value))
        elif isinstance(value, list):
            for item in value:
                add(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                if key == "sections" and isinstance(item, dict):
                    for section_name, entries in item.items():
                        inventory.append(section_name.replace("_", " ").title())
                        add(entries)
                else:
                    add(item, key)

    add(document.get("cv", {}))
    return list(dict.fromkeys(inventory))


def _normalize_for_coverage(text: str) -> str:
    dehyphenated = re.sub(r"\s*-\s*\r?\n\s*", "", text).replace("-", "")
    words_only = re.sub(r"[^\w]+", " ", dehyphenated.casefold())
    month_aliases = {
        "january": "jan",
        "february": "feb",
        "march": "mar",
        "april": "apr",
        "june": "jun",
        "july": "jul",
        "august": "aug",
        "september": "sep",
        "sept": "sep",
        "october": "oct",
        "november": "nov",
        "december": "dec",
        "enero": "ene",
        "marzo": "mar",
        "abril": "abr",
        "mayo": "may",
        "junio": "jun",
        "julio": "jul",
        "agosto": "ago",
        "septiembre": "sep",
        "setiembre": "sep",
        "octubre": "oct",
        "noviembre": "nov",
        "diciembre": "dic",
    }
    return " ".join(month_aliases.get(word, word) for word in words_only.split())


def verify_text(
    text: str,
    redlines: list[str],
    required_texts: list[str] | None = None,
) -> VerificationResult:
    normalized_text = _normalize_for_coverage(text)
    hits = [
        redline
        for redline in redlines
        if _normalize_for_coverage(redline)
        and _normalize_for_coverage(redline) in normalized_text
    ]
    required_items = required_texts or []
    invalid_required = [
        required for required in required_items if not _normalize_for_coverage(required)
    ]
    missing = [
        required
        for required in required_items
        if not _normalize_for_coverage(required)
        or _normalize_for_coverage(required) not in normalized_text
    ]
    errors = [f"redline found: {redline}" for redline in hits]
    errors.extend(f"invalid required text: {required!r}" for required in invalid_required)
    errors.extend(
        f"required text missing: {required}"
        for required in missing
        if required not in invalid_required
    )
    return VerificationResult(
        ok=not errors,
        text_chars=len(text),
        redline_hits=hits,
        missing_required_texts=missing,
        errors=errors,
    )


def verify_pdf(
    pdf_path: Path,
    redlines: list[str],
    max_pages: int = 2,
    min_text_chars: int = 200,
    required_texts: list[str] | None = None,
) -> VerificationResult:
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except (OSError, PyPdfError):
        return VerificationResult(
            ok=False,
            page_count=None,
            text_chars=0,
            redline_hits=[],
            errors=["unable to read PDF"],
        )
    result = verify_text(text, redlines, required_texts=required_texts)
    page_count = len(reader.pages)
    errors = list(result.errors)
    if page_count > max_pages:
        errors.append(f"page limit exceeded: {page_count} > {max_pages}")
    if len(text) < min_text_chars:
        errors.append(f"text layer too short: {len(text)} < {min_text_chars}")
    return VerificationResult(
        ok=not errors,
        page_count=page_count,
        text_chars=len(text),
        redline_hits=result.redline_hits,
        missing_required_texts=result.missing_required_texts,
        errors=errors,
    )
