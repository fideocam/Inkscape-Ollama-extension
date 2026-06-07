"""Parse assistant output and apply a constrained set of SVG edits."""

from __future__ import annotations

from typing import Any, Optional

import inkex
from inkex import Style

from actions_json import extract_actions_json

__all__ = ["extract_actions_json", "apply_actions"]


def _find_element(svg: inkex.SvgDocumentElement, ref: str) -> Optional[Any]:
    ref = (ref or "").strip()
    if not ref:
        return None
    try:
        elem = svg.getElementById(ref)
        if elem is not None:
            return elem
    except Exception:
        pass
    for elem in svg.descendants():
        try:
            if elem.get_id() == ref:
                return elem
        except Exception:
            pass
        if getattr(elem, "label", None) == ref:
            return elem
    return None


def _target_layer(svg: inkex.SvgDocumentElement, layer_id: Optional[str]) -> Any:
    if layer_id:
        layer = _find_element(svg, layer_id)
        if layer is not None:
            return layer
    return svg.get_current_layer()


def _style_from_action(raw: dict[str, Any]) -> Style:
    style = Style()
    mapping = {
        "fill": "fill",
        "stroke": "stroke",
        "stroke_width": "stroke-width",
        "opacity": "opacity",
        "font_size": "font-size",
    }
    for key, css_key in mapping.items():
        if key in raw and raw[key] is not None:
            style[css_key] = str(raw[key])
    return style


def apply_actions(svg: inkex.SvgDocumentElement, actions: list[dict[str, Any]]) -> list[str]:
    logs: list[str] = []
    if not actions:
        return logs

    for raw in actions:
        op = raw.get("op")
        try:
            if op == "create_rect":
                _apply_create_rect(svg, raw, logs)
            elif op == "create_ellipse":
                _apply_create_ellipse(svg, raw, logs)
            elif op == "create_line":
                _apply_create_line(svg, raw, logs)
            elif op == "create_path":
                _apply_create_path(svg, raw, logs)
            elif op == "create_text":
                _apply_create_text(svg, raw, logs)
            elif op == "set_transform":
                _apply_set_transform(svg, raw, logs)
            elif op == "set_dimensions":
                _apply_set_dimensions(svg, raw, logs)
            elif op == "set_style":
                _apply_set_style(svg, raw, logs)
            elif op == "delete_elements":
                _apply_delete_elements(svg, raw, logs)
            elif op == "rename_element":
                _apply_rename_element(svg, raw, logs)
            elif op == "duplicate_element":
                _apply_duplicate_element(svg, raw, logs)
            elif op == "create_layer":
                _apply_create_layer(svg, raw, logs)
            elif op == "move_to_layer":
                _apply_move_to_layer(svg, raw, logs)
            elif op == "group_elements":
                _apply_group_elements(svg, raw, logs)
            elif op == "set_page_size":
                _apply_set_page_size(svg, raw, logs)
            else:
                logs.append(f"skip unknown op: {op!r}")
        except Exception as exc:
            logs.append(f"error on {op!r}: {exc}")

    return logs


