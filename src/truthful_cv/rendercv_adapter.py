from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from truthful_cv.manifest import ContentLine, ManifestPolicyError, validate_manifest
from truthful_cv.profile import Profile
from truthful_cv.verifier import verify_text


def build_rendercv_data(
    profile: Profile,
    lines: list[ContentLine],
    *,
    redlines: list[str],
    language: str = "english",
) -> dict[str, Any]:
    """Build a RenderCV-compatible dictionary after evidence validation."""
    if not lines:
        raise ValueError("export requires at least one approved content line")
    validate_manifest(
        lines,
        profile,
        require_line_approval=True,
        language=language,
    )

    identity = profile.identity
    if identity is None:
        raise ValueError("profile identity is required for export")
    contact = identity.contact
    cv: dict[str, Any] = {"name": identity.preferred_name}
    if identity.location:
        cv["location"] = identity.location
    for field in ("email", "phone"):
        if value := getattr(contact, field):
            cv[field] = value
    if contact.linkedin:
        path_parts = [part for part in urlparse(contact.linkedin).path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0].casefold() == "in":
            cv["social_networks"] = [
                {"network": "LinkedIn", "username": path_parts[1]}
            ]

    headline = next((line for line in lines if line.kind == "headline"), None)
    if headline:
        cv["headline"] = headline.text

    sections: dict[str, Any] = {}
    summaries = [line.text for line in lines if line.kind == "summary"]
    if summaries:
        sections["professional_summary"] = summaries

    skills = [
        {"label": line.label, "details": line.text}
        for line in lines
        if line.kind == "skill"
    ]
    if skills:
        sections["technical_skills"] = skills

    credentials = [
        {"label": line.label, "details": line.text}
        for line in lines
        if line.kind == "credential"
    ]
    if credentials:
        sections["certifications_and_training"] = credentials

    bullets_by_subject: dict[str, list[str]] = defaultdict(list)
    for line in lines:
        if line.kind == "bullet" and line.subject_id:
            bullets_by_subject[line.subject_id].append(line.text)

    entries_by_section: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for role in profile.roles:
        highlights = bullets_by_subject.get(role.id)
        if not highlights:
            continue
        section = (
            "structured_training"
            if role.category == "structured_training"
            else "experience"
        )
        entry = {
            "company": role.organization,
            "position": role.localized_titles.get(language, role.title),
            "start_date": role.start,
            "end_date": role.end,
            "highlights": highlights,
        }
        if role.location:
            entry["location"] = role.location
        entries_by_section[section].append(entry)
    sections.update(entries_by_section)

    education_by_id = {item.id: item for item in profile.education}
    education_entries = []
    for line in lines:
        if line.kind != "education" or not line.subject_id:
            continue
        education = education_by_id[line.subject_id]
        entry = {
            "institution": education.institution,
            "area": line.text,
            "degree": line.label,
            "end_date": education.expected_end or education.end,
        }
        if education.start is not None:
            entry["start_date"] = education.start
        education_entries.append(entry)
    if education_entries:
        sections["education"] = education_entries

    section_order = (
        "professional_summary",
        "experience",
        "structured_training",
        "education",
        "technical_skills",
        "certifications_and_training",
    )
    sections = {name: sections[name] for name in section_order if name in sections}
    if language == "spanish":
        spanish_labels = {
            "professional_summary": "resumen_profesional",
            "experience": "experiencia",
            "structured_training": "formación_estructurada",
            "education": "educación",
            "technical_skills": "habilidades_técnicas",
            "certifications_and_training": "certificaciones_y_formación",
        }
        sections = {spanish_labels[name]: entries for name, entries in sections.items()}
    cv["sections"] = sections
    rendered_strings: list[str] = []

    def collect_strings(value: object) -> None:
        if isinstance(value, str):
            rendered_strings.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                collect_strings(item)
        elif isinstance(value, list):
            for item in value:
                collect_strings(item)

    collect_strings(cv)
    redline_result = verify_text("\n".join(rendered_strings), redlines)
    if redline_result.redline_hits:
        raise ManifestPolicyError(
            f"forbidden redline: {redline_result.redline_hits[0]}"
        )
    return {"cv": cv}
