from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.analysis_models import AnalysisSummary, canonical_analysis_schema
from src.analytics import build_summary
from src.models import EvidenceSegment
from tests.test_models import valid_record


def valid_summary() -> dict:
    record = EvidenceSegment.model_validate(valid_record())
    return build_summary([record])


def test_generated_summary_matches_pydantic_and_json_schema() -> None:
    summary = valid_summary()
    assert AnalysisSummary.model_validate(summary).metric_version == "1.0.0"
    Draft202012Validator(canonical_analysis_schema()).validate(summary)


def test_population_totals_cannot_drift() -> None:
    summary = deepcopy(valid_summary())
    summary["population"]["excluded_records"] = 1
    with pytest.raises(ValidationError, match="must equal all_records"):
        AnalysisSummary.model_validate(summary)


def test_segment_denominator_is_checked() -> None:
    summary = deepcopy(valid_summary())
    summary["population"]["additional_target_records"] = 1
    with pytest.raises(ValidationError, match="must equal additional_target_records"):
        AnalysisSummary.model_validate(summary)


def test_review_coverage_is_recomputed_from_counts() -> None:
    summary = deepcopy(valid_summary())
    summary["population"]["human_review_coverage"] = 0.5
    with pytest.raises(ValidationError, match="must equal reviewed_records / all_records"):
        AnalysisSummary.model_validate(summary)


def test_allegation_total_and_nonnegative_counts_are_checked() -> None:
    summary = deepcopy(valid_summary())
    summary["allegation_qualification_counts"]["total_allegations"] = 2
    summary["review_state_counts"]["human_reviewed"] = -1
    with pytest.raises(ValidationError) as error:
        AnalysisSummary.model_validate(summary)
    messages = str(error.value)
    assert "must equal total_allegations" in messages
    assert "greater than or equal to 0" in messages