def _apply_create_rect(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    parent = _target_layer(svg, raw.get("layer_id"))
    rect = parent.add(inkex.Rectangle())
    rect.set("x", str(float(raw.get("x", 0))))
    rect.set("y", str(float(raw.get("y", 0))))
    rect.set("width", str(float(raw.get("width", 10))))
    rect.set("height", str(float(raw.get("height", 10))))
    if raw.get("rx") is not None:
        rect.set("rx", str(float(raw["rx"])))
    if raw.get("ry") is not None:
        rect.set("ry", str(float(raw["ry"])))
    if raw.get("id"):
        rect.set_id(str(raw["id"]))
    if raw.get("label"):
        rect.label = str(raw["label"])
    rect.style = _style_from_action(raw) + rect.style
    logs.append(f"create_rect {_elem_log(rect)}")


def _apply_create_ellipse(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    parent = _target_layer(svg, raw.get("layer_id"))
    ell = parent.add(inkex.Ellipse())
    ell.set("cx", str(float(raw.get("cx", 0))))
    ell.set("cy", str(float(raw.get("cy", 0))))
    ell.set("rx", str(float(raw.get("rx", 10))))
    ell.set("ry", str(float(raw.get("ry", 10))))
    if raw.get("id"):
        ell.set_id(str(raw["id"]))
    if raw.get("label"):
        ell.label = str(raw["label"])
    ell.style = _style_from_action(raw) + ell.style
    logs.append(f"create_ellipse {_elem_log(ell)}")


def _apply_create_line(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    parent = _target_layer(svg, raw.get("layer_id"))
    line = parent.add(inkex.Line())
    line.set("x1", str(float(raw.get("x1", 0))))
    line.set("y1", str(float(raw.get("y1", 0))))
    line.set("x2", str(float(raw.get("x2", 10))))
    line.set("y2", str(float(raw.get("y2", 10))))
    if raw.get("id"):
        line.set_id(str(raw["id"]))
    if raw.get("label"):
        line.label = str(raw["label"])
    line.style = _style_from_action(raw) + line.style
    logs.append(f"create_line {_elem_log(line)}")


def _apply_create_path(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    d = raw.get("d")
    if not d:
        raise ValueError("create_path requires d")
    parent = _target_layer(svg, raw.get("layer_id"))
    path = parent.add(inkex.PathElement())
    path.set("d", str(d))
    if raw.get("id"):
        path.set_id(str(raw["id"]))
    if raw.get("label"):
        path.label = str(raw["label"])
    path.style = _style_from_action(raw) + path.style
    logs.append(f"create_path {_elem_log(path)}")


def _apply_create_text(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    parent = _target_layer(svg, raw.get("layer_id"))
    text = parent.add(inkex.TextElement())
    text.set("x", str(float(raw.get("x", 0))))
    text.set("y", str(float(raw.get("y", 0))))
    text.text = str(raw.get("text", ""))
    if raw.get("id"):
        text.set_id(str(raw["id"]))
    if raw.get("label"):
        text.label = str(raw["label"])
    text.style = _style_from_action(raw) + text.style
    logs.append(f"create_text {_elem_log(text)}")


def _apply_set_transform(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    elem = _find_element(svg, str(raw.get("id", "")))
    if elem is None:
        raise ValueError(f"element not found: {raw.get('id')!r}")
    transform = inkex.Transform()
    translate = raw.get("translate")
    if isinstance(translate, (list, tuple)) and len(translate) >= 2:
        transform.add_translate(float(translate[0]), float(translate[1]))
    rotate = raw.get("rotate")
    if rotate is not None:
        transform.add_rotate(float(rotate))
    scale = raw.get("scale")
    if isinstance(scale, (list, tuple)) and len(scale) >= 2:
        transform.add_scale(float(scale[0]), float(scale[1]))
    elif isinstance(scale, (int, float)):
        transform.add_scale(float(scale))
    elem.transform = transform * elem.transform
    logs.append(f"set_transform {_elem_log(elem)}")


def _apply_set_dimensions(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    elem = _find_element(svg, str(raw.get("id", "")))
    if elem is None:
        raise ValueError(f"element not found: {raw.get('id')!r}")
    for key in ("x", "y", "width", "height", "cx", "cy", "rx", "ry", "r"):
        if raw.get(key) is not None:
            elem.set(key, str(float(raw[key])))
    logs.append(f"set_dimensions {_elem_log(elem)}")


def _apply_set_style(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    elem = _find_element(svg, str(raw.get("id", "")))
    if elem is None:
        raise ValueError(f"element not found: {raw.get('id')!r}")
    elem.style = _style_from_action(raw) + elem.style
    logs.append(f"set_style {_elem_log(elem)}")


def _apply_delete_elements(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    ids = raw.get("ids") or []
    if not isinstance(ids, list):
        raise ValueError("delete_elements.ids must be a list")
    for ref in ids:
        elem = _find_element(svg, str(ref))
        if elem is None:
            logs.append(f"delete skip missing: {ref!r}")
            continue
        parent = elem.getparent()
        if parent is not None:
            parent.remove(elem)
            logs.append(f"delete {ref!r}")


def _apply_rename_element(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    elem = _find_element(svg, str(raw.get("id", "")))
    if elem is None:
        raise ValueError(f"element not found: {raw.get('id')!r}")
    if raw.get("new_id"):
        elem.set_id(str(raw["new_id"]))
    if raw.get("new_label"):
        elem.label = str(raw["new_label"])
    logs.append(f"rename {_elem_log(elem)}")


def _apply_duplicate_element(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    elem = _find_element(svg, str(raw.get("id", "")))
    if elem is None:
        raise ValueError(f"element not found: {raw.get('id')!r}")
    copy = elem.copy()
    offset = raw.get("offset") or [10, 10]
    if isinstance(offset, (list, tuple)) and len(offset) >= 2:
        copy.transform.add_translate(float(offset[0]), float(offset[1]))
    if raw.get("new_id"):
        copy.set_id(str(raw["new_id"]))
    else:
        copy.set_random_id()
    parent = elem.getparent()
    if parent is None:
        raise ValueError("element has no parent")
    parent.append(copy)
    logs.append(f"duplicate {_elem_log(copy)}")


def _apply_create_layer(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    layer = svg.getroot().add(inkex.Layer())
    if raw.get("id"):
        layer.set_id(str(raw["id"]))
    else:
        layer.set_random_id("layer")
    layer.label = str(raw.get("label") or raw.get("id") or "Layer")
    layer.set("inkscape:groupmode", "layer")
    logs.append(f"create_layer {_elem_log(layer)}")


def _apply_move_to_layer(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    layer = _find_element(svg, str(raw.get("layer_id", "")))
    if layer is None:
        raise ValueError(f"layer not found: {raw.get('layer_id')!r}")
    ids = raw.get("ids") or []
    for ref in ids:
        elem = _find_element(svg, str(ref))
        if elem is None:
            logs.append(f"move skip missing: {ref!r}")
            continue
        layer.append(elem)
        logs.append(f"move {ref!r} → {layer.get_id()}")


def _apply_group_elements(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    ids = raw.get("ids") or []
    elems = []
    parent = None
    for ref in ids:
        elem = _find_element(svg, str(ref))
        if elem is None:
            logs.append(f"group skip missing: {ref!r}")
            continue
        elems.append(elem)
        if parent is None:
            parent = elem.getparent()
    if not elems or parent is None:
        return
    group = parent.add(inkex.Group())
    if raw.get("group_id"):
        group.set_id(str(raw["group_id"]))
    if raw.get("label"):
        group.label = str(raw["label"])
    for elem in elems:
        group.append(elem)
    logs.append(f"group {_elem_log(group)} ({len(elems)} items)")


def _apply_set_page_size(svg: inkex.SvgDocumentElement, raw: dict[str, Any], logs: list[str]) -> None:
    root = svg.getroot()
    units = str(raw.get("units") or "mm")
    width = float(raw.get("width", 210))
    height = float(raw.get("height", 297))
    root.set("width", f"{width}{units}")
    root.set("height", f"{height}{units}")
    try:
        svg.namedview.set("inkscape:document-units", units)
    except Exception:
        pass
    logs.append(f"set_page_size {width}x{height} {units}")


def _elem_log(elem: Any) -> str:
    try:
        label = getattr(elem, "label", None)
        eid = elem.get_id()
        if label:
            return f"{eid!r} ({label!r})"
        return repr(eid)
    except Exception:
        return "?"
