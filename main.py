from io import BytesIO
from typing import Any

from fpdf import FPDF
from litestar import Litestar, Response, post
from litestar.static_files import StaticFilesConfig
from litestar.config.cors import CORSConfig
from pydantic import BaseModel


class FieldItem(BaseModel):
    id: str
    caption: str
    fieldType: str
    required: bool = False
    fullLine: bool = False
    value: Any = None


class SyncPayload(BaseModel):
    formId: str
    formType: str
    fields: list[FieldItem]


def build_markdown(data: SyncPayload) -> str:
    lines = [
        f"# 表单反馈",
        "",
        f"**表单ID:** {data.formId}",
        f"**表单类型:** {data.formType}",
        "",
        "---",
        "",
        "## 字段详情",
        "",
        "| 控件标识 | 标题 | 控件类型 | 必填 | 值 |",
        "|----------|------|----------|------|----|",
    ]
    for f in data.fields:
        required = "是" if f.required else "否"
        val = str(f.value) if f.value is not None else ""
        lines.append(f"| {f.id} | {f.caption} | {f.fieldType} | {required} | {val} |")
    return "\n".join(lines)


def generate_pdf(data: SyncPayload, md_text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("SimSun", "", "C:/Windows/Fonts/simsun.ttc", uni=True)
    pdf.set_font("SimSun", "", 12)

    pdf.cell(0, 10, "表单反馈", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    pdf.set_font("SimSun", "", 10)
    pdf.cell(0, 8, f"表单ID: {data.formId}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"表单类型: {data.formType}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    col_widths = [40, 40, 35, 15, 55]
    headers = ["控件标识", "标题", "控件类型", "必填", "值"]
    pdf.set_font("SimSun", "", 9)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, align="C")
    pdf.ln()

    for f in data.fields:
        required = "是" if f.required else "否"
        val = str(f.value) if f.value is not None else ""
        row = [f.id, f.caption, f.fieldType, required, val]
        for i, cell in enumerate(row):
            pdf.cell(col_widths[i], 8, cell, border=1, align="C")
        pdf.ln()

    return pdf.output()


@post("/api/sync")
async def sync(data: SyncPayload) -> Response:
    md_text = build_markdown(data)
    pdf_bytes = generate_pdf(data, md_text)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={data.formId}.pdf"},
    )


cors_config = CORSConfig(
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    allow_credentials=False,
)

app = Litestar(
    route_handlers=[sync],
    cors_config=cors_config,
    static_files_config=[
        StaticFilesConfig(
            path="/static",
            directories=["static"],
            name="static")
    ]
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=12378)
