"""Draw declared room subjects from a frozen evaluated native snapshot."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
from matplotlib.ticker import MaxNLocator
import numpy as np

DEFAULT_LEGEND = 'Blue-gray: architecture   •   Ochre: services   •   Purple: contents   •   Dashed: finish footprint, including crops and open seams'


def legend_text(view):
    legend = view.get('legend')
    if legend is None:
        return DEFAULT_LEGEND
    if not isinstance(legend, dict) or legend.get('mode') not in ('default', 'none', 'explicit'):
        raise ValueError(f"{view['id']} legend mode must be default, none, or explicit")
    if legend['mode'] == 'default':
        return DEFAULT_LEGEND
    if legend['mode'] == 'none':
        return ''
    items = legend.get('items')
    if not isinstance(items, list) or not all(isinstance(item, str) and item for item in items):
        raise ValueError(f"{view['id']} explicit legend items must be non-empty strings")
    return '   •   '.join(items)


def apply_view_presentation(ax, view):
    show_coordinates = view.get('show_coordinates', True)
    if not isinstance(show_coordinates, bool):
        raise ValueError(f"{view['id']} show_coordinates must be boolean")
    if not show_coordinates:
        ax.set_axis_off()
        ax.grid(False)
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.tick_params(bottom=False, left=False, labelbottom=False, labelleft=False)
        ax.set_xlabel('')
        ax.set_ylabel('')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_view_frame(view):
    if 'view_direction_frame' not in view:
        raise ValueError(f"{view['id']} must declare view_direction_frame")
    right = np.asarray(view['right_frame'], float)
    up = np.asarray(view['up_frame'], float)
    direction = np.asarray(view['view_direction_frame'], float)
    if any(vector.shape != (3,) for vector in (right, up, direction)):
        raise ValueError(f"{view['id']} frame vectors must have three components")
    if not all(np.all(np.isfinite(vector)) for vector in (right, up, direction)):
        raise ValueError(f"{view['id']} frame vectors must be finite")
    if not np.allclose([np.linalg.norm(right), np.linalg.norm(up), np.linalg.norm(direction)], 1.0, atol=1e-7):
        raise ValueError(f"{view['id']} frame vectors must be unit length")
    if not np.allclose([np.dot(right, up), np.dot(right, direction), np.dot(up, direction)], 0.0, atol=1e-7):
        raise ValueError(f"{view['id']} frame vectors must be mutually orthogonal")
    reflection_field = 'horizontal_reflection_of_upward_camera'
    reflected = view.get(reflection_field, False)
    if not isinstance(reflected, bool):
        raise ValueError(f"{view['id']} {reflection_field} must be boolean")
    if reflected and view['kind'] != 'reflected_ceiling':
        raise ValueError(f"{view['id']} {reflection_field} is only valid for reflected_ceiling")
    if reflected and not np.allclose(direction, [0.0, 0.0, 1.0], atol=1e-7):
        raise ValueError(f"{view['id']} {reflection_field} requires an upward +Z view_direction_frame")
    expected_right = np.cross(direction, up)
    if reflected:
        expected_right = -expected_right
    if not np.allclose(right, expected_right, atol=1e-7):
        relation = '-cross(view_direction_frame, up_frame)' if reflected else 'cross(view_direction_frame, up_frame)'
        raise ValueError(f"{view['id']} right_frame must equal {relation}")
    if view['kind'] == 'reflected_ceiling' and not reflected:
        raise ValueError(f"{view['id']} reflected_ceiling must explicitly declare {reflection_field}")


def validate_section_marks(specification):
    """Validate plan section marks against their uniquely named section views."""
    sections = [view for view in specification.get('views', []) if view.get('kind') == 'section']
    marks = specification.get('section_marks', [])
    for mark in marks:
        mark_id = mark.get('section_id', mark.get('label', '<unnamed>'))
        section_id = mark.get('section_id')
        if not isinstance(section_id, str) or not section_id:
            raise ValueError(f"section mark {mark_id} must declare section_id")
        matches = [view for view in sections if view.get('id') == section_id]
        if len(matches) != 1:
            raise ValueError(f"section mark {mark_id} must reference one section view")
        section = matches[0]
        cut = section.get('cut', {})
        axis = mark.get('axis')
        value = mark.get('value_m')
        try:
            value = float(value)
            cut_value = float(cut['value_m'])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"section mark {mark_id} cut must use finite numeric values")
        if (isinstance(axis, bool) or axis != cut.get('axis') or not np.isfinite(value)
                or not np.isfinite(cut_value) or not np.isclose(value, cut_value, atol=1e-9, rtol=0)):
            raise ValueError(f"section mark {mark_id} cut does not match section {section_id}")
        if axis not in (0, 1):
            raise ValueError(f"section mark {mark_id} must use plan axis 0 or 1")
        arrow_from = np.asarray(mark.get('arrow_from'), float)
        arrow_to = np.asarray(mark.get('arrow_to'), float)
        if arrow_from.shape != (2,) or arrow_to.shape != (2,) or not np.isfinite(arrow_from).all() or not np.isfinite(arrow_to).all():
            raise ValueError(f"section mark {mark_id} arrow endpoints must be finite 2-D points")
        delta = arrow_to - arrow_from
        length = np.linalg.norm(delta)
        direction = np.asarray(section.get('view_direction_frame', []), float)
        plan_direction = direction[:2] if direction.shape == (3,) else np.asarray([])
        if length <= 1e-12 or plan_direction.shape != (2,) or not np.isfinite(plan_direction).all():
            raise ValueError(f"section mark {mark_id} arrow must have a finite nonzero plan direction")
        direction_length = np.linalg.norm(plan_direction)
        parallel_error = abs(delta[0] * plan_direction[1] - delta[1] * plan_direction[0])
        if direction_length <= 1e-12 or parallel_error > 1e-7 * length * direction_length or np.dot(delta, plan_direction) <= 0:
            raise ValueError(f"section mark {mark_id} arrow must follow section {section_id} view direction")


def segment_length_inside_bounds(segment, bounds):
    """Return the positive length of a 2-D segment inside rectangular bounds."""
    start, end = np.asarray(segment[0], float), np.asarray(segment[1], float)
    delta = end - start
    lower = np.asarray(bounds[::2], float)
    upper = np.asarray(bounds[1::2], float)
    first, last = 0.0, 1.0
    for axis in range(2):
        if abs(delta[axis]) <= 1e-15:
            if start[axis] < lower[axis] or start[axis] > upper[axis]:
                return 0.0
            continue
        near = (lower[axis] - start[axis]) / delta[axis]
        far = (upper[axis] - start[axis]) / delta[axis]
        if near > far:
            near, far = far, near
        first, last = max(first, near), min(last, far)
        if first >= last:
            return 0.0
    return float(np.linalg.norm(delta) * max(0.0, last - first))


def segment_is_subsegment(segment, source, tolerance=1e-7):
    """Return whether a finite segment lies on a source segment."""
    segment = np.asarray(segment, float)
    source = np.asarray(source, float)
    source_delta = source[1] - source[0]
    source_length_squared = source_delta @ source_delta
    if source_length_squared <= tolerance * tolerance:
        return False
    for point in segment:
        parameter = ((point - source[0]) @ source_delta) / source_length_squared
        nearest = source[0] + parameter * source_delta
        if parameter < -tolerance or parameter > 1.0 + tolerance:
            return False
        if np.linalg.norm(point - nearest) > tolerance:
            return False
    return True


def validate_boundary_tolerance(subject, view_id, object_id):
    """Return a subject boundary tolerance after finite-positive validation."""
    value = subject.get('boundary_tolerance_m', 1e-7)
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{view_id} subject {object_id} boundary tolerance must be finite and positive")
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{view_id} subject {object_id} boundary tolerance must be finite and positive")
    return value


def validate_boundary_line_tolerance(subject, view_id, object_id, boundary_tolerance):
    """Return a subject supporting-line tolerance after validation."""
    value = subject.get('boundary_line_tolerance_m', boundary_tolerance)
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{view_id} subject {object_id} boundary line tolerance must be finite and positive")
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{view_id} subject {object_id} boundary line tolerance must be finite and positive")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--views', type=Path, required=True)
    parser.add_argument('--math-helper', type=Path, required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--output-stem', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    module = importlib.util.spec_from_file_location('drawing_math', args.math_helper)
    math = importlib.util.module_from_spec(module)
    module.loader.exec_module(math)
    native = json.loads(args.native.read_text())
    specification = json.loads(args.views.read_text())
    validate_section_marks(specification)
    args.output.mkdir(exist_ok=False)
    assert native['model_sha256'] == specification['model_sha256']
    assert digest(args.native) == specification['native_sha256']
    assert native['all_visible_guard']
    objects = {row['name']: row for row in native['objects']}
    basis = np.asarray(specification['frame_axes_world'], float)
    assert np.allclose(basis @ basis.T, np.eye(3), atol=1e-7)
    vertices = {name: np.asarray(row['vertices_world_m'], dtype=float).reshape(-1, 3) @ basis.T
                for name, row in objects.items()}
    triangles_by_polygon = {}
    for name, row in objects.items():
        per_polygon = {}
        for triangle in row['loop_triangles']:
            per_polygon.setdefault(triangle['polygon_index'], []).append(
                np.asarray(triangle['vertex_indices'], int))
        triangles_by_polygon[name] = per_polygon
    styles = specification['styles']
    records = []
    manifest = {'status': 'declared_before_drawing', 'native_path': str(args.native),
                'native_sha256': digest(args.native), 'model_sha256': native['model_sha256'],
                'view_specification': specification, 'views_sha256': digest(args.views),
                'math_helper_sha256': digest(args.math_helper),
                'producer_sha256': digest(__file__), 'no_model_edit': True,
                'nondrawable_objects': [], 'omitted_objects': []}
    manifest_path = args.output / 'drawing-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

    def render(ax, view, overview=False):
        selection = {}
        nondrawable_objects = []
        omitted_objects = []
        validate_view_frame(view)
        right, up = view['right_frame'], view['up_frame']
        bounds = view['bounds_frame']
        emitted_segments = []
        for subject in view['subjects']:
            name = subject['object_id']
            row, points = objects[name], vertices[name]
            edge_mode = subject.get('edge_mode', 'existing_edges')
            if edge_mode not in ('existing_edges', 'coplanar_boundary'):
                raise ValueError(f"{view['id']} subject {name} has unsupported edge_mode")
            boundary_tolerance = validate_boundary_tolerance(subject, view['id'], name)
            boundary_line_tolerance = validate_boundary_line_tolerance(
                subject, view['id'], name, boundary_tolerance)
            if edge_mode == 'coplanar_boundary' and view['kind'] == 'section':
                raise ValueError(f"{view['id']} subject {name} cannot use coplanar_boundary in a section")
            classification = math.classify_selected_geometry(
                row['vertices_world_m'], row['polygons'], subject['face_indices'])
            if not classification['finite']:
                raise ValueError(f"{view['id']} selected polygon vertices for {name} are non-finite")
            if classification['all_vertices_coincident']:
                nondrawable_objects.append({
                    'view_id': view['id'], 'object_id': name,
                    'reason': 'selected_polygon_vertices_coincident',
                    'vertex_indices': classification['vertex_indices'],
                    'unique_point_count': classification['unique_point_count'],
                })
                continue
            color = styles[subject['style']]['color']
            segments = []
            face_segments = {}
            boundary_faces = []
            for index in subject['face_indices']:
                polygon = points[np.asarray(row['polygons'][index], int)]
                pieces_to_cut = [polygon]
                if view['kind'] == 'section':
                    cut = view['cut']
                    coplanar = np.max(np.abs(polygon[:, cut['axis']] - cut['value_m'])) <= math.EPS
                    if not coplanar:
                        pieces_to_cut = [points[vertex_indices]
                                         for vertex_indices in triangles_by_polygon[name].get(index, [])]
                        assert pieces_to_cut, (name, index)
                drawn = False
                for face in pieces_to_cut:
                    for crop in (view.get('spatial_clips', []) +
                                 subject.get('spatial_clips', [])):
                        face = math.clipped(face, crop['axis'], crop['value_m'], crop['keep_below'])
                        if len(face) < 2:
                            break
                    if len(face) < 2:
                        continue
                    if view['kind'] == 'section':
                        cut = view['cut']
                        face = np.asarray(math.intersect_face(face, cut['axis'], cut['value_m']))
                    elif view['kind'] in ('plan', 'reflected_ceiling'):
                        cut = view['cut']
                        face = math.clipped(face, cut['axis'], cut['value_m'], cut['keep_below'])
                    if len(face) < 2:
                        continue
                    projected = math.project(face, right, up)
                    pieces = [edge for edge in math.line_segments(projected)
                              if np.linalg.norm(edge[1] - edge[0]) > 1e-7]
                    if not pieces:
                        continue
                    segments.extend(pieces)
                    face_segments.setdefault(index, []).extend(pieces)
                    boundary_faces.append((index, face))
                    drawn = True
                    if subject.get('fill', False) and view['kind'] != 'section' and len(projected) > 2:
                        ax.add_patch(Polygon(projected, closed=True, facecolor=color,
                                             edgecolor='none', alpha=.085))
                if not drawn:
                    face_segments.pop(index, None)
            if edge_mode == 'coplanar_boundary':
                boundary_records = math.coplanar_boundary_records(
                    [face for _, face in boundary_faces],
                    tolerance=boundary_tolerance,
                    line_tolerance=boundary_line_tolerance)
                boundary_segments = []
                face_segments = {}
                for owner, edge in boundary_records:
                    if np.linalg.norm(edge[1] - edge[0]) <= 1e-7:
                        continue
                    boundary_segments.append(edge)
                    index, _ = boundary_faces[owner]
                    face_segments.setdefault(index, []).append(edge)
                segments = [math.project(edge, right, up) for edge in boundary_segments]
                face_segments = {
                    index: [math.project(edge, right, up) for edge in edges]
                    for index, edges in face_segments.items()
                }
            used = [index for index in subject['face_indices']
                    if any(segment_length_inside_bounds(edge, bounds) > 1e-9
                           for edge in face_segments.get(index, []))]
            if segments:
                emitted_segments.extend(segments)
                unique = {tuple(sorted(tuple(np.round(p, 7)) for p in edge)): edge
                          for edge in segments}
                ax.add_collection(LineCollection(list(unique.values()), colors=color,
                    linewidths=.8 if subject['style'] == 'architecture' else .55,
                    linestyles='--' if subject.get('crop_boundary') and view['kind'] in ('plan', 'reflected_ceiling') else '-', alpha=.85))
                if used:
                    selection[name] = used
                else:
                    omitted_objects.append({
                        'view_id': view['id'], 'object_id': name,
                        'reason': 'selected_faces_have_no_segments_inside_declared_bounds',
                        'face_indices': list(subject['face_indices']),
                    })
            else:
                omitted_objects.append({
                    'view_id': view['id'], 'object_id': name,
                    'reason': 'selected_faces_emitted_no_segments_after_cuts_or_clips',
                    'face_indices': list(subject['face_indices']),
                })
        emitted_length_inside_bounds = sum(
            segment_length_inside_bounds(segment, bounds)
            for segment in emitted_segments
        )
        if emitted_length_inside_bounds <= 1e-9:
            raise ValueError(f"{view['id']} emits no geometry inside its declared bounds")
        ax.set_xlim(bounds[:2])
        ax.set_ylim(bounds[2:])
        ax.set_aspect('equal')
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        x_span, y_span = bounds[1] - bounds[0], bounds[3] - bounds[2]
        if y_span > 0 and x_span / y_span < 0.3:
            for label in ax.get_xticklabels():
                label.set_rotation(90)
                label.set_ha('center')
        ax.grid(True, color='#cbd5e1', lw=.4, alpha=.6)
        ax.tick_params(labelsize=7 if overview else 10)
        if not overview and view.get('show_coordinates', True):
            ax.set_xlabel(view['axis_labels'][0] + ' (model m)', fontsize=10)
            ax.set_ylabel(view['axis_labels'][1] + ' (model m)', fontsize=10)
        if view['kind'] == 'plan':
            for mark in specification['section_marks']:
                axis, value = mark['axis'], mark['value_m']
                if axis == 1:
                    ax.axhline(value, color='#985044', ls='--', lw=.8)
                else:
                    ax.axvline(value, color='#365d8c', ls='--', lw=.8)
                ax.annotate(mark['label'], xy=mark['arrow_to'], xytext=mark['arrow_from'],
                    fontsize=8, color=mark['color'], ha='center', va='center',
                    arrowprops={'arrowstyle': '-|>', 'color': mark['color']})
        for note in view.get('annotations', []):
            if overview and not note.get('overview', False):
                continue
            ax.annotate(note['text'], xy=note['point'], xytext=note['text_position'],
                fontsize=7 if overview else 9, ha=note.get('ha', 'center'), va='center',
                color='#475569', arrowprops={'arrowstyle': '-', 'color': '#64748b', 'lw': .65},
                bbox={'facecolor': 'white', 'edgecolor': 'none', 'alpha': .9, 'pad': 2})
        apply_view_presentation(ax, view)
        return {'view_id': view['id'], 'drawn_faces': selection,
                'emitted_length_inside_bounds': emitted_length_inside_bounds,
                'nondrawable_objects': nondrawable_objects,
                'omitted_objects': omitted_objects}

    room_title = args.title
    output_stem = args.output_stem
    figures = []
    for view in specification['views']:
        fig = plt.figure(figsize=(420 / 25.4, 297 / 25.4), facecolor='white')
        fig.text(.055, .949, view['id'] + ' | ' + room_title + ' — ' + view['title'],
                 fontsize=19, weight='bold')
        fig.text(.055, .918, view['note'], fontsize=10, color='#475569')
        ax = fig.add_axes([.12, .17, .76, .69])
        record = render(ax, view)
        assert record['drawn_faces'], view['id']
        records.append(record)
        legend = legend_text(view)
        if legend:
            fig.text(.055, .075, legend, fontsize=10, color='#475569')
        fig.text(.055, .045, 'Current-model documentation. Hidden cores, exact contacts, physical room extents and survey accuracy remain unestablished.',
                 fontsize=9, color='#475569')
        fig.savefig(args.output / (view['id'] + '.png'), dpi=130)
        figures.append(fig)
    pdf = args.output / f'{output_stem}-geometry.pdf'
    with PdfPages(pdf) as output:
        for fig in figures:
            output.savefig(fig)
            plt.close(fig)
    overview_pages = [specification['views'][start:start + 6]
                      for start in range(0, len(specification['views']), 6)]
    for page_number, page_views in enumerate(overview_pages, 1):
        fig, axes = plt.subplots(2, 3, figsize=(16, 10), dpi=130)
        page_label = '' if len(overview_pages) == 1 else \
            f' — OVERVIEW {page_number}/{len(overview_pages)}'
        fig.suptitle(room_title + ' — CURRENT MODEL' + page_label,
                     fontsize=19, weight='bold')
        for ax, view in zip(axes.ravel(), page_views):
            render(ax, view, overview=True)
            ax.set_title(view['title'], fontsize=11)
        for ax in axes.ravel()[len(page_views):]:
            ax.set_visible(False)
        fig.tight_layout(rect=(.015, .03, .985, .93), h_pad=3.0, w_pad=2.0)
        fig.text(.04, .018,
                 'Dashed: finish footprint, including crops and open seams. '
                 'Current-model documentation; hidden cores and exact contacts remain unestablished.',
                 fontsize=10, color='#475569')
        overview_name = (f'{output_stem}-overview.png' if len(overview_pages) == 1 else
                         f'{output_stem}-overview-{page_number:02d}.png')
        fig.savefig(args.output / overview_name)
        plt.close(fig)
    manifest['status'] = 'generated_pending_root_review'
    manifest['rendered_selections'] = records
    manifest['nondrawable_objects'] = [item for record in records
                                       for item in record['nondrawable_objects']]
    manifest['omitted_objects'] = [item for record in records
                                   for item in record['omitted_objects']]
    manifest['outputs'] = [{'path': p.name, 'sha256': digest(p)}
                           for p in sorted(args.output.iterdir()) if p.suffix in ('.png', '.pdf')]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'status': 'ok', 'geometry_pages': len(figures), 'pdf': str(pdf)}))


if __name__ == '__main__':
    main()
