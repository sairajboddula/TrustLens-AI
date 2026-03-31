"""
Tests for Fraud Detection Utilities

Covers:
  - calculate_name_similarity
  - validate_id_format
  - check_duplicate_submission
  - calculate_fraud_score
  - generate_fraud_report
"""

from __future__ import annotations

import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.fraud_detection import (
    calculate_fraud_score,
    calculate_name_similarity,
    check_duplicate_submission,
    generate_fraud_report,
    validate_id_format,
)


# ---------------------------------------------------------------------------
# Name similarity
# ---------------------------------------------------------------------------


def test_name_similarity_exact_match():
    """Identical names produce a similarity score of 1.0."""
    score = calculate_name_similarity("John Doe", "John Doe")
    assert score == 1.0


def test_name_similarity_case_insensitive():
    """Name similarity is case-insensitive."""
    score = calculate_name_similarity("JOHN DOE", "john doe")
    assert score >= 0.95


def test_name_similarity_close_match():
    """Names differing by a single character still score above 0.80."""
    score = calculate_name_similarity("John Doe", "Jon Doe")
    assert score >= 0.80


def test_name_similarity_different_names():
    """Completely different names produce a low similarity score."""
    score = calculate_name_similarity("John Doe", "Alice Smith")
    assert score < 0.50


def test_name_similarity_reversed_order():
    """Token-sort ratio handles reversed name order gracefully."""
    score = calculate_name_similarity("John Doe", "Doe John")
    # Token-sort ratio should give ~1.0 for reversed tokens
    assert score >= 0.85


def test_name_similarity_empty_string():
    """Empty name returns 0.0 similarity."""
    assert calculate_name_similarity("", "John Doe") == 0.0
    assert calculate_name_similarity("John Doe", "") == 0.0
    assert calculate_name_similarity("", "") == 0.0


def test_name_similarity_none_input():
    """None inputs return 0.0."""
    assert calculate_name_similarity(None, "John Doe") == 0.0
    assert calculate_name_similarity("John Doe", None) == 0.0


# ---------------------------------------------------------------------------
# ID format validation
# ---------------------------------------------------------------------------


def test_id_format_validation_passport_valid():
    """Valid passport numbers (6-9 alphanumeric chars) pass validation."""
    valid_numbers = ["AB123456", "Z9X8W7V6", "ABCDEF"]
    for id_num in valid_numbers:
        is_valid, err = validate_id_format(id_num, "passport")
        assert is_valid, f"Expected {id_num} to be valid, got error: {err}"
        assert err is None


def test_id_format_validation_passport_invalid():
    """Passport numbers that are too short or contain special chars fail."""
    invalid = ["AB1", "ABC!@#456", ""]
    for id_num in invalid:
        is_valid, err = validate_id_format(id_num, "passport")
        assert not is_valid, f"Expected {id_num} to be invalid"
        assert err is not None


def test_id_format_validation_drivers_license():
    """Valid driver's license numbers pass; invalid ones fail."""
    valid = ["DL12345", "A1B2C3D4E5", "XY-123456"]
    for id_num in valid:
        is_valid, err = validate_id_format(id_num, "drivers_license")
        assert is_valid, f"Expected {id_num} to be valid, got: {err}"

    invalid = ["AB!"]  # too short / special chars
    for id_num in invalid:
        is_valid, _ = validate_id_format(id_num, "drivers_license")
        assert not is_valid, f"Expected {id_num} to be invalid"


def test_id_format_validation_national_id():
    """Valid national ID numbers pass validation."""
    valid = ["NID-12345", "123456789AB", "AB-123-XYZ"]
    for id_num in valid:
        is_valid, err = validate_id_format(id_num, "national_id")
        assert is_valid, f"Expected {id_num} to be valid, got: {err}"


def test_id_format_validation_empty_id():
    """Empty ID number always fails."""
    is_valid, err = validate_id_format("", "passport")
    assert not is_valid
    assert err is not None


def test_id_format_validation_unknown_type():
    """Unknown document type falls back to alphanumeric validation."""
    is_valid, err = validate_id_format("XYZ123", "alien_card")
    assert is_valid
    assert err is None


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_duplicate_detection_no_duplicate():
    """Returns False when no matching submission exists in the DB."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await check_duplicate_submission(
        db=mock_db,
        name="John Doe",
        dob="1990-01-15",
        id_number="AB123456",
    )
    assert result is False


@pytest.mark.asyncio
async def test_duplicate_detection_found():
    """Returns True when a matching submission is found in the DB."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = uuid.uuid4()  # found
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await check_duplicate_submission(
        db=mock_db,
        name="John Doe",
        dob="1990-01-15",
        id_number="AB123456",
    )
    assert result is True


