# Fix Fangsong Bold + Content Layout

## TL;DR

> **Quick Summary**: 修复 main.py PDF 生成中 Fangsong 字体无法加粗的问题（替换为 SimHei 黑体），同时优化内容框排版（去空白行 + 最低高度），避免 A4 纸底部大面积留白。
>
> **Deliverables**:
> - 10 处 Fangsong Bold → SimHei 字体替换
> - _load_fonts 死代码清理
> - 内容值首尾空白行 strip
> - 内容框最低高度 150pt 约束
>
> **Estimated Effort**: Quick
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 → Task 2 (same file, safer sequential)

---

## Context

### Original Request
用户反馈 `main.py` 第 121-130 行 PDF 生成中字体无法加粗。经排查，根因是 Fangsong（仿宋）字体 `simfang.ttf` 仅含 Regular 字重，而 fpdf2 对 `add_font()` 加载的自定义 TTF 不自动模拟 Bold。后续追加需求：内容输出前去除首尾空白行，设置内容框最低高度以优化 A4 排版。

### Interview Summary
**Key Discussions**:
- **修复方案**: 用户选择方案 B — 用 SimHei（黑体）天然粗笔画替代 Fangsong Bold
- **范围变更**: 初始仅 121-130 行 → Metis 发现与 _load_fonts 清理冲突 → 用户选择全文统一修复（10 处全部替换）
- **附带清理**: _load_fonts 中 `add_font(name, "B", path)` 死代码一并移除
- **内容布局**: strip 首尾空白行 + 内容框最低高度 150pt

**Research Findings**:
- fpdf2 v2.8+ 对自定义 TTF 字体不模拟 Bold（与核心字体行为不同）
- SimHei 已被代码在标题处使用（103, 107 行），复用无新增风险
- 10 处 Fangsong Bold 分布在 121, 123, 126, 128, 133, 160, 176, 181, 186, 212 行（Oracle 核实）

### Metis Review
**Identified Gaps** (addressed):
- **CRITICAL**: 只改 121-130 行 + 清理 _load_fonts 会崩溃 → 用户升级为全文修复 → 方案 B
- **Line off-by-one**: 132 → 133（Oracle 修正，132 行是注释）

---

## Work Objectives

### Core Objective
修复 PDF 中 10 处 Fangsong Bold 无法加粗的缺陷，并优化内容框排版使其适配 A4 纸。

### Concrete Deliverables
- `main.py`: 10 行 `set_font("Fangsong", "B", ...)` → `set_font("Heiti", "", ...)`
- `main.py`: `_load_fonts()` 移除 `pdf.add_font(name, "B", path)` 
- `main.py`: `content_val` 增加 `.strip()`
- `main.py`: 内容 `multi_cell` 增加最低高度 150pt 约束

### Definition of Done
- [ ] 所有 Fangsong Bold 引用已替换为 Heiti
- [ ] `_load_fonts` 不再注册 Bold 样式的伪粗体
- [ ] 内容值前后无空白行
- [ ] 内容框高度 ≥ 150pt

### Must Have
- `set_font("Fangsong", "B", ...)` 0 处残留（grep 验证）
- PDF 生成不崩溃
- 非 Bold Fangsong 正文不受影响

### Must NOT Have (Guardrails)
- 不修改非 Bold 的 Fangsong 正文（lines 116, 146, 168, 178, 183, 188, 204）
- 不修改函数签名（`generate_pdf`, `_load_fonts`）
- 不新增字体文件依赖
- 不添加验证代码/测试框架

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed.

### Test Decision
- **Infrastructure exists**: NO
- **Automated tests**: None (user selected "暂不验证")
- **Agent-Executed QA**: MANDATORY for all tasks

### QA Policy
- **PDF 完整性**: 启动服务 → POST 测试数据 → 验证 PDF 生成成功（HTTP 200 + Content-Type: application/pdf）
- **代码验证**: grep 验证无残留 Fangsong Bold 引用

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (串行 — 同文件编辑):
├── Task 1: 字体修复 + _load_fonts 清理 [quick]
└── Task 2: 内容布局优化 [quick]

