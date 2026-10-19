# -*- coding: utf-8 -*-
"""简历文档解析服务：PDF / Word 纯文本提取。

Word 解析按文档真实顺序提取段落与表格，处理合并单元格去重、嵌套表格递归展开，
保证表格排版简历也能完整提取。
"""
import os

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

try:
    from docx import Document
except ImportError:  # pragma: no cover
    Document = None


def _iter_block_items(parent):
    """按文档真实顺序遍历正文块（段落 / 表格可能交错出现）。"""
    from docx.document import Document as _Document
    from docx.table import _Cell
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        return

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _cell_blocks(cell):
    """提取一个单元格内的段落文本；遇到嵌套表格则递归展开。"""
    from docx.text.paragraph import Paragraph

    out = []
    for block in _iter_block_items(cell):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t:
                out.append(t)
        else:  # 嵌套表格
            nested = _table_to_text(block).replace("\n", " ").strip()
            if nested:
                out.append(nested)
    return out


def _table_to_text(table) -> str:
    """把一张 Word 表格转成文本：每行一个段落，单元格用 | 分隔。
    合并单元格在 python-docx 里会重复出现，按底层 tc 节点去重。"""
    lines = []
    for row in table.rows:
        seen = set()
        cells = []
        for cell in row.cells:
            tc_id = id(cell._tc)
            if tc_id in seen:
                continue
            seen.add(tc_id)
            cell_text = " ".join(_cell_blocks(cell)).strip()
            if cell_text:
                cells.append(cell_text)
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def docx_to_text(file_path: str) -> str:
    """提取 docx 全文，包含【段落】和【表格】内容（表格是简历常见排版方式）。"""
    from docx.text.paragraph import Paragraph

    doc = Document(file_path)
    parts = []
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t:
                parts.append(t)
        else:  # 顶层表格
            table_text = _table_to_text(block).strip()
            if table_text:
                parts.append(table_text)
    return "\n".join(parts).strip()


def read_local_resume(file_path: str) -> str:
    """读取单份简历 PDF/DOCX。

    注意：文件不存在/解析失败时返回以 ❌ 开头的错误文案（兼容旧调用方约定）。
    """
    if not os.path.exists(file_path):
        return f"❌ 文件不存在：{file_path}"
    text = ""
    try:
        if file_path.lower().endswith(".pdf") and fitz:
            doc = fitz.open(file_path)
            for page in doc:
                t = page.get_text("text")
                text += t or " ".join(w[4] for w in page.get_text("words"))
            doc.close()
        elif file_path.lower().endswith((".docx", ".doc")) and Document:
            # 同时提取段落与表格内容（真实简历大量使用表格排版）
            text = docx_to_text(file_path)
    except Exception as e:
        return f"❌ 解析失败：{str(e)}"
    return text.strip()


def extract_resume_text(file_path: str) -> str:
    """读取简历纯文本；失败时直接抛异常（HTTP 网关层使用）。"""
    if not os.path.exists(file_path):
        raise Exception(f"文件不存在：{file_path}")
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        text = ""
        doc = fitz.open(file_path)
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text += page_text + "\n"
        doc.close()
    elif ext in (".docx", ".doc"):
        text = docx_to_text(file_path)
    else:
        raise Exception("仅支持 .pdf / .docx 简历文件")
    if not text.strip():
        raise Exception("文件内未识别到任何文字内容")
    return text.strip()


def read_multi_resume(path_str: str) -> str:
    """读取多份简历并拼接（按逗号分隔路径）。"""
    path_list = path_str.split(",")
    full_content = ""
    for idx, path in enumerate(path_list):
        path = path.strip()
        text = read_local_resume(path)
        if "❌" in text:
            return f"简历{idx + 1}读取失败：{text}"
        full_content += f"\n===== 简历{idx + 1} =====\n{text}\n"
    return full_content
