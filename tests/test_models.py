import pytest
from pydantic import ValidationError

from truthful_cv.models import (
    Attribution,
    Claim,
    ClaimCategory,
    ClaimStatus,
    EvidenceTier,
)


def test_approved_claim_requires_a_source() -> None:
    with pytest.raises(ValidationError, match="approved claim must reference evidence"):
        Claim(
            id="CLM-001",
            statement="Provided deskside technical support.",
            category="professional",
            tier=EvidenceTier.C,
            attribution=Attribution.INDIVIDUAL,
            status=ClaimStatus.APPROVED,
            source_ids=[],
            tags=["it_support"],
        )


def test_tier_d_claim_cannot_be_approved() -> None:
    with pytest.raises(ValidationError, match="Tier D claim cannot be approved"):
        Claim(
            id="CLM-002",
            statement="Holds a credential that is contradicted by evidence.",
            category="certification",
            tier=EvidenceTier.D,
            attribution=Attribution.UNKNOWN,
            status=ClaimStatus.APPROVED,
            source_ids=["SRC-001"],
        )


def test_claim_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError, match="category"):
        Claim(
            id="CLM-003",
            statement="A supported fact.",
            category="unsupported",
            tier=EvidenceTier.C,
            attribution=Attribution.INDIVIDUAL,
            status=ClaimStatus.APPROVED,
            source_ids=["SRC-001"],
        )


def test_claim_rejects_whitespace_only_statement() -> None:
    with pytest.raises(ValidationError, match="statement"):
        Claim(
            id="CLM-003",
            statement="   ",
            category="knowledge",
            tier=EvidenceTier.C,
            attribution=Attribution.INDIVIDUAL,
            status=ClaimStatus.APPROVED,
            source_ids=["SRC-001"],
        )


@pytest.mark.parametrize("category", list(ClaimCategory))
def test_claim_accepts_each_supported_category(category: ClaimCategory) -> None:
    claim = Claim(
        id="CLM-004",
        statement="A supported fact.",
        category=category,
        tier=EvidenceTier.C,
        attribution=Attribution.INDIVIDUAL,
        status=ClaimStatus.APPROVED,
        source_ids=["SRC-001"],
    )

    assert claim.category is category