Wave FINAL: 已跳过（用户选择暂不验证）
```

**Critical Path**: Task 1 → Task 2
**Parallel Speedup**: N/A (同文件，顺序执行保证不冲突)

### Agent Dispatch Summary

- **Wave 1**: **1 agent** - Task 1 → Task 2 (sequential, 同文件)

---

## TODOs

- [x] 1. 字体修复：10 处 Fangsong Bold → SimHei + _load_fonts 清理

  **What to do**:
  - 将以下 10 处的 `set_font("Fangsong", "B", ...)` 替换为 `set_font("Heiti", "", ...)`，保持原字号不变：
    - 121: `set_font("Heiti", "", 12)` — "主 题" 标签
    - 123: `set_font("Heiti", "", 12)` — 主题的值
    - 126: `set_font("Heiti", "", 12)` — "时 间" 标签
    - 128: `set_font("Heiti", "", 12)` — 时间的值
    - 133: `set_font("Heiti", "", 12)` — 主送/内容段前（会被 146 行覆盖，但为一致性替换）
    - 160: `set_font("Heiti", "", 11)` — "经 办 人" / "联系电话" 标签
    - 176: `set_font("Heiti", "", 12)` — "校对" 标签
    - 181: `set_font("Heiti", "", 12)` — "审核" 标签
    - 186: `set_font("Heiti", "", 12)` — "批准" 标签
    - 212: `set_font("Heiti", "", 11)` — "送达部门签收" 标签
  - 在 `_load_fonts()` 函数（第 59-68 行）中：
    - 删除第 67 行 `pdf.add_font(name, "B", path)`
    - 删除第 64-66 行的误导性注释（声称 fpdf2 可模拟 Bold）

  **Must NOT do**:
  - 不修改任何 `set_font("Fangsong", "", ...)` 调用（正文部分）
  - 不修改 SimSun Bold 注册（SimSun Bold 从未被使用，顺手删除无影响但超出范围）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 机械性替换操作，单文件 10 处统一变更，无复杂逻辑
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `git-master`: 提交策略简单，无需高级 git 操作

  **Parallelization**:
  - **Can Run In Parallel**: NO (与 Task 2 同文件，顺序执行)
  - **Parallel Group**: Wave 1 (顺序)
  - **Blocks**: Task 2（内容布局）
  - **Blocked By**: None

  **References**:
  - `main.py:32-35` — FONT_PATHS 定义，确认 Heiti 字体路径存在
  - `main.py:103,107` — 现有 Heiti 使用模式，作为替换参考
  - `main.py:59-68` — _load_fonts 函数，确认删除范围
  - `main.py:116,146,168,178,183,188,204` — 所有 `set_font("Fangsong", "", ...)` 的位置，确保不被误改

  **Acceptance Criteria**:
  - [ ] `grep -n 'Fangsong.*"B"' main.py` → 0 matches
  - [ ] `grep -n 'Heiti.*""' main.py` → 至少 12 matches（2 个标题 + 10 个标签）
  - [ ] `grep -n 'pdf.add_font.*"B"' main.py` → 0 matches（_load_fonts 清理）
  - [ ] PDF 生成不崩溃：`uv run python -c "from main import generate_pdf, build_markdown, SyncPayload, FieldItem; p = SyncPayload(formId='test', formType='test', fields=[]); pdf = generate_pdf(p, build_markdown(p)); print(len(pdf))"` → 输出有效字节数

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: PDF 生成完整性 — 所有字体替换后 PDF 不崩溃
    Tool: Bash
    Preconditions: main.py 已完成编辑
    Steps:
      1. 运行: uv run python -c "from main import generate_pdf, build_markdown, SyncPayload, FieldItem; import json; fields = [FieldItem(id='crrc_textfield', caption='主题', fieldType='text', value='测试主题'), FieldItem(id='crrc_datefield', caption='时间', fieldType='date', value='2025-01-01'), FieldItem(id='crrc_largetextfield', caption='内容', fieldType='textarea', value='测试内容')]; p = SyncPayload(formId='T001', formType='feedback', fields=fields); pdf = generate_pdf(p, build_markdown(p)); print(f'PDF_SIZE:{len(pdf)}')"
      2. 检查输出包含 "PDF_SIZE:" 且数值 > 0
    Expected Result: stdout 包含 "PDF_SIZE:" + 正整数，无 Traceback
    Failure Indicators: 出现 RuntimeError（如 "Undefined font: fangsong B"）或 PDF_SIZE 为 0
    Evidence: .omo/evidence/task-1-pdf-integrity.txt
  ```

  ```
  Scenario: 无残留 Fangsong Bold — grep 验证全部替换
    Tool: Bash
    Preconditions: main.py 已完成编辑
    Steps:
      1. 运行: grep -n 'Fangsong.*"B"' main.py
      2. 检查退出码和输出
    Expected Result: 退出码 1（no matches），stdout 为空
    Failure Indicators: 退出码 0 或有任何行输出
    Evidence: .omo/evidence/task-1-no-residual.txt
  ```

  **Evidence to Capture**:
  - [ ] task-1-pdf-integrity.txt
  - [ ] task-1-no-residual.txt

  **Commit**: YES
  - Message: `fix(pdf): replace Fangsong Bold with SimHei for all 10 table labels`
  - Files: `main.py`

