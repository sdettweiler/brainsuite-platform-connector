"""
Export service: generates PDF, Excel, and CSV exports from harmonized data.
"""
import io
import csv
import logging
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Field definitions for export
DIMENSION_FIELDS = {
    "ad_name": "Ad Name",
    "campaign_name": "Campaign Name",
    "campaign_objective": "Campaign Objective",
    "platform": "Platform",
    "ad_account_id": "Ad Account ID",
    "asset_format": "Format",
    "report_date": "Date",
}

PERFORMANCE_KPI_FIELDS = {
    "spend": "Spend",
    "impressions": "Impressions",
    "clicks": "Clicks",
    "ctr": "CTR (%)",
    "cpm": "CPM",
    "conversions": "Conversions",
    "conversion_value": "Conversion Value",
    "cvr": "CVR (%)",
    "roas": "ROAS",
    "reach": "Reach",
    "frequency": "Frequency",
    "video_views": "Video Views",
    "vtr": "VTR (%)",
    "video_completion_rate": "Video Completion Rate (%)",
    "cost_per_view": "Cost per View",
}

BRAINSUITE_KPI_FIELDS = {
    "ace_score": "ACE Score",
    "attention_score": "Attention Score",
    "brand_score": "Brand Score",
    "emotion_score": "Emotion Score",
    "message_clarity": "Message Clarity",
    "visual_impact": "Visual Impact",
}

DEFAULT_EXPORT_FIELDS = [
    "ad_name", "platform", "campaign_name", "asset_format",
    "spend", "impressions", "ctr", "roas", "ace_score",
]


class ExportService:

    def get_available_fields(self) -> Dict[str, Dict[str, str]]:
        return {
            "dimensions": DIMENSION_FIELDS,
            "performance_kpis": PERFORMANCE_KPI_FIELDS,
            "brainsuite_kpis": BRAINSUITE_KPI_FIELDS,
        }

    def prepare_rows(
        self,
        assets: List[Dict[str, Any]],
        fields: List[str],
        date_from: date,
        date_to: date,
    ) -> List[Dict[str, Any]]:
        """Build export rows from asset data aggregated over date range."""
        rows = []
        all_fields = {**DIMENSION_FIELDS, **PERFORMANCE_KPI_FIELDS, **BRAINSUITE_KPI_FIELDS}

        for asset in assets:
            row = {}
            perf = asset.get("performance", {}) or {}
            brainsuite = asset.get("brainsuite_metadata", {}) or {}

            for field in fields:
                if field in DIMENSION_FIELDS:
                    row[all_fields[field]] = asset.get(field, "")
                elif field in PERFORMANCE_KPI_FIELDS:
                    val = perf.get(field)
                    if val is not None and isinstance(val, (Decimal, float)):
                        val = round(float(val), 4)
                    row[all_fields[field]] = val
                elif field in BRAINSUITE_KPI_FIELDS:
                    if field == "ace_score":
                        row[all_fields[field]] = asset.get("ace_score")
                    else:
                        row[all_fields[field]] = brainsuite.get(field)
            rows.append(row)

        return rows

    def generate_csv(self, rows: List[Dict[str, Any]]) -> bytes:
        if not rows:
            return b""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue().encode("utf-8-sig")

    def generate_excel(self, rows: List[Dict[str, Any]], sheet_name: str = "Export") -> bytes:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise RuntimeError("openpyxl not installed")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        if not rows:
            output = io.BytesIO()
            wb.save(output)
            return output.getvalue()

        headers = list(rows[0].keys())

        # Header styling
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1B2A47", end_color="1B2A47", fill_type="solid")

        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        # Data rows
        for row_idx, row in enumerate(rows, 2):
            for col_idx, header in enumerate(headers, 1):
                ws.cell(row=row_idx, column=col_idx, value=row.get(header))

        # Auto-width
        for col_idx, header in enumerate(headers, 1):
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].width = max(len(header) + 4, 12)

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()

    def generate_pdf(self, rows: List[Dict[str, Any]], title: str = "Brainsuite Export") -> bytes:
        try:
            from reportlab.lib.pagesizes import landscape, A4
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib import colors
        except ImportError:
            raise RuntimeError("reportlab not installed")

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=landscape(A4), topMargin=20, bottomMargin=20)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph(title, styles["Title"]))
        elements.append(Spacer(1, 12))

        if not rows:
            elements.append(Paragraph("No data available.", styles["Normal"]))
            doc.build(elements)
            return output.getvalue()

        headers = list(rows[0].keys())
        table_data = [headers]
        for row in rows:
            table_data.append([str(row.get(h, "")) for h in headers])

        col_width = (landscape(A4)[0] - 40) / len(headers)
        table = Table(table_data, colWidths=[col_width] * len(headers))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1B2A47")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        elements.append(table)
        doc.build(elements)
        return output.getvalue()


export_service = ExportService()
