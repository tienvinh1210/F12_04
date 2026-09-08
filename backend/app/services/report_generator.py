from __future__ import annotations

import base64
import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.constants import MEASURE_LABELS, MEASURE_UNITS
from app.models.schemas import FilterState
from app.services.chart_service import CohortService, DistributionService, TimeseriesService
from app.services.email_service import generate_filter_summary
from app.services.summary_service import SummaryService


def _normalize_chart_name(name: str) -> str:
    key = (name or "").strip().lower().replace("_", " ")
    if key in ("summary statistics", "summary", "stats"):
        return "summary"
    if key in ("time series", "timeseries", "ts"):
        return "timeseries"
    if key in ("distribution", "distributions", "hist", "histogram"):
        return "distribution"
    if key in ("cohorts", "cohort"):
        return "cohorts"
    return key


def _to_datetimes(values: list) -> list[datetime]:
    out: list[datetime] = []
    for v in values:
        if isinstance(v, datetime):
            out.append(v)
        else:
            out.append(pd.to_datetime(v).to_pydatetime())
    return out


def _format_time_axis(ax, n_points: int) -> None:
    """Keep x-axis date labels readable (max ~6–8 ticks)."""
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    if n_points <= 14:
        formatter = mdates.DateFormatter("%d %b")
    elif n_points <= 90:
        formatter = mdates.DateFormatter("%d %b")
    else:
        formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.tick_params(axis="x", labelsize=8)
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_horizontalalignment("right")


