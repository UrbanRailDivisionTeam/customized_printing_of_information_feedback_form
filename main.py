import logging
import traceback
from io import BytesIO
from typing import Any

from fpdf import FPDF
from litestar import Litestar, post
from litestar.response import Response, Stream
from litestar.static_files import StaticFilesConfig
from litestar.config.cors import CORSConfig
from pydantic import BaseModel

logger = logging.getLogger(__name__)


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


FONT_PATHS = {
    "Heiti": "C:/Windows/Fonts/simhei.ttf",
    "Fangsong": "C:/Windows/Fonts/simfang.ttf",
    "SimSun": "C:/Windows/Fonts/simsun.ttc",
}


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


def _load_fonts(pdf: FPDF):
    import os
    for name, path in FONT_PATHS.items():
        if os.path.exists(path):
            pdf.add_font(name, "", path)
    return "Fangsong"  # Default font


def get_field_value(fields: list[FieldItem], key: str, default: str = "") -> str:
    for f in fields:
        if f.id == key or f.caption == key:
            return str(f.value) if f.value is not None else default
    return default


class MyFPDF(FPDF):
    def footer(self):
        self.set_y(-25) # Position at 25 units from bottom
        self.set_font("Fangsong", "", 15)
        self.cell(0, 10, "中车株洲电力机车有限公司", new_x="LMARGIN", new_y="NEXT", align="R")

