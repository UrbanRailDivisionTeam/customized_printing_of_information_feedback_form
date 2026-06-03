import logging
import os
import re
import tempfile
import traceback
from typing import Any

import win32com.client as win32
from litestar import Litestar, post
from litestar.response import Response
from litestar.static_files import StaticFilesConfig
from litestar.config.cors import CORSConfig
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# 模板文件路径（相对于 main1.py 所在目录）
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_BASE_DIR, "信息反馈单模版.doc")

# 模板标签（文档中的精确文本）→ 规范化的字段名（用于匹配前端传来的 caption）
# 文档结构（一个4行×8列的表）：
#   Row1: [主  题] [→值] [时间] [→值]
#   Row2: [大空白正文区，跨整行]
#   Row3: [经办人\n联系电话] [→值] [校对] [→值] [审核] [→值] [批准] [→值]
#   Row4: [送达部门签    收] [主送：\n抄送：\n呈：]
#   + 段落: "单据编号"（不在表格内）
TEMPLATE_LABELS = [
    ("单据编号", "单据编号"),
    ("主  题", "主题"),
    ("时间", "时间"),
    ("经办人", "经办人"),
    ("联系电话", "联系电话"),
    ("校对", "校对"),
    ("审核", "审核"),
    ("批准", "批准"),
    ("送达部门签    收", "送达部门签收"),
    ("主送：", "主送"),
    ("抄送：", "抄送"),
    ("呈：", "呈"),
]

# 正文字段名：这些字段的值填入中间大空白框
CONTENT_FIELD_NAMES = {"内容", "正文", "描述", "详情", "备注"}


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


def _normalize(s: str) -> str:
    """去空格、去冒号、去换行，用于字段名称匹配"""
    return re.sub(r"[\s：:\r\n]+", "", s)


# 字段 ID → 模板字段名 的硬映射（当 caption 无法匹配时回退到此映射）
FIELD_ID_MAP: dict[str, str] = {
    # 底部表格区域
    "crrc_userfield": "经办人",
    "crrc_textfield1": "联系电话",
    "crrc_userfield1": "校对",
    "crrc_userfield2": "审核",
    "crrc_userfield3": "批准",
    # 主送/抄送/呈
    "crrc_mulbasedatafield": "主送",
    "crrc_mulbasedatafield1": "抄送",
    "crrc_mulbasedatafield2": "呈",
    # 正文区
    "crrc_largetextfield": "内容",
}

# caption 规范化后可能匹配到的关键词 → 模板字段名
CAPTION_KEYWORDS: dict[str, str] = {
    "主题": "主题",
    "时间": "时间",
    "日期": "时间",
    "经办人": "经办人",
    "创建人": "经办人",
    "联系人": "经办人",
    "联系电话": "联系电话",
    "联系方式": "联系电话",
    "电话": "联系电话",
    "校对": "校对",
    "审核": "审核",
    "审批": "审核",
    "批准": "批准",
    "主送": "主送",
    "抄送": "抄送",
    "呈": "呈",
    "呈送": "呈",
    "送达": "送达部门签收",
    "签收": "送达部门签收",
    "内容": "内容",
    "正文": "内容",
    "描述": "内容",
    "详情": "内容",
    "备注": "内容",
    "单据编号": "单据编号",
}


def build_field_value_map(data: SyncPayload) -> dict[str, str]:
    """从表单数据构建 规范化字段名 → 值 的映射。优先按 ID 匹配，其次按 caption 关键词匹配"""
    value_map: dict[str, str] = {}
    for f in data.fields:
        val = str(f.value) if f.value is not None else ""
        if not val or val == "-":
            continue

        matched = False
        # 1) 优先用字段 ID 精确匹配
        if f.id in FIELD_ID_MAP:
            value_map[FIELD_ID_MAP[f.id]] = val
            matched = True

        # 2) 用 caption 关键词匹配（已有匹配则跳过避免覆盖 ID 映射）
        norm_caption = _normalize(f.caption)
        for kw, target in CAPTION_KEYWORDS.items():
            if kw in norm_caption and target not in value_map:
                value_map[target] = val
                matched = True
                break

        if not matched:
            logger.info(f"[MAP] 未匹配字段: id={f.id}, caption={f.caption}, value={val[:50]}")

    # formId 默认对应"单据编号"（如果前端没有传的话）
    if "单据编号" not in value_map:
        value_map["单据编号"] = data.formId

    logger.info(f"[MAP] 最终映射: {list(value_map.keys())}")
    return value_map