class ReportGenerator:
    @staticmethod
    def generate_chart_png(
        grouped_df: pd.DataFrame,
        chart_source: str,
        measure: str,
        filters: FilterState,
        filtered_df: pd.DataFrame | None = None,
    ) -> bytes:
        fig, ax = plt.subplots(figsize=(10, 5))
        kind = _normalize_chart_name(chart_source)
        filtered_df = filtered_df if filtered_df is not None else grouped_df
        y_label = MEASURE_LABELS.get(measure, measure)

        if kind == "timeseries":
            result = TimeseriesService.compute(grouped_df, measure)
            n_points = 0
            for group in sorted(
                {s["group"] for s in result["series"] if "(trend)" not in s["group"]}
            ):
                pts = sorted(
                    (s for s in result["series"] if s["group"] == group),
                    key=lambda p: p["date"],
                )
                dates = _to_datetimes([p["date"] for p in pts])
                values = [p["value"] for p in pts]
                n_points = max(n_points, len(dates))
                ax.plot(dates, values, label=group, marker="o", markersize=2.5, linewidth=1.5)
            ax.set_ylabel(y_label)
            ax.set_title("Time Series")
            ax.legend(fontsize=8)
            if n_points:
                _format_time_axis(ax, n_points)
        elif kind == "distribution":
            result = DistributionService.compute(grouped_df, measure)
            for g in result["histogram"]["groups"]:
                ax.hist(g["values"], bins=result["histogram"]["bins"], alpha=0.5, label=g["group"])
            ax.axvline(result["histogram"]["mean"], color="#B08968", linestyle="--", label="Mean")
            ax.axvline(result["histogram"]["median"], color="#7B241C", linestyle=":", label="Median")
            ax.set_xlabel(y_label)
            ax.set_title("Distribution")
            ax.legend(fontsize=8)
        elif kind == "cohorts":
            result = CohortService.analyze(filtered_df, grouped_df, measure, 10, filters)
            n_points = 0
            for cohort_name in ("top", "bottom"):
                pts = [t for t in result["timeline"] if t["cohort"] == cohort_name]
                if not pts:
                    continue
                pts = sorted(pts, key=lambda p: p["date"])
                dates = _to_datetimes([p["date"] for p in pts])
                n_points = max(n_points, len(dates))
                ax.plot(
                    dates,
                    [p["value"] for p in pts],
                    label=f"{cohort_name.title()} {result['percentile']}%",
                    marker="o",
                    markersize=2.5,
                    linewidth=1.5,
                )
            ax.set_title(f"Cohorts (top/bottom {result['percentile']}%)")
            ax.set_ylabel(y_label)
            ax.legend(fontsize=8)
            if n_points:
                _format_time_axis(ax, n_points)
            if not result["timeline"]:
                ax.axis("off")
                ax.text(0.5, 0.5, "No cohort data for current filters", ha="center", va="center")
        else:
            stats = SummaryService.compute_stats(grouped_df, measure)
            rows = [["Group", "Window", "Mean", "Count"]]
            for g in stats[:5]:
                for _, w in g["windows"].items():
                    rows.append([g["full_group"][:30], w["label"], str(w["mean"]), str(w["count"])])
            ax.axis("off")
            table = ax.table(cellText=rows, loc="center", cellLoc="left")
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            ax.set_title("Summary Statistics")

        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def _append_summary_tables(story, styles, grouped_df: pd.DataFrame, measure: str) -> None:
        stats = SummaryService.compute_stats(grouped_df, measure)
        story.append(Paragraph("<b>Summary Statistics</b>", styles["Heading2"]))
        if not stats:
            story.append(Paragraph("No summary data for current filters.", styles["Normal"]))
            return
        for g in stats[:5]:
            story.append(Paragraph(g["full_group"], styles["Heading3"]))
            rows = [["Window", "Mean", "Min", "Max", "Median", "Count"]]
            for w in g["windows"].values():
                rows.append(
                    [
                        w["label"],
                        str(w["mean"]),
                        str(w["min"]),
                        str(w["max"]),
                        str(w["median"]),
                        str(w["count"]),
                    ]
                )
            tbl = Table(rows)
            tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
            story.append(tbl)
            story.append(Spacer(1, 8))

    @staticmethod
    def _append_cohort_tables(story, styles, filtered_df, grouped_df, filters, measure: str) -> None:
        result = CohortService.analyze(filtered_df, grouped_df, measure, 10, filters)
        story.append(Paragraph("<b>Cohorts</b>", styles["Heading2"]))
        story.append(
            Paragraph(
                f"Top/bottom {result['percentile']}% of {result['total_animals']} animals",
                styles["Normal"],
            )
        )
        for label, block in (("Top", result["top"]), ("Bottom", result["bottom"])):
            story.append(Paragraph(f"<b>{label} cohort</b>", styles["Heading3"]))
            rows = [
                ["Count", "Average", "Min", "Max"],
                [
                    str(block["count"]),
                    str(block["average"]),
                    str(block["min"]),
                    str(block["max"]),
                ],
            ]
            tbl = Table(rows)
            tbl.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
            story.append(tbl)
            story.append(Spacer(1, 6))

    @staticmethod
    def generate_pdf(
        filters: FilterState,
        grouped_df: pd.DataFrame,
        charts: list[str],
        farm_name: str,
        filtered_df: pd.DataFrame | None = None,
    ) -> bytes:
        filtered_df = filtered_df if filtered_df is not None else grouped_df
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=0.75 * inch, rightMargin=0.75 * inch)
        styles = getSampleStyleSheet()
        story = []
        measure = filters.measure
        selected = [_normalize_chart_name(c) for c in (charts or [])]
        # Preserve user order while deduping
        ordered: list[str] = []
        for c in selected:
            if c and c not in ordered:
                ordered.append(c)
        if not ordered:
            ordered = ["summary", "timeseries", "distribution"]

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

        unit = MEASURE_UNITS.get(measure, "")
        story.append(
            Paragraph(
                f"<i>Measure: {MEASURE_LABELS.get(measure, measure)} ({unit})</i>",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 12))

        img_width = 6.5 * inch
        for kind in ordered:
            if kind == "summary":
                ReportGenerator._append_summary_tables(story, styles, grouped_df, measure)
                story.append(Spacer(1, 12))
                continue

            title = {
                "timeseries": "Time Series",
                "distribution": "Distribution",
                "cohorts": "Cohorts",
            }.get(kind, kind.title())
            story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))

            if kind == "cohorts":
                ReportGenerator._append_cohort_tables(
                    story, styles, filtered_df, grouped_df, filters, measure
                )

            try:
                png = ReportGenerator.generate_chart_png(
                    grouped_df, kind, measure, filters, filtered_df=filtered_df
                )
                img = Image(io.BytesIO(png), width=img_width, height=3.2 * inch, kind="proportional")
                story.append(img)
            except Exception as exc:
                story.append(
                    Paragraph(f"<i>Could not render {title} chart: {exc}</i>", styles["Normal"])
                )
            story.append(Spacer(1, 14))

        doc.build(story)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def generate_html(
        filters: FilterState,
        grouped_df: pd.DataFrame,
        charts: list[str],
        farm_name: str,
        filtered_df: pd.DataFrame | None = None,
    ) -> str:
        filtered_df = filtered_df if filtered_df is not None else grouped_df
        summary = generate_filter_summary(filters.model_dump())
        items = "".join(f"<li><b>{k.title()}:</b> {v}</li>" for k, v in summary.items())
        measure = filters.measure
        selected = [_normalize_chart_name(c) for c in (charts or [])]
        ordered: list[str] = []
        for c in selected:
            if c and c not in ordered:
                ordered.append(c)
        if not ordered:
            ordered = ["summary", "timeseries", "distribution"]

        sections = []
        for kind in ordered:
            if kind == "summary":
                stats_html = "<h2>Summary Statistics</h2>"
                if grouped_df is not None and not grouped_df.empty:
                    stats = SummaryService.compute_stats(grouped_df, measure)
                    for g in stats[:5]:
                        stats_html += f"<h3>{g['full_group']}</h3><table border='1' cellpadding='4'>"
                        stats_html += "<tr><th>Window</th><th>Mean</th><th>Min</th><th>Max</th><th>Median</th><th>Count</th></tr>"
                        for w in g["windows"].values():
                            stats_html += (
                                f"<tr><td>{w['label']}</td><td>{w['mean']}</td><td>{w['min']}</td>"
                                f"<td>{w['max']}</td><td>{w['median']}</td><td>{w['count']}</td></tr>"
                            )
                        stats_html += "</table>"
                sections.append(stats_html)
                continue

            title = {
                "timeseries": "Time Series",
                "distribution": "Distribution",
                "cohorts": "Cohorts",
            }.get(kind, kind.title())
            try:
                png = ReportGenerator.generate_chart_png(
                    grouped_df, kind, measure, filters, filtered_df=filtered_df
                )
                b64 = base64.b64encode(png).decode("ascii")
                sections.append(
                    f"<h2>{title}</h2><img alt='{title}' style='max-width:100%' src='data:image/png;base64,{b64}'/>"
                )
            except Exception as exc:
                sections.append(f"<h2>{title}</h2><p><i>Could not render chart: {exc}</i></p>")

        body = "\n".join(sections)
        return f"""<!DOCTYPE html>
<html><head><title>{farm_name} Report</title>
<style>body{{font-family:Poppins,sans-serif;color:#2c3e50;padding:2rem;}}
h1,h2{{color:#1B4332;}} table{{border-collapse:collapse;margin-bottom:1rem;}}</style></head>
<body>
<h1>Livestock Report — {farm_name}</h1>
<p>Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
<p><i>Measure: {MEASURE_LABELS.get(measure, measure)}</i></p>
<h2>Filters</h2><ul>{items}</ul>
{body}
</body></html>"""