def generate_pdf(data: SyncPayload, md_text: str) -> bytes:
    pdf = MyFPDF()
    pdf.add_page()
    _load_fonts(pdf)

    # Margins
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)

    # 0. Logo
    import os
    logo_path = "logo_1.jpeg"
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=20, y=5, w=40)
    
    pdf.ln(10)

    # 1. Title Section
    # 城轨制造中心 (SimHei, Xiao Er = 18pt)
    pdf.set_font("Heiti", "", 18)
    pdf.cell(0, 15, "城轨制造中心", new_x="LMARGIN", new_y="NEXT", align="C")

    # 信息反馈单 (SimHei, Xiao Yi = 24pt)
    pdf.set_font("Heiti", "", 24)
    pdf.cell(0, 20, "信 息 反 馈 单", new_x="LMARGIN", new_y="NEXT", align="C")

    # 单据编号 (Fangsong, Si Hao = 14pt)
    bill_no = get_field_value(data.fields, "billno", get_field_value(data.fields, "单据编号"))
    pdf.set_font("Fangsong", "", 14)
    pdf.cell(0, 10, f"{bill_no}", new_x="LMARGIN", new_y="NEXT", align="R")

    # 2. Table Section (Fangsong, Xiao Si = 12pt)
    pdf.set_font("Fangsong", "", 12)
    line_height = 10
    table_width = pdf.w - 40 # 210 - 20 - 20 = 170

    # Row 1: 主题 | [value] | 时间 | [value]
    pdf.set_font("Heiti", "", 12)
    pdf.cell(20, line_height, "主 题", border=1, align="C")
    pdf.set_font("Heiti", "", 12) # Value of Subject bold
    subject = get_field_value(data.fields, "crrc_textfield", get_field_value(data.fields, "主题"))
    pdf.cell(90, line_height, subject, border=1, align="L")
    pdf.set_font("Heiti", "", 12) # Label Time bold
    pdf.cell(20, line_height, "时 间", border=1, align="C")
    pdf.set_font("Heiti", "", 12) # Value of Time bold
    date_val = get_field_value(data.fields, "crrc_datefield", get_field_value(data.fields, "时间"))
    pdf.cell(40, line_height, date_val, border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    # Row 2 & 3: 主送 and 内容 (Merged cell, NO label box)
    pdf.set_font("Heiti", "", 12)
    
    # Get values and replace delimiters
    primary_recipient = get_field_value(data.fields, "crrc_mulbasedatafield", get_field_value(data.fields, "主送")).replace(";", "、").replace("；", "、")
    content_val = get_field_value(data.fields, "crrc_largetextfield", get_field_value(data.fields, "内容")).strip()
    
    # Prepare text for multi_cell
    merged_text = f"{primary_recipient}：\n{content_val}"

    # Draw the content part full width
    x_start_merged = pdf.get_x()
    y_start_merged = pdf.get_y()
    
    pdf.set_font("Fangsong", "", 12) # Content body not bold
    
    # Use multi_cell to draw the content box spanning full table width
    pdf.multi_cell(table_width, line_height, merged_text, border=1, align="L")
    y_end_merged = pdf.get_y()
    
    # Enforce minimum 150pt content box height to fill A4 page
    # If content is too short, draw an empty cell with LRB borders to extend the box
    content_rendered = y_end_merged - y_start_merged
    if content_rendered < 150:
        pdf.cell(table_width, 150 - content_rendered, "", border="LRB", 
                 new_x="LMARGIN", new_y="NEXT")
        y_end_merged = pdf.get_y()
    
    pdf.set_y(y_end_merged)

    # Row 4 & 5: Handler and others
    x_start = pdf.get_x()
    y_start = pdf.get_y()

    # Column 1: Labels (Stacked) - Bold
    pdf.set_font("Heiti", "", 11)
    pdf.cell(20, line_height / 2, "经 办 人", border="LTR", align="C")
    pdf.set_xy(x_start, y_start + line_height / 2)
    pdf.cell(20, line_height / 2, "联系电话", border="LBR", align="C")

    # Column 2: Values (Stacked)
    handler = get_field_value(data.fields, "crrc_userfield", get_field_value(data.fields, "经办人"))
    phone = get_field_value(data.fields, "crrc_textfield1", get_field_value(data.fields, "联系电话"))
    pdf.set_font("Fangsong", "", 11)
    pdf.set_xy(x_start + 20, y_start)
    pdf.cell(40, line_height / 2, handler, border="TR", align="C")
    pdf.set_xy(x_start + 20, y_start + line_height / 2)
    pdf.cell(40, line_height / 2, phone, border="BR", align="C")

    # Columns 3-8: 校对, 审核, 批准 - Labels Bold
    pdf.set_xy(x_start + 60, y_start)
    pdf.set_font("Heiti", "", 12)
    pdf.cell(15, line_height, "校对", border=1, align="C")
    pdf.set_font("Fangsong", "", 12)
    checker = get_field_value(data.fields, "crrc_userfield1", get_field_value(data.fields, "校对"))
    pdf.cell(20, line_height, checker, border=1, align="C")
    pdf.set_font("Heiti", "", 12)
    pdf.cell(15, line_height, "审核", border=1, align="C")
    pdf.set_font("Fangsong", "", 12)
    reviewer = get_field_value(data.fields, "crrc_userfield2", get_field_value(data.fields, "审核"))
    pdf.cell(25, line_height, reviewer, border=1, align="C")
    pdf.set_font("Heiti", "", 12)
    pdf.cell(15, line_height, "批准", border=1, align="C")
    pdf.set_font("Fangsong", "", 12)
    approver = get_field_value(data.fields, "crrc_userfield3", get_field_value(data.fields, "批准"))
    pdf.cell(20, line_height, approver, border=1, align="C", new_x="LMARGIN", new_y="NEXT")

    # Row 6: 送达部门签收
    y_start_row6 = pdf.get_y()
    x_start_row6 = pdf.get_x()

    # Right content text and replace delimiters
    v_zs = get_field_value(data.fields, "crrc_mulbasedatafield", get_field_value(data.fields, "送达主送")).replace(";", "、").replace("；", "、")
    v_cs = get_field_value(data.fields, "crrc_mulbasedatafield1", get_field_value(data.fields, "送达抄送")).replace(";", "、").replace("；", "、")
    v_ls = get_field_value(data.fields, "crrc_mulbasedatafield2", get_field_value(data.fields, "送达呈送")).replace(";", "、").replace("；", "、")
    right_content_text = f"主送：{v_zs}\n抄送：{v_cs}\n呈送：{v_ls}"

    # Draw right side first to determine height
    pdf.set_xy(x_start_row6 + 20, y_start_row6)
    pdf.set_font("Fangsong", "", 11)
    pdf.multi_cell(table_width - 20, line_height, right_content_text, border=1, align="L")
    y_after_right_mc = pdf.get_y()
    
    total_sign_height = y_after_right_mc - y_start_row6

    # Draw left label cell with the SAME height - Bold
    pdf.set_xy(x_start_row6, y_start_row6)
    pdf.set_font("Heiti", "", 11)
    # Using a single cell or multi_cell with the total height to avoid splitting
    pdf.multi_cell(20, total_sign_height / 2, "送达部门\n签    收", border=1, align="C")

    # Set final Y
    pdf.set_y(y_after_right_mc)

    return bytes(pdf.output())


@post("/api/sync")
async def sync(data: SyncPayload) -> Response:
    logger.info(f"[SYNC] 收到请求: formId={data.formId}, formType={data.formType}, fields={len(data.fields)}")
    try:
        md_text = build_markdown(data)
        logger.info(f"[SYNC] Markdown 生成完成, 长度={len(md_text)}")
        pdf_bytes = generate_pdf(data, md_text)
        logger.info(f"[SYNC] PDF 生成完成, 大小={len(pdf_bytes)} bytes")

        resp = Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={data.formId}.pdf"},
        )
        logger.info(f"[SYNC] Response 构造成功, 准备返回")
        return resp
    except Exception as e:
        logger.error(f"[SYNC] 处理失败: {e}\n{traceback.format_exc()}")
        return Response(
            content=f'{{"status": "error", "message": "{e}"}}'.encode(),
            media_type="application/json",
            status_code=500,
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