def fill_template_and_export_pdf(data: SyncPayload) -> bytes:
    """用 win32com 打开 Word 模板，将字段值填入标题右侧空白单元格，导出 PDF"""
    word = win32.Dispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0  # wdAlertsNone

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(f"模板文件不存在: {TEMPLATE_PATH}")

    doc = word.Documents.Open(TEMPLATE_PATH)

    try:
        value_map = build_field_value_map(data)
        table = doc.Tables(1)
        logger.info(f"[FILL] value_map keys: {list(value_map.keys())}")

        # 主送/抄送/呈 的值：将中文分号替换为顿号
        def _replace_semicolons(v: str) -> str:
            return v.replace("；", "、").replace(";", "、") if v else v

        for key in ("主送", "抄送", "呈"):
            if key in value_map:
                value_map[key] = _replace_semicolons(value_map[key])

        # ── Row 1: 主题 / 时间 ──
        if value_map.get("主题"):
            cell = table.Cell(1, 2)
            cell.Range.Text = value_map["主题"]
            # 去掉标黄（清除高亮）
            cell.Range.HighlightColorIndex = 0  # wdNoHighlight
        if value_map.get("时间"):
            table.Cell(1, 4).Range.Text = value_map["时间"]

        # ── Row 2: 中间大空白框（正文区）──
        # 第一行：主送：{值}（不缩进），正文从第二行开始
        main_send = value_map.get("主送", "")
        main_send_line = f"{main_send}：" if main_send else ""
        content_text = ""
        for f in data.fields:
            if _normalize(f.caption) in CONTENT_FIELD_NAMES and f.value:
                content_text = str(f.value)
                break
        if main_send_line and content_text:
            cell_text = main_send_line + "\n" + content_text
        elif main_send_line:
            cell_text = main_send_line
        elif content_text:
            cell_text = content_text
        else:
            cell_text = ""
        if cell_text:
            cell = table.Cell(2, 1)
            cell.Range.Text = cell_text
            for i, para in enumerate(cell.Range.Paragraphs):
                para.Range.Font.Name = "宋体"
                para.Range.Font.Size = 12
                para.LineSpacingRule = 5   # wdLineSpaceMultiple
                para.LineSpacing = 15      # 1.25 × 12pt = 15pt
                if i == 0 and main_send_line:
                    para.FirstLineIndent = 0  # 首行不缩进
                else:
                    para.FirstLineIndent = 24  # 2 字符缩进

        # ── Row 3: 经办人/联系电话 / 校对 / 审核 / 批准 ──
        person = value_map.get("经办人", "")
        # 联系电话可能匹配多种 caption：联系电话 / 联系人电话 / 电话
        phone_keys = ["联系电话", "联系人电话", "电话"]
        phone = ""
        for k in phone_keys:
            v = value_map.get(k, "")
            if v:
                phone = v
                break
        if person and phone:
            table.Cell(3, 2).Range.Text = f"{person}\n{phone}"
        elif person:
            table.Cell(3, 2).Range.Text = person
        elif phone:
            table.Cell(3, 2).Range.Text = phone
        logger.info(f"[FILL] 经办人={person}, 联系电话={phone}")
        if value_map.get("校对"):
            table.Cell(3, 4).Range.Text = value_map["校对"]
        if value_map.get("审核"):
            table.Cell(3, 6).Range.Text = value_map["审核"]
        if value_map.get("批准"):
            table.Cell(3, 8).Range.Text = value_map["批准"]

        # ── Row 4: 送达部门签收 / 主送/抄送/呈 ──
        if value_map.get("送达部门签收"):
            table.Cell(4, 1).Range.Text = "送达部门签    收  " + value_map["送达部门签收"]
        send_lines = []
        for label, key in [("主送：", "主送"), ("抄送：", "抄送"), ("呈：", "呈")]:
            v = value_map.get(key, "")
            send_lines.append(f"{label}{v}" if v else label)
        table.Cell(4, 2).Range.Text = "\n".join(send_lines)

        # ── 单据编号（不在表格内的段落）──
        # 替换"单据编号"文字为纯值，居右对齐，缩小字号保持一行
        rng = doc.Content
        rng.Find.Execute(FindText="单据编号", Forward=True, Wrap=0, MatchCase=False)
        if rng.Find.Found:
            doc_id = value_map.get("单据编号", "")
            doc_id = doc_id.replace("\r", "").replace("\n", "")
            rng.Text = doc_id
            para = rng.Paragraphs(1)
            para.Alignment = 2  # wdAlignParagraphRight
            rng.Font.Size = 14   # 缩小字号避免换行

        # ── 导出 PDF ──
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        doc.ExportAsFixedFormat(
            OutputFileName=tmp_path,
            ExportFormat=17,
            OpenAfterExport=False,
            OptimizeFor=0,
            Item=0,
            IncludeDocProps=False,
            KeepIRM=True,
            CreateBookmarks=0,
            DocStructureTags=True,
            BitmapMissingFonts=True,
            UseISO19005_1=False,
        )

        with open(tmp_path, "rb") as f:
            pdf_bytes = f.read()
        os.unlink(tmp_path)
        return pdf_bytes

    finally:
        doc.Close(False)
        word.Quit()


@post("/api/sync")
async def sync(data: SyncPayload) -> Response:
    logger.info(f"[SYNC] 收到请求: formId={data.formId}, formType={data.formType}, fields={len(data.fields)}")
    try:
        pdf_bytes = fill_template_and_export_pdf(data)
        logger.info(f"[SYNC] PDF 生成完成, 大小={len(pdf_bytes)} bytes")

        resp = Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={data.formId}.pdf"},
        )
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
    uvicorn.run("main:app", host="0.0.0.0", port=12377)
