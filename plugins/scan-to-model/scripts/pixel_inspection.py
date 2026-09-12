"""Inspect native pixel centers with exact source context and explicit crop edges."""

import copy
from io import BytesIO
import math
from PIL import Image, ImageDraw, ImageFont

REVIEW_PADDING_PX = 32


COORDINATE_CONTEXT_RADIUS_PX = 128
COORDINATE_CONTEXT_MAGNIFICATION = 1
COORDINATE_DETAIL_RADIUS_PX = 4
COORDINATE_DETAIL_MAGNIFICATION = 12
COORDINATE_ROWS_PER_COLUMN = 8
COORDINATE_PADDING = 12
COORDINATE_LABEL_HEIGHT = 62
COORDINATE_PANEL_GAP = 12
COORDINATE_CELL_GAP = 12
COORDINATE_COLUMN_GAP = 24
COORDINATE_OUTSIDE_COLOR = (36, 36, 36, 255)
COORDINATE_BACKGROUND_COLOR = (246, 246, 246, 255)
COORDINATE_LOCATOR_COLOR = (255, 45, 32, 255)


def format_number(value):
    if isinstance(value, int):
        return str(value)
    return format(value, ".15g")


def display_pixel_center(point, source):
    u, v = point
    if source["orientation"] == "raw":
        return [u, v]
    return [source["height"] - 1 - v, u]


def native_pixel_center(point, source):
    display_u, display_v = point
    if source["orientation"] == "raw":
        return [display_u, display_v]
    return [display_v, source["height"] - 1 - display_u]


def display_dimensions(source):
    if source["orientation"] == "upright90cw":
        return source["height"], source["width"]
    return source["width"], source["height"]


def display_crop_pixel_edges(display_coordinates, source):
    width, height = display_dimensions(source)
    xs = [point[0] + 0.5 for point in display_coordinates]
    ys = [point[1] + 0.5 for point in display_coordinates]
    return [
        max(0, math.floor(min(xs) - REVIEW_PADDING_PX)),
        max(0, math.floor(min(ys) - REVIEW_PADDING_PX)),
        min(width, math.ceil(max(xs) + REVIEW_PADDING_PX)),
        min(height, math.ceil(max(ys) + REVIEW_PADDING_PX)),
    ]


def nearest_pixel_center(value):
    return math.floor(value + 0.5)


def patch_inspection_bytes(source, displayed, display_coordinates):
    """Show the entire polygon and surrounding pixels without covering the source panel."""
    bounds = display_crop_pixel_edges(display_coordinates, source)
    magnification = 3
    crop = displayed.crop(bounds)
    crop = crop.resize((crop.width * magnification, crop.height * magnification), Image.Resampling.NEAREST)
    marked = crop.copy()
    polygon = [((u + .5 - bounds[0]) * magnification - .5,
                (v + .5 - bounds[1]) * magnification - .5)
               for u, v in display_coordinates]
    ImageDraw.Draw(marked).line(polygon + polygon[:1], fill=COORDINATE_LOCATOR_COLOR, width=2)
    padding, label_height, gap = 12, 24, 12
    sheet = Image.new('RGBA', (crop.width * 2 + padding * 2 + gap,
                               crop.height + padding * 2 + label_height), COORDINATE_BACKGROUND_COLOR)
    draw = ImageDraw.Draw(sheet)
    panel_top = padding + label_height
    unmarked_left, marked_left = padding, padding + crop.width + gap
    draw.text((unmarked_left, padding), 'Unmarked source / 3x nearest', fill='black')
    draw.text((marked_left, padding), 'Selected polygon / 3x nearest', fill='black')
    sheet.paste(crop, (unmarked_left, panel_top))
    sheet.paste(marked, (marked_left, panel_top))
    output = BytesIO()
    sheet.save(output, format='PNG', compress_level=9)
    return output.getvalue(), {
        'display_bounds_pixel_edges': bounds,
        'context_padding_display_pixels': REVIEW_PADDING_PX,
        'magnification': magnification,
        'resampling': 'nearest',
        'unmarked_bounds': [unmarked_left, panel_top, unmarked_left + crop.width, panel_top + crop.height],
        'marked_bounds': [marked_left, panel_top, marked_left + crop.width, panel_top + crop.height],
    }


def _coordinate_context(image, coordinate, radius, magnification):
    size = radius * 2 + 1
    x, y = coordinate
    left = max(0, x - radius)
    top = max(0, y - radius)
    right = min(image.width, x + radius + 1)
    bottom = min(image.height, y + radius + 1)
    context = Image.new("RGBA", (size, size), COORDINATE_OUTSIDE_COLOR)
    context.paste(
        image.crop((left, top, right, bottom)),
        (radius - (x - left), radius - (y - top)),
    )
    return context.resize(
        (size * magnification, size * magnification),
        Image.Resampling.NEAREST,
    )


def _draw_open_pixel_locator(image):
    draw = ImageDraw.Draw(image)
    start = COORDINATE_DETAIL_RADIUS_PX * COORDINATE_DETAIL_MAGNIFICATION
    end = start + COORDINATE_DETAIL_MAGNIFICATION - 1
    margin = 3
    length = 7
    corners = [
        [(start - margin, start + length), (start - margin, start - margin),
         (start + length, start - margin)],
        [(end - length, start - margin), (end + margin, start - margin),
         (end + margin, start + length)],
        [(start - margin, end - length), (start - margin, end + margin),
         (start + length, end + margin)],
        [(end - length, end + margin), (end + margin, end + margin),
         (end + margin, end - length)],
    ]
    for points in corners:
        draw.line(points, fill=COORDINATE_LOCATOR_COLOR, width=2)


