from __future__ import annotations

import pandas as pd

from app.models.schemas import FilterState
from app.services.filter_service import FilterService


class DataService:
    @staticmethod
    def get_filtered_data(filters: FilterState, is_admin: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, int]:
        base_df = FilterService.load_farm_dataframe(filters.farm_id)
        total_records = len(base_df)
        filtered = FilterService.filter_data(base_df, filters, is_admin)
        grouped = FilterService.build_grouped_data(filtered, filters, is_admin)
        return filtered, grouped, base_df, total_records

    @staticmethod
    def get_grouped_data(filters: FilterState, is_admin: bool) -> pd.DataFrame:
        filtered, grouped, _, _ = DataService.get_filtered_data(filters, is_admin)
        return grouped

    @staticmethod
    def get_common_note(filters: FilterState, grouped: pd.DataFrame) -> str | None:
        return FilterService.get_common_filters_note(filters, grouped)
