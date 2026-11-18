#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script kết xuất Báo cáo thí nghiệm và Log chat AI từ Markdown sang:
  1. Định dạng PDF chuẩn in ấn A4 (thông qua HTML định kiểu học thuật + Google Chrome Headless)
  2. Định dạng Microsoft Word (.docx) chuẩn OpenXML ECMA-376 (đầy đủ Heading, Bảng biểu có khung,
     Đồ thị PNG nhúng trực tiếp độ phân giải 300 DPI, hỗ trợ tiếng Việt Unicode hoàn chỉnh).
"""

import base64
import html
import os
import re
import struct
import subprocess
import tempfile
import zipfile
from pathlib import Path


# =============================================================================
# 1. Bộ chuyển đổi biểu thức toán học LaTeX sang HTML / Unicode sạch đẹp
# =============================================================================
LATEX_REPLACEMENTS = [
    (r"\\log", "<span class='m-text'>log</span>"),
    (r"\\bmod\b", " <span class='m-text'>mod</span> "),
    (r"\\\{", "{"),
    (r"\\\}", "}"),
    (r"\\pm\b", "±"),
    (r"\\times\b", "×"),
    (r"\\cdot\b", "·"),
    (r"\\le\b", "≤"),
    (r"\\ge\b", "≥"),
    (r"\\approx\b", "≈"),
    (r"\\sim\b", "~"),
    (r"\\in\b", "∈"),
    (r"\\dots\b", "…"),
    (r"\\rightarrow\b", "→"),
    (r"\\to\b", "→"),
    (r"\\lfloor\b", "⌊"),
    (r"\\rfloor\b", "⌋"),
    (r"\\Delta\b", "Δ"),
    (r"\\,", " "),
    (r"\\;", " "),
]

UNICODE_LATEX_REPLACEMENTS = [
    (r"\\log", "log"),
    (r"\\bmod\b", " mod "),
    (r"\\\{", "{"),
    (r"\\\}", "}"),
    (r"\\pm\b", "±"),
    (r"\\times\b", "×"),
    (r"\\cdot\b", "·"),
    (r"\\le\b", "≤"),
    (r"\\ge\b", "≥"),
    (r"\\approx\b", "≈"),
    (r"\\sim\b", "~"),
    (r"\\in\b", "∈"),
    (r"\\dots\b", "…"),
    (r"\\rightarrow\b", "→"),
    (r"\\to\b", "→"),
    (r"\\lfloor\b", "⌊"),
    (r"\\rfloor\b", "⌋"),
    (r"\\Delta\b", "Δ"),
    (r"\\,", " "),
    (r"\\;", " "),
]


def latex_to_html(expr: str) -> str:
    s = expr.strip()
    # \text{...}
    s = re.sub(r"\\text\{([^{}]*)\}", lambda m: f"<span class='m-text'>{html.escape(m.group(1))}</span>", s)
    # \bar{x}
    s = re.sub(r"\\bar\{([^{}]*)\}", r"\1&#772;", s)
    # \sqrt{...}
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    # \frac{a}{b}
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1) / (\2)", s)
    for pat, rep in LATEX_REPLACEMENTS:
        s = re.sub(pat, rep, s)
    # _{...} and _x
    s = re.sub(r"_\{([^{}]*)\}", r"<sub>\1</sub>", s)
    s = re.sub(r"_([A-Za-z0-9])", r"<sub>\1</sub>", s)
    # ^{...} and ^x
    s = re.sub(r"\^\{([^{}]*)\}", r"<sup>\1</sup>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-]+)", r"<sup>\1</sup>", s)
    s = s.replace(r"\%", "%")
    return f"<span class='math'>{s}</span>"


def latex_to_plain_unicode(expr: str) -> str:
    s = expr.strip()
    s = re.sub(r"\\text\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\bar\{x\}", "x̄", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    for pat, rep in UNICODE_LATEX_REPLACEMENTS:
        s = re.sub(pat, rep, s)
    sub_map = str.maketrans("0123456789n+-", "₀₁₂₃₄₅₆₇₈₉ₙ₊₋")
    sup_map = str.maketrans("0123456789n+-", "⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁺⁻")
    s = re.sub(r"_\{([0-9n+\-]+)\}", lambda m: m.group(1).translate(sub_map), s)
    s = re.sub(r"_([0-9n])", lambda m: m.group(1).translate(sub_map), s)
    s = re.sub(r"_\{([^{}]*)\}", r"(\1)", s)
    s = re.sub(r"\^\{([0-9n+\-]+)\}", lambda m: m.group(1).translate(sup_map), s)
    s = re.sub(r"\^([0-9n])", lambda m: m.group(1).translate(sup_map), s)
    s = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", s)
    s = s.replace(r"\%", "%")
    return s


# =============================================================================
# 2. Định dạng văn bản inline Markdown -> HTML
# =============================================================================
def format_inline_html(text: str) -> str:
    # Giữ vùng code inline trước
    code_tokens = []

    def save_code(m):
        idx = len(code_tokens)
        code_tokens.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00CODE{idx}\x00"

    text = re.sub(r"`([^`]+)`", save_code, text)

    # Giữ vùng math inline $...$
    math_tokens = []

    def save_math(m):
        idx = len(math_tokens)
        math_tokens.append(latex_to_html(m.group(1)))
        return f"\x00MATH{idx}\x00"

    text = re.sub(r"\$([^$]+)\$", save_math, text)

    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*]+?)\*", r"<em>\1</em>", text)

    for i, tok in enumerate(math_tokens):
        text = text.replace(f"\x00MATH{i}\x00", tok)
    for i, tok in enumerate(code_tokens):
        text = text.replace(f"\x00CODE{i}\x00", tok)
    return text


# =============================================================================
# 3. Bộ phân tích cú pháp khối Markdown dùng chung cho HTML & DOCX
# =============================================================================
def parse_markdown_blocks(md_text: str):
    lines = md_text.splitlines()
    blocks = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            blocks.append(("hr", None))
            i += 1
            continue

        # Code block ```
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", (lang, "\n".join(code_lines))))
            continue

        # Display math $$...$$
        if stripped.startswith("$$"):
            if stripped.endswith("$$") and len(stripped) > 4:
                blocks.append(("math_block", stripped[2:-2].strip()))
                i += 1
                continue
            math_lines = [stripped[2:]]
            i += 1
            while i < n and not lines[i].strip().endswith("$$"):
                math_lines.append(lines[i])
                i += 1
            if i < n:
                math_lines.append(lines[i].strip()[:-2])
                i += 1
            blocks.append(("math_block", " ".join(math_lines).strip()))
            continue

        # Heading
        m_head = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m_head:
            level = len(m_head.group(1))
            blocks.append(("heading", (level, m_head.group(2).strip())))
            i += 1
            continue

        # Image ![alt](path)
        m_img = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m_img:
            blocks.append(("image", (m_img.group(1).strip(), m_img.group(2).strip())))
            i += 1
            continue

        # Blockquote >
        if stripped.startswith(">"):
            q_lines = []
            while i < n and lines[i].strip().startswith(">"):
                q_lines.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            blocks.append(("quote", " ".join(q_lines)))
            continue

        # Table | ... |
        if stripped.startswith("|") and (i + 1 < n) and re.match(r"^\|[\s:\-\|]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            align_raw = [c.strip() for c in lines[i + 1].strip().strip("|").split("|")]
            aligns = []
            for a in align_raw:
                if a.startswith(":") and a.endswith(":"):
                    aligns.append("center")
                elif a.endswith(":"):
                    aligns.append("right")
                else:
                    aligns.append("left")
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                r = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(r)
                i += 1
            blocks.append(("table", (header, aligns, rows)))
            continue

        # List items (- or 1.)
        if re.match(r"^(\-|\*|\d+\.)\s+", stripped):
            items = []
            while i < n:
                s_cur = lines[i].strip()
                m_li = re.match(r"^(\-|\*|\d+\.)\s+(.*)$", s_cur)
                if m_li:
                    indent = len(lines[i]) - len(lines[i].lstrip(" "))
                    is_ordered = m_li.group(1).endswith(".")
                    items.append((indent, is_ordered, m_li.group(2).strip()))
                    i += 1
                elif s_cur.startswith("$$"):
                    break
                elif s_cur and (len(lines[i]) - len(lines[i].lstrip(" ")) >= 2) and items:
                    # Continuation line of previous bullet
                    prev_indent, prev_ord, prev_txt = items[-1]
                    items[-1] = (prev_indent, prev_ord, prev_txt + " " + s_cur)
                    i += 1
                else:
                    break
            blocks.append(("list", items))
            continue

        # Normal paragraph
        p_lines = [stripped]
        i += 1
        while i < n:
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt == "---"
                or nxt.startswith("#")
                or nxt.startswith("```")
                or nxt.startswith("$$")
                or nxt.startswith("![")
                or nxt.startswith(">")
                or nxt.startswith("|")
                or re.match(r"^(\-|\*|\d+\.)\s+", nxt)
            ):
                break
            p_lines.append(nxt)
            i += 1
        blocks.append(("para", " ".join(p_lines)))

    return blocks


# =============================================================================
# 4. Kết xuất HTML định kiểu học thuật & In sang PDF bằng Chrome Headless
# =============================================================================
def blocks_to_html(blocks, base_dir: Path, doc_title: str) -> str:
    body_parts = []
    fig_counter = 0

    for btype, content in blocks:
        if btype == "hr":
            body_parts.append("<hr/>")
        elif btype == "heading":
            lvl, text = content
            body_parts.append(f"<h{lvl}>{format_inline_html(text)}</h{lvl}>")
        elif btype == "para":
            body_parts.append(f"<p>{format_inline_html(content)}</p>")
        elif btype == "quote":
            body_parts.append(f"<blockquote>{format_inline_html(content)}</blockquote>")
        elif btype == "math_block":
            body_parts.append(f"<div class='math-block'>{latex_to_html(content)}</div>")
        elif btype == "code":
            _, code_str = content
            body_parts.append(f"<pre><code>{html.escape(code_str)}</code></pre>")
        elif btype == "image":
            alt, rel_path = content
            img_path = (base_dir / rel_path).resolve()
            b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
            fig_counter += 1
            body_parts.append(
                f"<figure>"
                f"<img src='data:image/png;base64,{b64}' alt='{html.escape(alt)}'/>"
                f"<figcaption><strong>Hình {fig_counter}:</strong> {format_inline_html(alt)}</figcaption>"
                f"</figure>"
            )
        elif btype == "table":
            header, aligns, rows = content
            th_html = "".join(
                f"<th style='text-align:{aligns[idx] if idx < len(aligns) else 'left'}'>{format_inline_html(h)}</th>"
                for idx, h in enumerate(header)
            )
            tr_list = []
            for r in rows:
                tds = "".join(
                    f"<td style='text-align:{aligns[idx] if idx < len(aligns) else 'left'}'>{format_inline_html(c)}</td>"
                    for idx, c in enumerate(r)
                )
                tr_list.append(f"<tr>{tds}</tr>")
            body_parts.append(
                f"<div class='table-wrap'><table><thead><tr>{th_html}</tr></thead>"
                f"<tbody>{''.join(tr_list)}</tbody></table></div>"
            )
        elif btype == "list":
            items = content
            if not items:
                continue
            tag = "ol" if items[0][1] else "ul"
            grouped = []
            for indent, is_ord, txt in items:
                if indent >= 2 and grouped:
                    grouped[-1][1].append(txt)
                else:
                    grouped.append([txt, []])
            li_html = []
            for parent_txt, children in grouped:
                sub_str = ""
                if children:
                    sub_lis = "".join(f"<li>{format_inline_html(ch)}</li>" for ch in children)
                    sub_str = f"<ul>{sub_lis}</ul>"
                li_html.append(f"<li>{format_inline_html(parent_txt)}{sub_str}</li>")
            body_parts.append(f"<{tag}>{''.join(li_html)}</{tag}>")

    css = """
    @page {
        size: A4 portrait;
        margin: 16mm 15mm 16mm 15mm;
    }
    * { box-sizing: border-box; }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
        font-size: 10.2pt;
        line-height: 1.52;
        color: #1e293b;
        margin: 0;
        padding: 0;
    }
    h1 {
        font-size: 17pt;
        color: #0f172a;
        margin: 0 0 4pt 0;
        letter-spacing: -0.2px;
        border-bottom: 2.2px solid #1e40af;
        padding-bottom: 6pt;
    }
    h2 {
        font-size: 12.6pt;
        color: #1e3a8a;
        margin: 14pt 0 6pt 0;
        border-left: 4px solid #2563eb;
        padding-left: 8pt;
        page-break-after: avoid;
    }
    h3 {
        font-size: 10.9pt;
        color: #0f172a;
        margin: 10pt 0 4pt 0;
        page-break-after: avoid;
    }
    p { margin: 4.5pt 0; text-align: justify; }
    ul, ol { margin: 4pt 0 6pt 16pt; padding: 0; }
    li { margin: 2.5pt 0; text-align: justify; }
    li.sub-li { margin-left: 14pt; list-style-type: circle; }
    hr { border: none; border-top: 1px solid #cbd5e1; margin: 10pt 0; }
    code {
        font-family: "SF Mono", Menlo, Consolas, monospace;
        font-size: 9pt;
        background: #f1f5f9;
        color: #0f172a;
        padding: 1px 4px;
        border-radius: 3px;
    }
    pre {
        background: #0f172a;
        color: #f8fafc;
        padding: 8pt 10pt;
        border-radius: 5px;
        overflow-x: auto;
        font-size: 8.6pt;
        line-height: 1.4;
        page-break-inside: avoid;
    }
    pre code { background: transparent; color: inherit; padding: 0; }
    blockquote {
        margin: 6pt 0;
        padding: 6pt 10pt;
        background: #eff6ff;
        border-left: 3.5px solid #3b82f6;
        color: #1e3a8a;
        font-style: italic;
    }
    .math {
        font-family: "Times New Roman", Times, Georgia, serif;
        font-style: italic;
        font-size: 10.6pt;
    }
    .math .m-text { font-style: normal; font-family: -apple-system, Arial, sans-serif; font-size: 9.6pt; }
    .math-block {
        text-align: center;
        margin: 8pt 0;
        padding: 5pt;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        font-size: 11.2pt;
        page-break-inside: avoid;
    }
    .table-wrap {
        margin: 7pt 0 9pt 0;
        page-break-inside: avoid;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 8.3pt;
        line-height: 1.3;
    }
    th {
        background: #1e3a8a;
        color: #ffffff;
        font-weight: 600;
        padding: 4pt 4.5pt;
        border: 1px solid #1e3a8a;
    }
    td {
        padding: 3.1pt 4.5pt;
        border: 1px solid #cbd5e1;
    }
    tbody tr:nth-child(even) { background: #f8fafc; }
    figure {
        margin: 9pt 0;
        text-align: center;
        page-break-inside: avoid;
    }
    figure img {
        max-width: 100%;
        height: auto;
        border: 1px solid #e2e8f0;
        border-radius: 4px;
    }
    figcaption {
        font-size: 8.9pt;
        color: #475569;
        margin-top: 4pt;
    }
    """
    return f"<!DOCTYPE html><html lang='vi'><head><meta charset='utf-8'/><title>{html.escape(doc_title)}</title><style>{css}</style></head><body>{''.join(body_parts)}</body></html>"


def render_html_to_pdf(html_str: str, pdf_path: Path):
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".html", encoding="utf-8", delete=False) as tmp:
        tmp.write(html_str)
        tmp_html_path = tmp.name
    try:
        cmd = [
            chrome_bin,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={pdf_path}",
            f"file://{tmp_html_path}",
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        if os.path.exists(tmp_html_path):
            os.remove(tmp_html_path)


# =============================================================================
# 5. Bộ tạo tệp Microsoft Word (.docx) chuẩn OpenXML ECMA-376 thuần Python
# =============================================================================
def get_png_dimensions(png_path: Path) -> tuple[int, int]:
    data = png_path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return (1600, 700)
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def inline_to_word_runs(text: str, base_color: str = "1E293B", force_bold: bool = False, font_sz_half_pt: int = 21) -> str:
    """Chuyển chuỗi Markdown inline (**bold**, *italic*, `code`, $math$) thành danh sách <w:r> (hỗ trợ lồng nhau)."""
    text = re.sub(r"\$([^$]+)\$", lambda m: latex_to_plain_unicode(m.group(1)), text)

    def render_segment(seg: str, bold: bool, italic: bool) -> list[str]:
        if not seg:
            return []
        # Ưu tiên tách `code` trước
        m_c = re.search(r"`([^`]+)`", seg)
        if m_c:
            return (
                render_segment(seg[:m_c.start()], bold, italic)
                + [make_run(m_c.group(1), bold=bold, italic=italic, is_code=True)]
                + render_segment(seg[m_c.end():], bold, italic)
            )
        # Tách **bold**
        m_b = re.search(r"\*\*(.+?)\*\*", seg)
        if m_b:
            return (
                render_segment(seg[:m_b.start()], bold, italic)
                + render_segment(m_b.group(1), True, italic)
                + render_segment(seg[m_b.end():], bold, italic)
            )
        # Tách *italic*
        m_i = re.search(r"\*([^*]+?)\*", seg)
        if m_i:
            return (
                render_segment(seg[:m_i.start()], bold, italic)
                + render_segment(m_i.group(1), bold, True)
                + render_segment(seg[m_i.end():], bold, italic)
            )
        return [make_run(seg, bold=bold, italic=italic, is_code=False)]

    def make_run(content: str, bold: bool, italic: bool, is_code: bool) -> str:
        rpr = []
        if is_code:
            rpr.append("<w:rFonts w:ascii='Consolas' w:hAnsi='Consolas' w:cs='Consolas'/>")
            rpr.append("<w:shd w:val='clear' w:color='auto' w:fill='F1F5F9'/>")
            rpr.append(f"<w:sz w:val='{max(16, font_sz_half_pt - 2)}'/>")
        else:
            rpr.append("<w:rFonts w:ascii='Times New Roman' w:hAnsi='Times New Roman' w:cs='Times New Roman'/>")
            rpr.append(f"<w:sz w:val='{font_sz_half_pt}'/>")
        if bold:
            rpr.append("<w:b/>")
        if italic:
            rpr.append("<w:i/>")
        rpr.append(f"<w:color w:val='{base_color}'/>")
        return (
            f"<w:r><w:rPr>{''.join(rpr)}</w:rPr>"
            f"<w:t xml:space='preserve'>{xml_escape(content)}</w:t></w:r>"
        )

    return "".join(render_segment(text, force_bold, False))


def build_docx(blocks, base_dir: Path, docx_path: Path):
    docx_path.parent.mkdir(parents=True, exist_ok=True)
    media_files = []  # list of (rId, media_name, Path)
    body_xml = []
    doc_pr_id = 1
    fig_num = 0

    for btype, content in blocks:
        if btype == "hr":
            body_xml.append(
                "<w:p><w:pPr><w:pBdr><w:bottom w:val='single' w:sz='6' w:space='1' w:color='CBD5E1'/></w:pBdr>"
                "<w:spacing w:before='80' w:after='80'/></w:pPr></w:p>"
            )
        elif btype == "heading":
            lvl, txt = content
            style_map = {1: ("Heading1", 32, "0F172A"), 2: ("Heading2", 26, "1E3A8A"), 3: ("Heading3", 23, "0F172A"), 4: ("Heading3", 22, "1E293B")}
            st_id, sz, col = style_map.get(lvl, ("Heading3", 22, "1E293B"))
            runs = inline_to_word_runs(txt, base_color=col, force_bold=True, font_sz_half_pt=sz)
            body_xml.append(
                f"<w:p><w:pPr><w:pStyle w:val='{st_id}'/><w:keepNext/>"
                f"<w:spacing w:before='{200 if lvl <= 2 else 140}' w:after='80'/></w:pPr>{runs}</w:p>"
            )
        elif btype == "para":
            runs = inline_to_word_runs(content, font_sz_half_pt=22)
            body_xml.append(
                f"<w:p><w:pPr><w:jc w:val='both'/><w:spacing w:before='40' w:after='90' w:line='276' w:lineRule='auto'/></w:pPr>{runs}</w:p>"
            )
        elif btype == "quote":
            runs = inline_to_word_runs(content, base_color="1E3A8A", font_sz_half_pt=21)
            body_xml.append(
                "<w:p><w:pPr><w:ind w:left='360' w:right='240'/>"
                "<w:pBdr><w:left w:val='single' w:sz='18' w:space='8' w:color='3B82F6'/></w:pBdr>"
                "<w:shd w:val='clear' w:color='auto' w:fill='EFF6FF'/>"
                f"<w:spacing w:before='80' w:after='100'/></w:pPr>{runs}</w:p>"
            )
        elif btype == "math_block":
            expr_uni = latex_to_plain_unicode(content)
            runs = inline_to_word_runs(f"*{expr_uni}*", base_color="0F172A", font_sz_half_pt=23)
            body_xml.append(
                "<w:p><w:pPr><w:jc w:val='center'/>"
                "<w:shd w:val='clear' w:color='auto' w:fill='F8FAFC'/>"
                f"<w:spacing w:before='100' w:after='100'/></w:pPr>{runs}</w:p>"
            )
        elif btype == "code":
            _, code_str = content
            for ln in code_str.splitlines():
                body_xml.append(
                    "<w:p><w:pPr><w:ind w:left='240'/>"
                    "<w:shd w:val='clear' w:color='auto' w:fill='F1F5F9'/>"
                    "<w:spacing w:before='0' w:after='20'/></w:pPr>"
                    "<w:r><w:rPr><w:rFonts w:ascii='Consolas' w:hAnsi='Consolas'/><w:sz w:val='18'/><w:color w:val='0F172A'/></w:rPr>"
                    f"<w:t xml:space='preserve'>{xml_escape(ln)}</w:t></w:r></w:p>"
                )
        elif btype == "list":
            top_ord_idx = 0
            for indent, is_ord, txt in content:
                if indent >= 2:
                    prefix = "◦ "
                elif is_ord:
                    top_ord_idx += 1
                    prefix = f"{top_ord_idx}. "
                else:
                    prefix = "• "
                left_twips = 640 if indent >= 2 else 360
                runs = inline_to_word_runs(prefix + txt, font_sz_half_pt=22)
                body_xml.append(
                    f"<w:p><w:pPr><w:ind w:left='{left_twips}' w:hanging='200'/>"
                    f"<w:jc w:val='both'/><w:spacing w:before='30' w:after='60' w:line='268' w:lineRule='auto'/></w:pPr>{runs}</w:p>"
                )
        elif btype == "image":
            alt, rel_path = content
            img_path = (base_dir / rel_path).resolve()
            fig_num += 1
            r_id = f"rIdImg{fig_num}"
            media_name = f"image{fig_num}.png"
            media_files.append((r_id, media_name, img_path))

            px_w, px_h = get_png_dimensions(img_path)
            # Chiều rộng khung trang A4 sau lề: ~16.5 cm = 5,940,000 EMUs
            max_cx = 5_900_000
            cx = max_cx
            cy = int(cx * (px_h / max(1, px_w)))
            doc_pr_id += 1

            drawing_xml = (
                f"<w:p><w:pPr><w:jc w:val='center'/><w:keepNext/><w:spacing w:before='140' w:after='40'/></w:pPr>"
                f"<w:r><w:drawing>"
                f"<wp:inline distT='0' distB='0' distL='0' distR='0'>"
                f"<wp:extent cx='{cx}' cy='{cy}'/>"
                f"<wp:docPr id='{doc_pr_id}' name='Picture {fig_num}'/>"
                f"<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main' noChangeAspect='1'/></wp:cNvGraphicFramePr>"
                f"<a:graphic xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main'>"
                f"<a:graphicData uri='http://schemas.openxmlformats.org/drawingml/2006/picture'>"
                f"<pic:pic xmlns:pic='http://schemas.openxmlformats.org/drawingml/2006/picture'>"
                f"<pic:nvPicPr><pic:cNvPr id='{doc_pr_id}' name='{media_name}'/><pic:cNvPicPr/></pic:nvPicPr>"
                f"<pic:blipFill><a:blip r:embed='{r_id}'/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>"
                f"<pic:spPr><a:xfrm><a:off x='0' y='0'/><a:ext cx='{cx}' cy='{cy}'/></a:xfrm>"
                f"<a:prstGeom prst='rect'><a:avLst/></a:prstGeom></pic:spPr>"
                f"</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>"
            )
            body_xml.append(drawing_xml)
            cap_runs = inline_to_word_runs(f"**Hình {fig_num}:** *{alt}*", base_color="475569", font_sz_half_pt=19)
            body_xml.append(
                f"<w:p><w:pPr><w:jc w:val='center'/><w:spacing w:before='20' w:after='140'/></w:pPr>{cap_runs}</w:p>"
            )
        elif btype == "table":
            header, aligns, rows = content
            jc_map = {"left": "left", "center": "center", "right": "right"}
            tbl_rows = []

            # Header row
            h_cells = []
            for idx_c, h_txt in enumerate(header):
                jc = jc_map.get(aligns[idx_c] if idx_c < len(aligns) else "left", "left")
                runs = inline_to_word_runs(h_txt, base_color="FFFFFF", force_bold=True, font_sz_half_pt=18)
                h_cells.append(
                    "<w:tc><w:tcPr><w:shd w:val='clear' w:color='auto' w:fill='1E3A8A'/>"
                    "<w:vAlign w:val='center'/></w:tcPr>"
                    f"<w:p><w:pPr><w:jc w:val='{jc}'/><w:spacing w:before='40' w:after='40'/></w:pPr>{runs}</w:p></w:tc>"
                )
            tbl_rows.append(f"<w:tr><w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>{''.join(h_cells)}</w:tr>")

            # Data rows
            for r_idx, row in enumerate(rows):
                fill = "F8FAFC" if (r_idx % 2 == 1) else "FFFFFF"
                d_cells = []
                for idx_c, cell_txt in enumerate(row):
                    jc = jc_map.get(aligns[idx_c] if idx_c < len(aligns) else "left", "left")
                    runs = inline_to_word_runs(cell_txt, base_color="1E293B", font_sz_half_pt=18)
                    d_cells.append(
                        f"<w:tc><w:tcPr><w:shd w:val='clear' w:color='auto' w:fill='{fill}'/>"
                        "<w:vAlign w:val='center'/></w:tcPr>"
                        f"<w:p><w:pPr><w:jc w:val='{jc}'/><w:spacing w:before='30' w:after='30'/></w:pPr>{runs}</w:p></w:tc>"
                    )
                tbl_rows.append(f"<w:tr><w:trPr><w:cantSplit/></w:trPr>{''.join(d_cells)}</w:tr>")

            tbl_xml = (
                "<w:tbl><w:tblPr>"
                "<w:tblW w:w='5000' w:type='pct'/>"
                "<w:jc w:val='center'/>"
                "<w:tblBorders>"
                "<w:top w:val='single' w:sz='6' w:space='0' w:color='94A3B8'/>"
                "<w:left w:val='single' w:sz='6' w:space='0' w:color='CBD5E1'/>"
                "<w:bottom w:val='single' w:sz='8' w:space='0' w:color='1E3A8A'/>"
                "<w:right w:val='single' w:sz='6' w:space='0' w:color='CBD5E1'/>"
                "<w:insideH w:val='single' w:sz='4' w:space='0' w:color='CBD5E1'/>"
                "<w:insideV w:val='single' w:sz='4' w:space='0' w:color='E2E8F0'/>"
                "</w:tblBorders>"
                "<w:tblCellMar>"
                "<w:top w:w='50' w:type='dxa'/><w:left w:w='80' w:type='dxa'/>"
                "<w:bottom w:w='50' w:type='dxa'/><w:right w:w='80' w:type='dxa'/>"
                "</w:tblCellMar>"
                f"</w:tblPr>{''.join(tbl_rows)}</w:tbl>"
                "<w:p><w:pPr><w:spacing w:before='0' w:after='80'/></w:pPr></w:p>"
            )
            body_xml.append(tbl_xml)

    # Định dạng trang A4 chuẩn (11906 x 16838 twips, lề 2.0 cm = 1134 twips)
    sect_pr = (
        "<w:sectPr>"
        "<w:pgSz w:w='11906' w:h='16838'/>"
        "<w:pgMar w:top='1134' w:right='1134' w:bottom='1134' w:left='1250' w:header='708' w:footer='708' w:gutter='0'/>"
        "</w:sectPr>"
    )

    document_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:document "
        "xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main' "
        "xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships' "
        "xmlns:wp='http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'>"
        f"<w:body>{''.join(body_xml)}{sect_pr}</w:body></w:document>"
    )

    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:rPr>
      <w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
      <w:sz w:val="22"/>
    </w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:outlineLvl w:val="0"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:outlineLvl w:val="1"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading3">
    <w:name w:val="heading 3"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:outlineLvl w:val="2"/></w:pPr>
    <w:rPr><w:b/><w:sz w:val="23"/></w:rPr>
  </w:style>
</w:styles>"""

    rels_items = [
        "<Relationship Id='rIdStyles' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles' Target='styles.xml'/>"
    ]
    for r_id, media_name, _ in media_files:
        rels_items.append(
            f"<Relationship Id='{r_id}' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/image' Target='media/{media_name}'/>"
        )

    doc_rels_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        f"{''.join(rels_items)}</Relationships>"
    )

    root_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

    with zipfile.ZipFile(docx_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml)
        zf.writestr("_rels/.rels", root_rels_xml)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", styles_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels_xml)
        for _, media_name, img_path in media_files:
            zf.writestr(f"word/media/{media_name}", img_path.read_bytes())


def main():
    root = Path(__file__).resolve().parent.parent
    report_md = root / "report" / "Bao_Cao_Thi_Nghiem_MergeSort_CUTOFF.md"
    report_pdf = root / "report" / "Bao_Cao_Thi_Nghiem_MergeSort_CUTOFF.pdf"
    report_docx = root / "report" / "Bao_Cao_Thi_Nghiem_MergeSort_CUTOFF.docx"

    chat_md = root / "ai_chat_log" / "Log_Chat_Voi_AI.md"
    chat_pdf = root / "ai_chat_log" / "Log_Chat_Voi_AI.pdf"

    # 1. Xuất Báo cáo thí nghiệm (.pdf và .docx)
    rep_blocks = parse_markdown_blocks(report_md.read_text(encoding="utf-8"))
    rep_html = blocks_to_html(rep_blocks, report_md.parent, "Báo cáo thí nghiệm Mergesort CUTOFF")
    render_html_to_pdf(rep_html, report_pdf)
    build_docx(rep_blocks, report_md.parent, report_docx)
    print("Đã xuất:", report_pdf)
    print("Đã xuất:", report_docx)

    # 2. Xuất Log chat với AI (.pdf)
    chat_blocks = parse_markdown_blocks(chat_md.read_text(encoding="utf-8"))
    chat_html = blocks_to_html(chat_blocks, chat_md.parent, "Log trao đổi với AI - Thí nghiệm Mergesort CUTOFF")
    render_html_to_pdf(chat_html, chat_pdf)
    print("Đã xuất:", chat_pdf)


if __name__ == "__main__":
    main()