---

- [x] 2. 内容布局优化：strip 空白行 + 最低高度 150pt

  **What to do**:
  - 在 `main.py` 第 137 行（`content_val = get_field_value(...)`）后增加 `.strip()`：
    ```python
    content_val = get_field_value(data.fields, "crrc_largetextfield", get_field_value(data.fields, "内容")).strip()
    ```
  - 在 `main.py` 第 149 行 `multi_cell` 调用处增加最低高度约束：
    - 计算 `multi_cell` 实际需要的高度 → `needed_height = len(merged_text.split('\n')) * line_height`
    - 若 `needed_height < 150`，则传入 `h = max(150, needed_height) / line_count` 或直接设置 `h=150`
    - 推荐实现：将 `multi_cell(table_width, line_height, merged_text, ...)` 改为使用变量控制高度
    ```python
    # Calculate minimum height for content box
    content_lines = merged_text.count('\n') + 1
    content_height = max(150, content_lines * line_height)
    pdf.multi_cell(table_width, line_height, merged_text, border=1, align="L", 
                   fill=False, split_only=False, max_line_height=line_height, 
                   new_x="LMARGIN", new_y="NEXT", h=content_height / content_lines)
    ```
    - 注意：fpdf2 的 `multi_cell` 的 `h` 参数是每行高度。若需确保整体最低高度，可用 `h = content_height / content_lines`

  **Must NOT do**:
  - 不修改 `merged_text` 的内容结构（保留 `{recipient}：\n{content}` 格式）
  - 不修改其他 `multi_cell` 调用（如 line 205 送达部门签收）
  - 不在 strip 时删除内容中间的空白行（仅首尾）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 单文件两处简单修改（`.strip()` + 高度计算），无复杂逻辑
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `git-master`: 简单提交，无需高级 git

  **Parallelization**:
  - **Can Run In Parallel**: NO (与 Task 1 同文件，需 Task 1 完成后执行)
  - **Parallel Group**: Wave 1 (after Task 1)
  - **Blocks**: None
  - **Blocked By**: Task 1

  **References**:
  - `main.py:137` — content_val 获取处
  - `main.py:140` — merged_text 组装处
  - `main.py:149` — multi_cell 调用处
  - `main.py:205` — 其他 multi_cell 调用（参考但不修改）

  **Acceptance Criteria**:
  - [ ] `grep -n 'content_val.*strip' main.py` → 1 match
  - [ ] `grep -n '150' main.py` → 至少 1 match（在高度计算上下文中）
  - [ ] 短内容测试：内容仅 1 行 → 内容框高度 ≥ 150pt → 不再有大面积底部留白
  - [ ] 长内容测试：内容 20+ 行 → 内容框自然高度 > 150pt → 不被截断

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: 短内容 — 内容框高度 ≥ 150pt
    Tool: Bash
    Preconditions: main.py 已完成编辑
    Steps:
      1. 运行短内容测试: uv run python -c "from main import generate_pdf, build_markdown, SyncPayload, FieldItem; fields = [FieldItem(id='crrc_textfield', caption='主题', fieldType='text', value='短测试'), FieldItem(id='crrc_largetextfield', caption='内容', fieldType='textarea', value='一行内容'), FieldItem(id='crrc_mulbasedatafield', caption='主送', fieldType='text', value='测试部门')]; p = SyncPayload(formId='T002', formType='feedback', fields=fields); pdf = generate_pdf(p, build_markdown(p)); print(f'PDF_SIZE:{len(pdf)}')"
      2. 检查 PDF_SIZE > 0 且无错误
    Expected Result: PDF 生成成功，无 Traceback
    Failure Indicators: RuntimeError 或 PDF_SIZE 为 0
    Evidence: .omo/evidence/task-2-short-content.txt

  Scenario: 长内容 — 不被截断，自然高度正常
    Tool: Bash
    Preconditions: main.py 已完成编辑
    Steps:
      1. 运行长内容测试: uv run python -c "from main import generate_pdf, build_markdown, SyncPayload, FieldItem; long_text = '\n'.join([f'第{i}行内容' for i in range(30)]); fields = [FieldItem(id='crrc_textfield', caption='主题', fieldType='text', value='长测试'), FieldItem(id='crrc_largetextfield', caption='内容', fieldType='textarea', value=long_text), FieldItem(id='crrc_mulbasedatafield', caption='主送', fieldType='text', value='测试部门')]; p = SyncPayload(formId='T003', formType='feedback', fields=fields); pdf = generate_pdf(p, build_markdown(p)); print(f'PDF_SIZE:{len(pdf)}')"
      2. 检查 PDF_SIZE > 0 且无错误
    Expected Result: PDF 生成成功，无 Traceback，PDF 明显大于短内容版本
    Failure Indicators: RuntimeError
    Evidence: .omo/evidence/task-2-long-content.txt

  Scenario: 首尾空白行 strip — 验证空白行已去除
    Tool: Bash
    Preconditions: main.py 已完成编辑
    Steps:
      1. 运行 strip 测试: uv run python -c "from main import generate_pdf, build_markdown, SyncPayload, FieldItem; fields = [FieldItem(id='crrc_largetextfield', caption='内容', fieldType='textarea', value='\n\n\n实际内容在这里\n\n\n')]; p = SyncPayload(formId='T004', formType='feedback', fields=fields); pdf = generate_pdf(p, build_markdown(p)); print(f'PDF_SIZE:{len(pdf)}')"
      2. 检查 PDF_SIZE > 0 且无错误
    Expected Result: PDF 生成成功，内容首尾空白行被去除
    Failure Indicators: RuntimeError
    Evidence: .omo/evidence/task-2-strip.txt
  ```

  **Evidence to Capture**:
  - [ ] task-2-short-content.txt
  - [ ] task-2-long-content.txt
  - [ ] task-2-strip.txt

  **Commit**: YES
  - Message: `feat(pdf): strip content blank lines and enforce min 150pt content box height`
  - Files: `main.py`

---

## Final Verification Wave

> 用户选择"暂不验证"，此 Wave 跳过。如需验证，手动运行：
> ```bash
> uv run python main.py
> # 然后 POST 测试数据到 http://localhost:12378/api/sync
> # 检查 PDF 中 主题/时间/经办人/校对/审核/批准/送达部门签收 标签是否为 Heiti 黑体
> # 检查内容框高度是否 ≥ 150pt
> ```

---

## Commit Strategy

- **Task 1**: `fix(pdf): replace Fangsong Bold with SimHei for all table labels` - main.py
- **Task 2**: `feat(pdf): strip content blank lines and enforce min content box height` - main.py

---

## Success Criteria

### Verification Commands
```bash
# 验证无残留 Fangsong Bold
grep -n 'Fangsong.*"B"' main.py
# Expected: 0 matches

# 验证 Heiti 替换正确
grep -n 'Heiti.*""' main.py
# Expected: 12 matches (2 existing titles + 10 new labels)

# 验证 PDF 生成不崩溃
uv run python -c "from main import generate_pdf, build_markdown, SyncPayload, FieldItem; p = SyncPayload(formId='test', formType='test', fields=[]); pdf = generate_pdf(p, build_markdown(p)); print(f'OK: {len(pdf)} bytes')"

# 验证内容 strip
grep -n 'content_val.*strip' main.py
# Expected: 1 match

# 验证最低高度
grep -n '150' main.py
# Expected: 1 match in multi_cell context
```

### Final Checklist
- [ ] Fangsong Bold 全部替换
- [ ] _load_fonts 清理完成
- [ ] Content strip 生效
- [ ] Min height 150pt 约束到位
- [ ] PDF 生成无崩溃