@pytest.mark.asyncio
async def test_duplicate_detection_db_error_returns_false():
    """DB error during duplicate check returns False (fail-open, not fail-closed)."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_db.execute = AsyncMock(side_effect=Exception("DB connection lost"))

    result = await check_duplicate_submission(
        db=mock_db,
        name="John Doe",
        dob="1990-01-15",
        id_number="AB123456",
    )
    assert result is False


# ---------------------------------------------------------------------------
# Fraud score calculation
# ---------------------------------------------------------------------------


def _make_state(**kwargs) -> Dict[str, Any]:
    base = {
        "fraud_flags": [],
        "name_match_score": 1.0,
        "dob_match": True,
        "id_match": True,
        "confidence_score": 0.95,
        "ocr_results": [{"confidence": 0.90}],
        "duplicate_detected": False,
        "decision": None,
    }
    base.update(kwargs)
    return base


def test_fraud_score_clean_state_is_zero():
    """No fraud flags and high confidence yield a fraud score of 0.0."""
    state = _make_state()
    score = calculate_fraud_score(state)
    assert score == 0.0


def test_fraud_score_increases_with_flags():
    """Each additional fraud flag raises the fraud score."""
    state_one_flag = _make_state(fraud_flags=["NAME_MISMATCH"])
    state_two_flags = _make_state(fraud_flags=["NAME_MISMATCH", "DOB_MISMATCH"])

    score_one = calculate_fraud_score(state_one_flag)
    score_two = calculate_fraud_score(state_two_flags)

    assert score_one > 0.0
    assert score_two > score_one


def test_fraud_score_critical_flag_penalizes_heavily():
    """DUPLICATE_SUBMISSION flag contributes more than a regular flag."""
    regular_state = _make_state(fraud_flags=["NAME_MISMATCH"])
    critical_state = _make_state(fraud_flags=["DUPLICATE_SUBMISSION"])

    regular_score = calculate_fraud_score(regular_state)
    critical_score = calculate_fraud_score(critical_state)

    assert critical_score > regular_score


def test_fraud_score_capped_at_one():
    """Fraud score is always in [0.0, 1.0]."""
    state = _make_state(
        fraud_flags=[
            "NAME_MISMATCH",
            "DOB_MISMATCH",
            "ID_MISMATCH",
            "ID_FORMAT_INVALID",
            "DUPLICATE_SUBMISSION",
            "LOW_OCR_CONFIDENCE",
        ],
        name_match_score=0.10,
        dob_match=False,
        ocr_results=[{"confidence": 0.10}],
    )
    score = calculate_fraud_score(state)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Fraud report generation
# ---------------------------------------------------------------------------


def test_generate_fraud_report_structure():
    """generate_fraud_report returns a dict with all expected keys."""
    state = _make_state()
    report = generate_fraud_report(state)

    required_keys = {"fraud_score", "risk_verdict", "flags", "checks", "overall_confidence"}
    assert required_keys.issubset(report.keys())


def test_generate_fraud_report_risk_verdict_clear():
    """A clean state produces CLEAR risk verdict."""
    state = _make_state()
    report = generate_fraud_report(state)
    assert report["risk_verdict"] == "CLEAR"


def test_generate_fraud_report_risk_verdict_high():
    """Multiple critical fraud flags yield HIGH_RISK verdict."""
    state = _make_state(
        fraud_flags=["DUPLICATE_SUBMISSION", "ID_FORMAT_INVALID", "NAME_MISMATCH"],
        name_match_score=0.30,
        dob_match=False,
    )
    report = generate_fraud_report(state)
    assert report["risk_verdict"] in ("HIGH_RISK", "MEDIUM_RISK")


def test_generate_fraud_report_checks_keys():
    """The checks dict contains all expected check categories."""
    state = _make_state()
    report = generate_fraud_report(state)
    checks = report["checks"]
    for key in ("name_similarity", "date_of_birth", "id_number", "duplicate_check", "ocr_quality"):
        assert key in checks, f"Missing check key: {key}"
