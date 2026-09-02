from __future__ import annotations

import math

import numpy as np
import pandas as pd

from app.constants import MEASURE_LABELS, MEASURE_UNITS
from app.models.schemas import FilterState
from app.services.filter_service import FilterService


def sample_for_distribution(df: pd.DataFrame, max_per_group: int = 500) -> pd.DataFrame:
    if len(df) <= 2000:
        return df
    return (
        df.groupby("group", group_keys=False)
        .apply(lambda g: g.sample(n=min(max_per_group, len(g)), random_state=42))
        .reset_index(drop=True)
    )


class DistributionService:
    @staticmethod
    def compute(grouped_df: pd.DataFrame, measure: str, hist_bins: int = 20) -> dict:
        if grouped_df.empty:
            return {"histogram": {"bins": [], "groups": [], "mean": 0, "median": 0}, "boxplot": {"groups": []}}

        hist_bins = max(10, min(50, hist_bins))
        sample_df = grouped_df
        if len(grouped_df) > 5000:
            sample_df = sample_for_distribution(grouped_df, 500)
        elif len(grouped_df) > 2000:
            sample_df = sample_for_distribution(grouped_df, 300)

        hist_groups = []
        all_values = []
        for group, gdf in sample_df.groupby("group"):
            vals = gdf[measure].dropna().tolist()
            if len(vals) > 3000:
                vals = list(np.random.default_rng(42).choice(vals, size=200, replace=False))
            hist_groups.append({"group": group, "values": vals})
            all_values.extend(vals)

        box_groups = []
        for group, gdf in grouped_df.groupby("group"):
            vals = gdf[measure].dropna()
            if vals.empty:
                continue
            q1, med, q3 = vals.quantile([0.25, 0.5, 0.75])
            box_groups.append(
                {
                    "group": group,
                    "min": round(float(vals.min()), 2),
                    "q1": round(float(q1), 2),
                    "median": round(float(med), 2),
                    "q3": round(float(q3), 2),
                    "max": round(float(vals.max()), 2),
                }
            )

        mean_val = round(float(np.mean(all_values)), 2) if all_values else 0
        median_val = round(float(np.median(all_values)), 2) if all_values else 0

        return {
            "histogram": {
                "bins": hist_bins,
                "groups": hist_groups,
                "mean": mean_val,
                "median": median_val,
            },
            "boxplot": {"groups": box_groups},
        }


class TimeseriesService:
    @staticmethod
    def compute(grouped_df: pd.DataFrame, measure: str, show_smooth: bool = False) -> dict:
        if grouped_df.empty:
            return {"series": [], "y_label": f"{measure} ({MEASURE_UNITS.get(measure, '')})"}

        daily = (
            grouped_df.groupby(["date", "group"])[measure]
            .agg(value="mean", count="count")
            .reset_index()
        )
        daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
        series = daily.to_dict(orient="records")

        if show_smooth and len(series) > 3:
            for group in daily["group"].unique():
                gdf = daily[daily["group"] == group].sort_values("date")
                if len(gdf) >= 3:
                    window = max(3, len(gdf) // 5)
                    smoothed = gdf["value"].rolling(window=window, center=True, min_periods=1).mean()
                    for (_, row), sm in zip(gdf.iterrows(), smoothed):
                        series.append(
                            {
                                "date": row["date"],
                                "group": f"{group} (trend)",
                                "value": round(float(sm), 2),
                                "count": int(row["count"]),
                            }
                        )

        label = MEASURE_LABELS.get(measure, measure)
        unit = MEASURE_UNITS.get(measure, "")
        return {"series": series, "y_label": f"{label} ({unit})"}


class CohortService:
    @staticmethod
    def analyze(
        filtered_df: pd.DataFrame, grouped_df: pd.DataFrame, measure: str, percentile: int, filters: FilterState
    ) -> dict:
        percentile = max(10, min(20, percentile))
        if percentile not in (10, 15, 20):
            percentile = 10

        mixed = FilterService.has_mixed_selection(filters)

        if filtered_df.empty:
            return {
                "percentile": percentile,
                "total_animals": 0,
                "top": {"count": 0, "average": 0, "min": 0, "max": 0, "animals": []},
                "bottom": {"count": 0, "average": 0, "min": 0, "max": 0, "animals": []},
                "show_mixed_warning": mixed,
                "timeline": [],
            }

        per_animal = filtered_df.groupby("eid")[measure].mean().reset_index(name="avg_measure")
        per_animal = per_animal.sort_values("avg_measure", ascending=False)
        n = len(per_animal)
        k = max(1, math.ceil(n * percentile / 100))

        top = per_animal.head(k)
        bottom = per_animal.tail(k)

        def cohort_stats(cdf: pd.DataFrame) -> dict:
            return {
                "count": len(cdf),
                "average": round(float(cdf["avg_measure"].mean()), 2) if len(cdf) else 0,
                "min": round(float(cdf["avg_measure"].min()), 2) if len(cdf) else 0,
                "max": round(float(cdf["avg_measure"].max()), 2) if len(cdf) else 0,
                "animals": [
                    {"eid": r["eid"], "avg_measure": round(float(r["avg_measure"]), 2)}
                    for _, r in cdf.iterrows()
                ],
            }

        timeline = []
        top_eids = set(top["eid"])
        bottom_eids = set(bottom["eid"])
        for cohort_name, eids in [("top", top_eids), ("bottom", bottom_eids)]:
            cdf = filtered_df[filtered_df["eid"].isin(eids)]
            daily = cdf.groupby("date")[measure].mean().reset_index()
            for _, row in daily.iterrows():
                timeline.append(
                    {
                        "date": row["date"].strftime("%Y-%m-%d"),
                        "cohort": cohort_name,
                        "value": round(float(row[measure]), 2),
                    }
                )

        return {
            "percentile": percentile,
            "total_animals": n,
            "top": cohort_stats(top),
            "bottom": cohort_stats(bottom),
            "show_mixed_warning": mixed,
            "timeline": timeline,
        }
