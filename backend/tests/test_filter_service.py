import pandas as pd
import pytest

from app.models.schemas import FilterState
from app.services.filter_service import FilterService, treatment_display
from app.services.summary_service import kpi_block, subset_by_window
from app.services.chart_service import CohortService
from app.utils.anonymize import anonymize_records
from app.auth.passwords import hash_password, verify_password


@pytest.fixture
def sample_df():
    dates = pd.date_range("2023-01-01", periods=20, freq="D")
    rows = []
    for i, d in enumerate(dates):
        rows.append({
            "eid": f"982 123536700{i:03d}",
            "date": d,
            "breed": "Brahman X",
            "treatment": "Drench" if i % 3 else None,
            "mob": "Front",
            "sex": "Steer" if i % 2 == 0 else "Heifer",
            "finalpweight": 500 + i * 5,
            "methane": 100 + i,
        })
    return pd.DataFrame(rows)


def test_filter_year_required(sample_df):
    f = FilterState(farm_id="KF", year=2023)
    f.year = None
    with pytest.raises(ValueError):
        FilterService.filter_data(sample_df, f, True)


def test_filter_month_all(sample_df):
    f = FilterState(farm_id="KF", year=2023, month="All")
    out = FilterService.filter_data(sample_df, f, True)
    assert len(out) == 20


def test_filter_month_october(sample_df):
    f = FilterState(farm_id="KF", year=2023, month="January")
    out = FilterService.filter_data(sample_df, f, True)
    assert all(out["date"].dt.month == 1)


def test_filter_no_treatment(sample_df):
    f = FilterState(farm_id="KF", year=2023, treatment=["No Treatment"])
    out = FilterService.filter_data(sample_df, f, True)
    assert out["treatment"].isna().all()


def test_filter_sex_overall(sample_df):
    f = FilterState(farm_id="KF", year=2023, sex=["Overall"])
    out = FilterService.filter_data(sample_df, f, True)
    assert len(out) == 20


def test_eid_ignored_non_admin(sample_df):
    f = FilterState(farm_id="KF", year=2023, eid=["982 123536700001"])
    out = FilterService.filter_data(sample_df, f, False)
    assert len(out) == 20


def test_subset_by_window_last_day(sample_df):
    out = subset_by_window(sample_df, 1)
    assert len(out) == 1
    assert out["date"].max() == sample_df["date"].max()


def test_subset_by_window_15_days(sample_df):
    out = subset_by_window(sample_df, 15)
    assert len(out) == 15


def test_kpi_block_empty():
    df = pd.DataFrame({"finalpweight": []})
    result = kpi_block(df, "finalpweight")
    assert result["display"] == "No data"


def test_kpi_block_values(sample_df):
    result = kpi_block(sample_df, "finalpweight")
    assert result["count"] == 20
    assert result["mean"] > 0


def test_anonymize_records():
    records = [{"eid": "123", "value": 1}]
    anon = anonymize_records(records, False)
    assert anon[0]["eid"] == "*****"
    admin = anonymize_records(records, True)
    assert admin[0]["eid"] == "123"


def test_cohort_percentile(sample_df):
    f = FilterState(farm_id="KF", year=2023)
    result = CohortService.analyze(sample_df, sample_df, "finalpweight", 10, f)
    assert result["total_animals"] == 20
    assert result["top"]["count"] == 2
    assert result["bottom"]["count"] == 2


def test_mixed_warning():
    f = FilterState(farm_id="KF", year=2023, sex=["Overall", "Steer"])
    assert FilterService.has_mixed_selection(f)


def test_scrypt_password():
    h = hash_password("testpass123")
    assert verify_password("testpass123", h)
    assert not verify_password("wrong", h)


def test_treatment_display():
    assert treatment_display(None) == "No Treatment"
    assert treatment_display("Drench") == "Drench"
