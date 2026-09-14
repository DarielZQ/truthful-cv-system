from __future__ import annotations

import os
from pathlib import Path


def safe_private_path(root: Path, *parts: str | Path) -> Path:
    """Return a resolved path contained by root, rejecting traversal and link escapes."""
    root = root.expanduser().resolve(strict=False)
    candidate = root
    for part in parts:
        value = Path(part)
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("private storage boundary violation")
        candidate /= value
    resolved = candidate.resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError("private storage boundary violation")
    # Windows junctions/reparse points are followed by resolve(); normcase also
    # prevents drive/case aliases from bypassing the parent comparison.
    root_case = os.path.normcase(str(root))
    target_case = os.path.normcase(str(resolved))
    try:
        common = os.path.commonpath([root_case, target_case])
    except ValueError as error:
        raise ValueError("private storage boundary violation") from error
    if common != root_case:
        raise ValueError("private storage boundary violation")
    return resolved
