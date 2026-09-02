from __future__ import annotations

import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.constants import MEASURE_LABELS, MEASURE_UNITS
from app.models.schemas import FilterState
from app.services.chart_service import DistributionService, TimeseriesService
from app.services.email_service import generate_filter_summary
from app.services.filter_service import FilterService
from app.services.summary_service import SummaryService


class ReportGenerator:
    @staticmethod
    def generate_chart_png(
        grouped_df: pd.DataFrame, chart_source: str, measure: str, filters: FilterState
    ) -> bytes:
        fig, ax = plt.subplots(figsize=(10, 5))
        if chart_source.lower() in ("time series", "timeseries"):
            result = TimeseriesService.compute(grouped_df, measure)
            for group in set(s["group"] for s in result["series"] if "(trend)" not in s["group"]):
                pts = [s for s in result["series"] if s["group"] == group]
                dates = [p["date"] for p in pts]
                values = [p["value"] for p in pts]
                ax.plot(dates, values, label=group, marker="o", markersize=3)
            ax.set_ylabel(result["y_label"])
            ax.set_title("Time Series")
            ax.legend(fontsize=8)
            plt.xticks(rotation=45, ha="right")
        elif chart_source.lower() == "distribution":
            result = DistributionService.compute(grouped_df, measure)
            for g in result["histogram"]["groups"]:
                ax.hist(g["values"], bins=result["histogram"]["bins"], alpha=0.5, label=g["group"])
            ax.axvline(result["histogram"]["mean"], color="#B08968", linestyle="--", label="Mean")
            ax.axvline(result["histogram"]["median"], color="#7B241C", linestyle=":", label="Median")
            ax.set_title("Distribution")
            ax.legend(fontsize=8)
        else:
            stats = SummaryService.compute_stats(grouped_df, measure)
            rows = [["Group", "Window", "Mean", "Count"]]
            for g in stats[:5]:
                for wk, w in g["windows"].items():
                    rows.append([g["full_group"][:30], w["label"], str(w["mean"]), str(w["count"])])
            ax.axis("off")
            table = ax.table(cellText=rows, loc="center", cellLoc="left")
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            ax.set_title("Summary Statistics")

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def generate_pdf(
        filters: FilterState,
        grouped_df: pd.DataFrame,
        charts: list[str],
        farm_name: str,
    ) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph(f"<b>Livestock Report — {farm_name}</b>", styles["Title"]))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]))
        story.append(Spacer(1, 12))

        summary = generate_filter_summary(filters.model_dump())
        filter_rows = [[k.title(), v] for k, v in summary.items()]
        if filter_rows:
            t = Table([["Filter", "Value"]] + filter_rows)
            t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B4332")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ]
                )
            )
            story.append(Paragraph("<b>Filters Applied</b>", styles["Heading2"]))
            story.append(t)
            story.append(Spacer(1, 12))

        measure = filters.measure
        if "Summary Statistics" in charts or "Summary" in charts:
            stats = SummaryService.compute_stats(grouped_df, measure)
            story.append(Paragraph("<b>Summary Statistics</b>", styles["Heading2"]))
            for g in stats[:3]:
                story.append(Paragraph(g["full_group"], styles["Heading3"]))
                rows = [["Window", "Mean", "Min", "Max", "Median", "Count"]]
                for w in g["windows"].values():
                    rows.append(
                        [w["label"], str(w["mean"]), str(w["min"]), str(w["max"]), str(w["median"]), str(w["count"])]
                    )
                tbl = Table(rows)
                tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
                story.append(tbl)
                story.append(Spacer(1, 8))

        unit = MEASURE_UNITS.get(measure, "")
        story.append(
            Paragraph(
                f"<i>Measure: {MEASURE_LABELS.get(measure, measure)} ({unit})</i>",
                styles["Normal"],
            )
        )

        doc.build(story)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def generate_html(
        filters: FilterState,
        grouped_df: pd.DataFrame,
        charts: list[str],
        farm_name: str,
    ) -> str:
        summary = generate_filter_summary(filters.model_dump())
        items = "".join(f"<li><b>{k.title()}:</b> {v}</li>" for k, v in summary.items())
        stats_html = ""
        if grouped_df is not None and not grouped_df.empty:
            stats = SummaryService.compute_stats(grouped_df, filters.measure)
            for g in stats[:3]:
                stats_html += f"<h3>{g['full_group']}</h3><table border='1' cellpadding='4'>"
                stats_html += "<tr><th>Window</th><th>Mean</th><th>Count</th></tr>"
                for w in g["windows"].values():
                    stats_html += f"<tr><td>{w['label']}</td><td>{w['mean']}</td><td>{w['count']}</td></tr>"
                stats_html += "</table>"
        return f"""<!DOCTYPE html>
<html><head><title>{farm_name} Report</title>
<style>body{{font-family:Poppins,sans-serif;color:#2c3e50;padding:2rem;}}
h1{{color:#1B4332;}}</style></head>
<body>
<h1>Livestock Report — {farm_name}</h1>
<p>Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
<h2>Filters</h2><ul>{items}</ul>
{stats_html}
</body></html>"""
