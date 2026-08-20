"""Pure layout geometry for collision-free topographic map sheets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def scaled(self, factor):
        return Box(*(value * factor for value in (self.x, self.y, self.width, self.height)))

    def intersects(self, other, gap=0.0):
        return not (
            self.right + gap <= other.x
            or other.right + gap <= self.x
            or self.bottom + gap <= other.y
            or other.bottom + gap <= self.y
        )

    def as_tuple(self):
        return (self.x, self.y, self.width, self.height)


@dataclass(frozen=True)
class LayoutGeometry:
    page_width: float
    page_height: float
    boxes: Mapping[str, Box]


def _landscape_boxes(template_key, legend_position, show_legend, show_metadata):
    boxes: Dict[str, Box] = {
        "title": Box(14, 7, 269, 10),
        "subtitle": Box(14, 19, 269, 6),
        "footer": Box(14, 201, 269, 5),
    }
    if template_key == "minimal_poster":
        boxes.update(
            map=Box(8, 30, 281, 158),
            north=Box(270, 190, 11, 11),
            scale=Box(14, 192, 52, 8),
            footer=Box(14, 204, 269, 4),
        )
        return boxes
    if legend_position == "bottom":
        boxes.update(
            map=Box(14, 33, 269, 130),
            north=Box(269, 174, 13, 13),
            scale=Box(199, 173, 55, 9),
        )
        if show_legend:
            boxes["legend"] = Box(14, 172, 176, 21)
        if show_metadata:
            boxes["metadata"] = Box(199, 185, 63, 8)
        return boxes
    map_width = 220 if template_key == "engineering_titleblock" else 216
    map_x = 12 if template_key == "engineering_titleblock" else 14
    boxes.update(
        map=Box(map_x, 33, map_width, 158),
        north=Box(253, 34, 18, 18),
        scale=Box(240, 145, 45, 10),
    )
    if show_legend:
        boxes["legend"] = Box(240, 59, 45, 80)
    if show_metadata:
        boxes["metadata"] = Box(240, 161, 45, 27)
    return boxes


def _portrait_boxes(template_key, show_legend, show_metadata):
    boxes: Dict[str, Box] = {
        "title": Box(13, 7, 184, 10),
        "subtitle": Box(13, 19, 184, 6),
        "footer": Box(13, 284, 184, 5),
    }
    if template_key == "minimal_poster":
        boxes.update(
            map=Box(8, 30, 194, 228),
            north=Box(180, 263, 12, 12),
            scale=Box(13, 264, 60, 8),
        )
        return boxes
    boxes.update(
        map=Box(13, 33, 184, 187),
        north=Box(177, 231, 15, 15),
        scale=Box(110, 250, 82, 9),
    )
    if show_legend:
        boxes["legend"] = Box(13, 231, 90, 42)
    if show_metadata:
        boxes["metadata"] = Box(110, 263, 82, 10)
    return boxes


def plan_layout_geometry(
    template_key,
    legend_position,
    page_width,
    page_height,
    *,
    show_legend=True,
    show_metadata=True,
):
    """Return scaled, non-overlapping safe zones for every layout item."""

    landscape = page_width > page_height
    if landscape:
        base_width, base_height = 297.0, 210.0
        boxes = _landscape_boxes(
            template_key, legend_position, show_legend, show_metadata
        )
    else:
        base_width, base_height = 210.0, 297.0
        boxes = _portrait_boxes(template_key, show_legend, show_metadata)
    scale = min(page_width / base_width, page_height / base_height)
    return LayoutGeometry(
        page_width=float(page_width),
        page_height=float(page_height),
        boxes={name: box.scaled(scale) for name, box in boxes.items()},
    )


def validate_layout_geometry(geometry, gap=1.0) -> Tuple[str, ...]:
    """Return page-bound or collision errors for active map furniture."""

    errors = []
    for name, box in geometry.boxes.items():
        if (
            box.x < 0
            or box.y < 0
            or box.right > geometry.page_width + 1e-6
            or box.bottom > geometry.page_height + 1e-6
        ):
            errors.append(f"{name}: outside page bounds")
    names = tuple(geometry.boxes)
    for index, left_name in enumerate(names):
        for right_name in names[index + 1 :]:
            if geometry.boxes[left_name].intersects(
                geometry.boxes[right_name], gap=gap
            ):
                errors.append(f"{left_name}: overlaps {right_name}")
    return tuple(errors)
