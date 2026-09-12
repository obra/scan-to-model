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


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--views', type=Path, required=True)
    parser.add_argument('--math-helper', type=Path, required=True)
    parser.add_argument('--title', required=True)
    parser.add_argument('--output-stem', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(exist_ok=False)
    module = importlib.util.spec_from_file_location('drawing_math', args.math_helper)
    math = importlib.util.module_from_spec(module)
    module.loader.exec_module(math)
    native = json.loads(args.native.read_text())
    specification = json.loads(args.views.read_text())
    assert native['model_sha256'] == specification['model_sha256']
    assert digest(args.native) == specification['native_sha256']
    assert native['all_visible_guard']
    objects = {row['name']: row for row in native['objects']}
    basis = np.asarray(specification['frame_axes_world'], float)
    assert np.allclose(basis @ basis.T, np.eye(3), atol=1e-7)
    vertices = {name: np.asarray(row['vertices_world_m']) @ basis.T
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
                'producer_sha256': digest(__file__), 'no_model_edit': True}
    manifest_path = args.output / 'drawing-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')

    def render(ax, view, overview=False):
        selection = {}
        right, up = view['right_frame'], view['up_frame']
        for subject in view['subjects']:
            name = subject['object_id']
            row, points = objects[name], vertices[name]
            color = styles[subject['style']]['color']
            segments, used = [], []
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
                    for crop in view.get('spatial_clips', []):
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
                    drawn = True
                    if subject.get('fill', False) and view['kind'] != 'section' and len(projected) > 2:
                        ax.add_patch(Polygon(projected, closed=True, facecolor=color,
                                             edgecolor='none', alpha=.085))
                if drawn:
                    used.append(index)
            if segments:
                unique = {tuple(sorted(tuple(np.round(p, 7)) for p in edge)): edge
                          for edge in segments}
                ax.add_collection(LineCollection(list(unique.values()), colors=color,
                    linewidths=.8 if subject['style'] == 'architecture' else .55,
                    linestyles='--' if subject.get('crop_boundary') and view['kind'] in ('plan', 'reflected_ceiling') else '-', alpha=.85))
                selection[name] = used
        bounds = view['bounds_frame']
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
        if not overview:
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
        return {'view_id': view['id'], 'drawn_faces': selection}

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
        fig.text(.055, .075, 'Blue-gray: architecture   •   Ochre: services   •   Purple: contents   •   Dashed: finish footprint, including crops and open seams',
                 fontsize=10, color='#475569')
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
    manifest['outputs'] = [{'path': p.name, 'sha256': digest(p)}
                           for p in sorted(args.output.iterdir()) if p.suffix in ('.png', '.pdf')]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'status': 'ok', 'geometry_pages': len(figures), 'pdf': str(pdf)}))


if __name__ == '__main__':
    main()
