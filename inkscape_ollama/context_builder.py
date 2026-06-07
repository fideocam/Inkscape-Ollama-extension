"""Build a compact text digest of the SVG document and selection for the LLM."""

from __future__ import annotations

from typing import Any, Optional


def _tag_name(elem: Any) -> str:
    tag = getattr(elem, "tag", None) or type(elem).__name__
    if isinstance(tag, str) and "}" in tag:
        tag = tag.split("}", 1)[-1]
    return str(tag)


def _elem_ref(elem: Any) -> str:
    elem_id = getattr(elem, "get_id", lambda: None)()
    if callable(getattr(elem, "get_id", None)):
        try:
            elem_id = elem.get_id()
        except Exception:
            elem_id = elem.get("id")
    else:
        elem_id = elem.get("id") if hasattr(elem, "get") else None
    label = getattr(elem, "label", None)
    if label:
        return f"id={elem_id!r} label={label!r}"
    return f"id={elem_id!r}"


def _bbox_lines(elem: Any, indent: str) -> list[str]:
    lines: list[str] = []
    try:
        bb = elem.bounding_box()
    except Exception:
        return lines
    if bb is None:
        return lines
    try:
        left, top, right, bottom = bb.left, bb.top, bb.right, bb.bottom
        w = right - left
        h = bottom - top
        cx = (left + right) / 2.0
        cy = (top + bottom) / 2.0
        lines.append(
            f"{indent}bbox_center=[{cx:.4f},{cy:.4f}] "
            f"bbox_size=[{w:.4f},{h:.4f}] "
            f"bbox=[{left:.4f},{top:.4f},{right:.4f},{bottom:.4f}]"
        )
    except Exception:
        pass
    return lines


def _style_summary(elem: Any, indent: str) -> Optional[str]:
    try:
        style = elem.style
    except Exception:
        style = None
    if style is None:
        return None
    parts: list[str] = []
    for key in ("fill", "stroke", "stroke-width", "opacity", "font-size"):
        val = style.get(key)
        if val is not None:
            parts.append(f"{key}={val}")
    if not parts:
        return None
    return f"{indent}style: " + ", ".join(parts)


def _element_lines(elem: Any, depth: int = 0, *, max_path_chars: int = 200) -> list[str]:
    indent = "  " * depth
    lines = [f"{indent}- {_tag_name(elem)} {_elem_ref(elem)}"]
    lines.extend(_bbox_lines(elem, indent + "  "))

    style_line = _style_summary(elem, indent + "  ")
    if style_line:
        lines.append(style_line)

    for attr in ("x", "y", "width", "height", "cx", "cy", "rx", "ry", "r", "d", "transform"):
        if hasattr(elem, "get"):
            val = elem.get(attr)
            if val is not None:
                sval = str(val)
                if attr == "d" and len(sval) > max_path_chars:
                    sval = sval[: max_path_chars - 3] + "..."
                lines.append(f"{indent}  {attr}={sval!r}")

    if _tag_name(elem).lower() in ("text", "flowroot"):
        try:
            text = elem.text_content()
            if text:
                preview = text.strip().replace("\n", " ")[:120]
                lines.append(f"{indent}  text_content={preview!r}")
        except Exception:
            pass

    if hasattr(elem, "__iter__"):
        children = [c for c in elem if hasattr(c, "tag")]
        if children and _tag_name(elem).lower() in ("g", "svg", "layer", "group"):
            lines.append(f"{indent}  children:")
            for child in children[:40]:
                lines.extend(_element_lines(child, depth + 2, max_path_chars=max_path_chars))
            if len(children) > 40:
                lines.append(f"{indent}    ... ({len(children) - 40} more children)")

    return lines


def _page_lines(svg: Any) -> list[str]:
    lines: list[str] = []
    root = svg.getroot() if hasattr(svg, "getroot") else svg
    try:
        w = root.get("width", "")
        h = root.get("height", "")
        vb = root.get("viewBox", "")
        lines.append(f"page: width={w!r} height={h!r} viewBox={vb!r}")
    except Exception:
        pass
    try:
        namedview = svg.namedview
        if namedview is not None:
            lines.append(
                f"namedview: document-units={namedview.get('inkscape:document-units', '?')!r} "
                f"pagecolor={namedview.get('pagecolor', '?')!r}"
            )
    except Exception:
        pass
    try:
        layer = svg.get_current_layer()
        if layer is not None:
            lines.append(f"current_layer: {_elem_ref(layer)}")
    except Exception:
        pass
    return lines


def _layer_tree(svg: Any) -> list[str]:
    lines: list[str] = ["Layers and top-level groups:"]
    try:
        root = svg.getroot()
        for child in root:
            if _tag_name(child).lower() in ("g", "svg"):
                is_layer = child.get("inkscape:groupmode") == "layer"
                kind = "layer" if is_layer else "group"
                lines.append(f"  - {kind} {_elem_ref(child)}")
    except Exception:
        lines.append("  (unable to read layer tree)")
    return lines


def build_document_digest(svg: Any, selection: list[Any], max_chars: int) -> str:
    lines: list[str] = ["Inkscape SVG document digest", ""]
    lines.extend(_page_lines(svg))
    lines.append("")
    lines.extend(_layer_tree(svg))
    lines.append("")
    lines.append("Document elements (truncated if large):")

    try:
        root = svg.getroot()
        count = 0
        for elem in root.descendants():
            if not hasattr(elem, "tag"):
                continue
            tag = _tag_name(elem).lower()
            if tag in ("defs", "namedview", "metadata", "style"):
                continue
            lines.extend(_element_lines(elem, 1))
            count += 1
            if count >= 80:
                lines.append("  ... (element list truncated at 80 items)")
                break
    except Exception as exc:
        lines.append(f"  (unable to enumerate elements: {exc})")

    lines.append("")
    lines.append("Selection (use for 'selected', 'this', 'these'):")
    if not selection:
        lines.append("  selected_elements: (none)")
    else:
        refs = ", ".join(_elem_ref(e) for e in selection)
        lines.append(f"  selected_elements: {refs}")
        for elem in selection:
            lines.extend(_element_lines(elem, 1))

    text = "\n".join(lines)
    if len(text) > max_chars:
        head = max_chars // 2
        tail = max_chars - head - 80
        text = (
            text[:head]
            + f"\n\n... [digest truncated at {max_chars} chars] ...\n\n"
            + text[-tail:]
        )
    return text