def _draw_open_context_locator(image):
    draw = ImageDraw.Draw(image)
    center = COORDINATE_CONTEXT_RADIUS_PX * COORDINATE_CONTEXT_MAGNIFICATION
    gap = 6
    length = 18
    lines = [
        (center - length, center, center - gap, center),
        (center + gap, center, center + length, center),
        (center, center - length, center, center - gap),
        (center, center + gap, center, center + length),
    ]
    for line in lines:
        draw.line(line, fill=COORDINATE_LOCATOR_COLOR, width=3)


def _coordinate_grid_position(index, count, columns):
    short_column_size = count // columns
    long_columns = count % columns
    long_column_size = short_column_size + 1
    long_column_items = long_columns * long_column_size
    if index < long_column_items:
        return index // long_column_size, index % long_column_size
    offset = index - long_column_items
    return long_columns + offset // short_column_size, offset % short_column_size


def coordinate_inspection_bytes(source, displayed, annotation):
    count = len(annotation["native_coordinates"])
    columns = math.ceil(count / COORDINATE_ROWS_PER_COLUMN)
    rows = math.ceil(count / columns)
    context_size = (
        (COORDINATE_CONTEXT_RADIUS_PX * 2 + 1) * COORDINATE_CONTEXT_MAGNIFICATION
    )
    detail_size = (
        (COORDINATE_DETAIL_RADIUS_PX * 2 + 1) * COORDINATE_DETAIL_MAGNIFICATION
    )
    cell_width = context_size * 2 + detail_size + COORDINATE_PANEL_GAP * 2
    cell_height = COORDINATE_LABEL_HEIGHT + context_size + COORDINATE_CELL_GAP
    width = (
        COORDINATE_PADDING * 2
        + columns * cell_width
        + (columns - 1) * COORDINATE_COLUMN_GAP
    )
    height = COORDINATE_PADDING * 2 + rows * cell_height - COORDINATE_CELL_GAP
    sheet = Image.new("RGBA", (width, height), COORDINATE_BACKGROUND_COLOR)
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    records = []
    for index, (native, display) in enumerate(zip(
        annotation["native_coordinates"], annotation["display_coordinates"]
    )):
        nearest_native = [nearest_pixel_center(value) for value in native]
        nearest_display = display_pixel_center(nearest_native, source)
        context = _coordinate_context(
            displayed,
            nearest_display,
            COORDINATE_CONTEXT_RADIUS_PX,
            COORDINATE_CONTEXT_MAGNIFICATION,
        )
        located_context = context.copy()
        _draw_open_context_locator(located_context)
        detail = _coordinate_context(
            displayed,
            nearest_display,
            COORDINATE_DETAIL_RADIUS_PX,
            COORDINATE_DETAIL_MAGNIFICATION,
        )
        _draw_open_pixel_locator(detail)
        column, row = _coordinate_grid_position(index, count, columns)
        left = COORDINATE_PADDING + column * (cell_width + COORDINATE_COLUMN_GAP)
        top = COORDINATE_PADDING + row * cell_height
        panel_top = top + COORDINATE_LABEL_HEIGHT
        located_left = left + context_size + COORDINATE_PANEL_GAP
        detail_left = located_left + context_size + COORDINATE_PANEL_GAP
        draw.text(
            (left, top),
            f"#{index} native ({format_number(native[0])}, {format_number(native[1])})",
            fill=(0, 0, 0, 255),
            font=font,
        )
        draw.text(
            (left, top + 14),
            f"display ({format_number(display[0])}, {format_number(display[1])})",
            fill=(0, 0, 0, 255),
            font=font,
        )
        draw.text(
            (left, top + 28),
            f"nearest native pixel ({nearest_native[0]}, {nearest_native[1]})",
            fill=(0, 0, 0, 255),
            font=font,
        )
        draw.text((left, top + 42), "unmarked context", fill=(0, 0, 0, 255), font=font)
        draw.text(
            (located_left, top + 42), "located context", fill=(0, 0, 0, 255), font=font
        )
        draw.text((detail_left, top + 42), "exact pixel", fill=(0, 0, 0, 255), font=font)
        sheet.paste(context, (left, panel_top))
        sheet.paste(located_context, (located_left, panel_top))
        sheet.paste(detail, (detail_left, panel_top))
        records.append({
            "index": index,
            "native": copy.deepcopy(native),
            "display": copy.deepcopy(display),
            "nearest_native_pixel": nearest_native,
            "nearest_display_pixel": nearest_display,
            "unmarked_context_bounds": [
                left, panel_top, left + context_size, panel_top + context_size,
            ],
            "located_context_bounds": [
                located_left, panel_top,
                located_left + context_size, panel_top + context_size,
            ],
            "detail_bounds": [
                detail_left, panel_top, detail_left + detail_size, panel_top + detail_size,
            ],
        })
    output = BytesIO()
    sheet.save(output, format="PNG", compress_level=9)
    return output.getvalue(), records
