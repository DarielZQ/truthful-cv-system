from pydantic import BaseModel

from truthful_cv.manifest import ContentLine, validate_manifest
from truthful_cv.matcher import JobRequirement
from truthful_cv.profile import Profile


class RankedLine(BaseModel):
    line: ContentLine
    score: int
    matched_requirement_ids: list[str]


def rank_lines_for_job(
    profile: Profile,
    lines: list[ContentLine],
    requirements: list[JobRequirement],
) -> list[RankedLine]:
    """Rank already-approved content by transparent requirement overlap."""
    validate_manifest(lines, profile, require_line_approval=True)
    claims = {claim.id: claim for claim in profile.claims}
    ranked: list[tuple[int, int, RankedLine]] = []
    for index, line in enumerate(lines):
        line_tags = {
            tag.casefold()
            for claim_id in line.claim_ids
            for tag in claims[claim_id].tags
        }
        matched = [
            requirement
            for requirement in requirements
            if line_tags.intersection(tag.casefold() for tag in requirement.tags)
        ]
        score = sum(2 if requirement.required else 1 for requirement in matched)
        ranked.append(
            (
                -score,
                index,
                RankedLine(
                    line=line,
                    score=score,
                    matched_requirement_ids=[requirement.id for requirement in matched],
                ),
            )
        )
    return [item for _, _, item in sorted(ranked)]
