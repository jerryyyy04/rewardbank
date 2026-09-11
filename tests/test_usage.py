from app.usage_service import calculate_usage


def test_usage_fits_inside_balance():
    result = calculate_usage(
        start_time="2026-09-10T10:00:00+00:00",
        end_time="2026-09-10T10:05:00+00:00",
        balance=10,
    )

    assert result["requested_minutes"] == 5
    assert result["covered_minutes"] == 5
    assert result["rejected_minutes"] == 0
    assert result["cutoff_time"] is None


def test_usage_exceeds_balance():
    result = calculate_usage(
        start_time="2026-09-10T10:00:00+00:00",
        end_time="2026-09-10T10:15:00+00:00",
        balance=10,
    )

    assert result["requested_minutes"] == 15
    assert result["covered_minutes"] == 10
    assert result["rejected_minutes"] == 5
    assert result["cutoff_time"] == "2026-09-10T10:10:00+00:00"


def test_zero_balance_blocks_entire_session():
    result = calculate_usage(
        start_time="2026-09-10T10:00:00+00:00",
        end_time="2026-09-10T10:15:00+00:00",
        balance=0,
    )

    assert result["requested_minutes"] == 15
    assert result["covered_minutes"] == 0
    assert result["rejected_minutes"] == 15
    assert result["cutoff_time"] == "2026-09-10T10:00:00+00:00"