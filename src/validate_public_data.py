from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import EvidenceSegment


def validate_jsonl(path: Path) -> int:
    errors: list[str] = []
    count = 0

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            count += 1
            try:
                EvidenceSegment.model_validate(json.loads(line))
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                errors.append(f"{path}:{line_number}: {exc}")

    if errors:
        raise SystemExit("\n".join(errors))

    return count


def main() -> None:
    data_path = Path("public-data/evidence-segments.jsonl")
    if not data_path.exists():
        raise SystemExit(f"Missing required file: {data_path}")

    count = validate_jsonl(data_path)
    print(f"Validated {count} evidence records.")


if __name__ == "__main__":
    main()
