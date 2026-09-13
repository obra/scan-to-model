"""Behavioral tests for the generic declared room drawing producer."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import importlib.util


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PRODUCER = PLUGIN_ROOT / 'scripts' / 'draw_room.py'
MATH_HELPER = PLUGIN_ROOT / 'scripts' / 'drawing.py'
SPEC = importlib.util.spec_from_file_location('draw_room', PRODUCER)
DRAW_ROOM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRAW_ROOM)


class DrawRoomTests(unittest.TestCase):
    def test_section_marks_follow_referenced_section_cut_and_direction(self):
        section = {
            'id': 'S1', 'kind': 'section', 'cut': {'axis': 0, 'value_m': 6.0},
            'view_direction_frame': [-1, 0, 0],
        }
        base = {'views': [section]}
        valid = {'section_id': 'S1', 'axis': 0, 'value_m': 6.0,
                 'arrow_from': [6.3, -1.0], 'arrow_to': [5.8, -1.0]}
        DRAW_ROOM.validate_section_marks(dict(base, section_marks=[valid]))
        for bad in [
            dict(valid, arrow_from=[5.8, -1.0], arrow_to=[6.3, -1.0]),
            dict(valid, arrow_from=[6.0, -1.0], arrow_to=[6.0, -1.5]),
            dict(valid, axis=1, value_m=-1.0),
        ]:
            with self.assertRaises(ValueError):
                DRAW_ROOM.validate_section_marks(dict(base, section_marks=[bad]))
        for direction, arrow_from, arrow_to in [
            ([0, -1, 0], [1.0, -1.7], [1.0, -2.3]),
            ([0, 1, 0], [1.0, -2.3], [1.0, -1.7]),
        ]:
            axis_one = {'id': 'S2', 'kind': 'section',
                        'cut': {'axis': 1, 'value_m': -2.0},
                        'view_direction_frame': direction}
            mark = {'section_id': 'S2', 'axis': 1, 'value_m': -2.0,
                    'arrow_from': arrow_from, 'arrow_to': arrow_to}
            DRAW_ROOM.validate_section_marks({'views': [axis_one], 'section_marks': [mark]})
        with self.assertRaises(ValueError):
            DRAW_ROOM.validate_section_marks({'views': [section],
                                              'section_marks': [dict(valid, section_id='missing')]})
        with self.assertRaises(ValueError):
            DRAW_ROOM.validate_section_marks({'views': [section, dict(section, id='S1')],
                                              'section_marks': [valid]})

    def test_shape_only_presentation_hides_coordinates_and_legend(self):
        figure, axis = plt.subplots()
        try:
            axis.set_xlabel('u (model m)')
            axis.set_ylabel('v (model m)')
            axis.grid(True)
            DRAW_ROOM.apply_view_presentation(axis, {'show_coordinates': False, 'legend': {'mode': 'none'}})
            self.assertFalse(axis.axison)
            self.assertEqual(axis.get_xlabel(), '')
            self.assertEqual(axis.get_ylabel(), '')
            self.assertFalse(axis.xaxis.get_visible())
            self.assertFalse(axis.yaxis.get_visible())
            self.assertFalse(any(line.get_visible() for line in axis.get_xgridlines() + axis.get_ygridlines()))
            self.assertEqual(DRAW_ROOM.legend_text({'show_coordinates': False, 'legend': {'mode': 'none'}}), '')
        finally:
            plt.close(figure)

    def test_default_and_explicit_legend_modes_are_structured(self):
        self.assertIn('Blue-gray: architecture', DRAW_ROOM.legend_text({}))
        self.assertEqual(DRAW_ROOM.legend_text({'legend': {'mode': 'explicit', 'items': ['Mosaic', 'Light']}}), 'Mosaic   •   Light')
        with self.assertRaisesRegex(ValueError, 'legend mode'):
            DRAW_ROOM.legend_text({'id': 'bad', 'legend': 'none'})

    def run_single_view(self, view, native_data=None, return_manifest=False):
        native_data = native_data or {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'fixture-mesh',
                'vertices_world_m': [[0, 0, 0], [2, 0, 1], [2, 2, 1], [0, 2, 0]],
                'polygons': [[0, 1, 2, 3]],
                'loop_triangles': [
                    {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                    {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                ],
            }, {
                'name': 'retained-empty-mesh',
                'vertices_world_m': [],
                'polygons': [],
                'loop_triangles': [],
            }],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native_path = root / 'native.json'
            native_path.write_text(json.dumps(native_data, indent=2) + '\n')
            specification = {
                'model_sha256': native_data['model_sha256'],
                'native_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
                'room_id': 'fixture-room',
                'frame_axes_world': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'frame_source': 'fixture',
                'frame_source_sha256': 'fixture-sha',
                'styles': {'architecture': {'color': '#566573'}},
                'section_marks': [],
                'views': [view],
            }
            views_path = root / 'views.json'
            views_path.write_text(json.dumps(specification, indent=2) + '\n')
            result = subprocess.run([
                sys.executable, '-B', str(PRODUCER),
                '--native', str(native_path),
                '--views', str(views_path),
                '--math-helper', str(MATH_HELPER),
                '--title', 'Fixture Room',
                '--output-stem', 'fixture-room',
                '--output', str(root / 'output'),
            ], capture_output=True, text=True)
            if return_manifest and result.returncode == 0:
                return result, json.loads((root / 'output' / 'drawing-manifest.json').read_text())
            return result

    def test_declared_views_draw_selected_faces_and_write_review_outputs(self):
        native_data = {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'fixture-mesh',
                'vertices_world_m': [[0, 0, 0], [2, 0, 1], [2, 2, 1], [0, 2, 0]],
                'polygons': [[0, 1, 2, 3]],
                'loop_triangles': [
                    {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                    {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                ],
            }, {
                'name': 'retained-empty-mesh',
                'vertices_world_m': [],
                'polygons': [],
                'loop_triangles': [],
            }],
        }
        base_view = {
            'subjects': [{
                'object_id': 'fixture-mesh',
                'style': 'architecture',
                'face_indices': [0],
            }],
            'bounds_frame': [-1, 3, -1, 3],
            'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }
        views = [
            dict(base_view, id='P1', kind='plan', title='Plan', note='Plan fixture',
                 right_frame=[1, 0, 0], up_frame=[0, 1, 0],
                 view_direction_frame=[0, 0, -1],
                 cut={'axis': 2, 'value_m': 0.5, 'keep_below': True}),
            dict(base_view, id='R1', kind='reflected_ceiling', title='RCP', note='RCP fixture',
                 right_frame=[1, 0, 0], up_frame=[0, 1, 0],
                 view_direction_frame=[0, 0, 1], horizontal_reflection_of_upward_camera=True,
                 cut={'axis': 2, 'value_m': 0.5, 'keep_below': False}),
            dict(base_view, id='E1', kind='elevation', title='Elevation', note='Elevation fixture',
                 right_frame=[1, 0, 0], up_frame=[0, 0, 1],
                 view_direction_frame=[0, 1, 0]),
            dict(base_view, id='S1', kind='section', title='Section', note='Section fixture',
                 right_frame=[0, 1, 0], up_frame=[0, 0, 1],
                 view_direction_frame=[-1, 0, 0],
                 cut={'axis': 0, 'value_m': 1.0}),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native_path = root / 'native.json'
            native_path.write_text(json.dumps(native_data, indent=2) + '\n')
            specification = {
                'model_sha256': native_data['model_sha256'],
                'native_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
                'room_id': 'fixture-room',
                'frame_axes_world': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'frame_source': 'fixture',
                'frame_source_sha256': 'fixture-sha',
                'styles': {'architecture': {'color': '#566573'}},
                'section_marks': [],
                'views': views,
            }
            views_path = root / 'views.json'
            views_path.write_text(json.dumps(specification, indent=2) + '\n')
            output = root / 'output'

            result = subprocess.run([
                sys.executable, '-B', str(PRODUCER),
                '--native', str(native_path),
                '--views', str(views_path),
                '--math-helper', str(MATH_HELPER),
                '--title', 'Fixture Room',
                '--output-stem', 'fixture-room',
                '--output', str(output),
            ], capture_output=True, text=True, check=True)

            self.assertEqual(json.loads(result.stdout)['geometry_pages'], 4)
            manifest = json.loads((output / 'drawing-manifest.json').read_text())
            self.assertEqual(
                [record['view_id'] for record in manifest['rendered_selections']],
                ['P1', 'R1', 'E1', 'S1'],
            )
            for record in manifest['rendered_selections']:
                self.assertEqual(record['drawn_faces'], {'fixture-mesh': [0]})
            detail_images = sorted(output.glob('P*.png')) + sorted(output.glob('R*.png')) + sorted(output.glob('E*.png')) + sorted(output.glob('S*.png'))
            self.assertEqual(len(detail_images), 4)
            self.assertTrue((output / 'fixture-room-geometry.pdf').is_file())
            self.assertTrue((output / 'fixture-room-overview.png').is_file())
            self.assertTrue(all(path.stat().st_size > 0 for path in detail_images))

    def test_subject_spatial_clip_is_scoped_to_one_subject(self):
        native_data = {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [],
        }
        for name, offset in [('clipped-object', 0), ('unchanged-object', 3)]:
            native_data['objects'].append({
                'name': name,
                'vertices_world_m': [[offset, 0, 0], [offset + 2, 0, 0],
                                     [offset + 2, 2, 0], [offset, 2, 0]],
                'polygons': [[0, 1, 2, 3]],
                'loop_triangles': [
                    {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                    {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                ],
            })
        base_view = {
            'kind': 'plan', 'title': 'Subject clip fixture', 'note': 'fixture',
            'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0],
            'view_direction_frame': [0, 0, -1],
            'bounds_frame': [-1, 6, -1, 3],
            'axis_labels': ['horizontal', 'vertical'],
            'cut': {'axis': 2, 'value_m': 1, 'keep_below': True},
            'annotations': [],
        }
        views = [
            dict(base_view, id='B', subjects=[{
                'object_id': 'unchanged-object', 'style': 'architecture', 'face_indices': [0],
            }]),
            dict(base_view, id='A', subjects=[{
                'object_id': 'clipped-object', 'style': 'architecture', 'face_indices': [0],
                'spatial_clips': [{'axis': 0, 'value_m': 1, 'keep_below': True}],
            }]),
            dict(base_view, id='AB', subjects=[
                {
                    'object_id': 'clipped-object', 'style': 'architecture', 'face_indices': [0],
                    'spatial_clips': [{'axis': 0, 'value_m': 1, 'keep_below': True}],
                },
                {'object_id': 'unchanged-object', 'style': 'architecture', 'face_indices': [0]},
            ]),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native_path = root / 'native.json'
            native_path.write_text(json.dumps(native_data, indent=2) + '\n')
            specification = {
                'model_sha256': native_data['model_sha256'],
                'native_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
                'frame_axes_world': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'styles': {'architecture': {'color': '#566573'}},
                'section_marks': [], 'views': views,
            }
            views_path = root / 'views.json'
            views_path.write_text(json.dumps(specification, indent=2) + '\n')
            output = root / 'output'
            result = subprocess.run([
                sys.executable, '-B', str(PRODUCER),
                '--native', str(native_path), '--views', str(views_path),
                '--math-helper', str(MATH_HELPER), '--title', 'Fixture Room',
                '--output-stem', 'fixture-room', '--output', str(output),
            ], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['geometry_pages'], 3)
            manifest = json.loads((output / 'drawing-manifest.json').read_text())
            lengths = {record['view_id']: record['emitted_length_inside_bounds']
                       for record in manifest['rendered_selections']}
            self.assertAlmostEqual(lengths['B'], 8.0)
            self.assertAlmostEqual(lengths['A'], 6.0)
            self.assertAlmostEqual(lengths['AB'], 14.0)

    def test_view_and_subject_clips_continue_to_later_section_triangles(self):
        native_data = {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'section-quad',
                'vertices_world_m': [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]],
                'polygons': [[0, 1, 2, 3]],
                'loop_triangles': [
                    {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                    {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                ],
            }],
        }
        view = {
            'id': 'section-clips', 'kind': 'section', 'title': 'Section clips',
            'note': 'fixture', 'right_frame': [1, 0, 0], 'up_frame': [0, 0, 1],
            'view_direction_frame': [0, 1, 0], 'bounds_frame': [-1, 3, -1, 1],
            'axis_labels': ['X', 'Z'], 'cut': {'axis': 1, 'value_m': 1.8},
            'spatial_clips': [{'axis': 0, 'value_m': 0.5, 'keep_below': True}],
            'annotations': [], 'subjects': [{
                'object_id': 'section-quad', 'style': 'architecture', 'face_indices': [0],
                'spatial_clips': [{'axis': 1, 'value_m': 1.5, 'keep_below': False}],
            }],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native_path = root / 'native.json'
            native_path.write_text(json.dumps(native_data, indent=2) + '\n')
            specification = {
                'model_sha256': native_data['model_sha256'],
                'native_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
                'frame_axes_world': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'styles': {'architecture': {'color': '#566573'}},
                'section_marks': [], 'views': [view],
            }
            views_path = root / 'views.json'
            views_path.write_text(json.dumps(specification, indent=2) + '\n')
            output = root / 'output'
            subprocess.run([
                sys.executable, '-B', str(PRODUCER),
                '--native', str(native_path), '--views', str(views_path),
                '--math-helper', str(MATH_HELPER), '--title', 'Fixture Room',
                '--output-stem', 'fixture-room', '--output', str(output),
            ], capture_output=True, text=True, check=True)
            manifest = json.loads((output / 'drawing-manifest.json').read_text())
            record = manifest['rendered_selections'][0]
            self.assertEqual(record['drawn_faces'], {'section-quad': [0]})
            self.assertAlmostEqual(record['emitted_length_inside_bounds'], 0.5)

    def test_rejects_direction_mismatch(self):
        result = self.run_single_view({
            'id': 'bad-direction', 'kind': 'plan', 'title': 'Bad direction', 'note': 'fixture',
            'subjects': [{'object_id': 'fixture-mesh', 'style': 'architecture', 'face_indices': [0]}],
            'bounds_frame': [-1, 3, -1, 3], 'axis_labels': ['horizontal', 'vertical'], 'annotations': [],
            'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0], 'view_direction_frame': [0, 0, 1],
            'cut': {'axis': 2, 'value_m': 0.5, 'keep_below': True},
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('bad-direction right_frame must equal', result.stderr)

    def test_requires_declared_view_direction(self):
        result = self.run_single_view({
            'id': 'missing-direction', 'kind': 'plan', 'title': 'Missing direction', 'note': 'fixture',
            'subjects': [{'object_id': 'fixture-mesh', 'style': 'architecture', 'face_indices': [0]}],
            'bounds_frame': [-1, 3, -1, 3], 'axis_labels': ['horizontal', 'vertical'], 'annotations': [],
            'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0],
            'cut': {'axis': 2, 'value_m': 0.5, 'keep_below': True},
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing-direction must declare view_direction_frame', result.stderr)

    def test_rejects_view_with_no_geometry_inside_bounds(self):
        result = self.run_single_view({
            'id': 'offscreen', 'kind': 'reflected_ceiling', 'title': 'Offscreen RCP', 'note': 'fixture',
            'subjects': [{'object_id': 'fixture-mesh', 'style': 'architecture', 'face_indices': [0]}],
            'bounds_frame': [10, 11, 10, 11], 'axis_labels': ['horizontal', 'vertical'], 'annotations': [],
            'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0], 'view_direction_frame': [0, 0, 1],
            'horizontal_reflection_of_upward_camera': True,
            'cut': {'axis': 2, 'value_m': 0.5, 'keep_below': False},
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('offscreen emits no geometry inside', result.stderr)

    def test_manifest_counts_only_faces_with_emitted_length_inside_bounds(self):
        native_data = {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'mixed-coverage-mesh',
                'vertices_world_m': [
                    [-2, 0, 0], [2, 0, 0], [2, 0, 1], [-2, 0, 1],
                    [10, 0, 0], [11, 0, 0], [11, 0, 1], [10, 0, 1],
                ],
                'polygons': [[0, 1, 2, 3], [4, 5, 6, 7]],
                'loop_triangles': [],
            }, {
                'name': 'offscreen-mesh',
                'vertices_world_m': [[10, 0, 0], [11, 0, 0], [11, 0, 1], [10, 0, 1]],
                'polygons': [[0, 1, 2, 3]],
                'loop_triangles': [],
            }],
        }
        view = {
            'id': 'E1', 'kind': 'elevation', 'title': 'Coverage fixture', 'note': 'fixture',
            'right_frame': [1, 0, 0], 'up_frame': [0, 0, 1],
            'view_direction_frame': [0, 1, 0],
            'subjects': [
                {'object_id': 'mixed-coverage-mesh', 'style': 'architecture',
                 'face_indices': [0, 1]},
                {'object_id': 'offscreen-mesh', 'style': 'architecture',
                 'face_indices': [0]},
            ],
            'bounds_frame': [-1, 1, -1, 2], 'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }

        result, manifest = self.run_single_view(view, native_data, return_manifest=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest['rendered_selections'][0]['drawn_faces'], {
            'mixed-coverage-mesh': [0],
        })
        self.assertEqual(manifest['omitted_objects'], [{
            'view_id': 'E1', 'object_id': 'offscreen-mesh',
            'reason': 'selected_faces_have_no_segments_inside_declared_bounds',
            'face_indices': [0],
        }])
        self.assertAlmostEqual(manifest['rendered_selections'][0]['emitted_length_inside_bounds'], 4.0)

    def test_manifest_separates_exact_point_collapse_from_projection_omission(self):
        native_data = {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [
                {
                    'name': 'collapsed',
                    'vertices_world_m': [[1, 1, 1]] * 4,
                    'polygons': [[0, 1, 2, 3]],
                    'loop_triangles': [
                        {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                        {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                    ],
                },
                {
                    'name': 'edge-on-plane',
                    'vertices_world_m': [[0, -1, 0], [0, 1, 0], [1, 1, 0], [1, -1, 0]],
                    'polygons': [[0, 1, 2, 3]],
                    'loop_triangles': [
                        {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                        {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                    ],
                },
                {
                    'name': 'clipped-normal',
                    'vertices_world_m': [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
                    'polygons': [[0, 1, 2, 3]],
                    'loop_triangles': [
                        {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                        {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                    ],
                },
                {
                    'name': 'drawable',
                    'vertices_world_m': [[-2, 0, 0], [-1.5, 0, 0], [-1.5, 0, 1], [-2, 0, 1]],
                    'polygons': [[0, 1, 2, 3]],
                    'loop_triangles': [
                        {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                        {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                    ],
                },
            ],
        }
        view = {
            'id': 'E1', 'kind': 'elevation', 'title': 'Fixture', 'note': 'fixture',
            'right_frame': [1, 0, 0], 'up_frame': [0, 0, 1],
            'view_direction_frame': [0, 1, 0],
            'subjects': [
                {'object_id': 'collapsed', 'style': 'architecture', 'face_indices': [0]},
                {'object_id': 'edge-on-plane', 'style': 'architecture', 'face_indices': [0]},
            ],
            'bounds_frame': [-2, 2, -2, 2], 'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }
        clipped_view = dict(view, id='E2', title='Clipped fixture',
                            spatial_clips=[{'axis': 0, 'value_m': -1, 'keep_below': True}],
                            subjects=[
                                {'object_id': 'drawable', 'style': 'architecture', 'face_indices': [0]},
                                {'object_id': 'clipped-normal', 'style': 'architecture', 'face_indices': [0]},
                            ])
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native_path = root / 'native.json'
            native_path.write_text(json.dumps(native_data, indent=2) + '\n')
            specification = {
                'model_sha256': native_data['model_sha256'],
                'native_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
                'room_id': 'fixture-room',
                'frame_axes_world': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'frame_source': 'fixture', 'frame_source_sha256': 'fixture-sha',
                'styles': {'architecture': {'color': '#566573'}},
                'section_marks': [], 'views': [view, clipped_view],
            }
            views_path = root / 'views.json'
            views_path.write_text(json.dumps(specification, indent=2) + '\n')
            output = root / 'output'
            subprocess.run([
                sys.executable, '-B', str(PRODUCER), '--native', str(native_path),
                '--views', str(views_path), '--math-helper', str(MATH_HELPER),
                '--title', 'Fixture Room', '--output-stem', 'fixture-room',
                '--output', str(output),
            ], capture_output=True, text=True, check=True)
            manifest = json.loads((output / 'drawing-manifest.json').read_text())
            self.assertEqual(manifest['nondrawable_objects'], [{
                'view_id': 'E1', 'object_id': 'collapsed',
                'reason': 'selected_polygon_vertices_coincident',
                'vertex_indices': [0, 1, 2, 3], 'unique_point_count': 1,
            }])
            self.assertEqual(manifest['omitted_objects'], [{
                'view_id': 'E2', 'object_id': 'clipped-normal',
                'reason': 'selected_faces_emitted_no_segments_after_cuts_or_clips',
                'face_indices': [0],
            }])
            self.assertEqual(manifest['rendered_selections'][0]['drawn_faces'], {'edge-on-plane': [0]})
            self.assertEqual(manifest['rendered_selections'][1]['drawn_faces'], {'drawable': [0]})

    def test_rejects_nonfinite_selected_polygon_coordinates(self):
        native_data = {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'nonfinite',
                'vertices_world_m': [[float('nan'), 0, 0], [0, 0, 0], [0, 0, 1]],
                'polygons': [[0, 1, 2]],
                'loop_triangles': [{'polygon_index': 0, 'vertex_indices': [0, 1, 2]}],
            }],
        }
        view = {
            'id': 'E1', 'kind': 'elevation', 'title': 'Fixture', 'note': 'fixture',
            'right_frame': [1, 0, 0], 'up_frame': [0, 0, 1],
            'view_direction_frame': [0, 1, 0],
            'subjects': [{'object_id': 'nonfinite', 'style': 'architecture', 'face_indices': [0]}],
            'bounds_frame': [-2, 2, -2, 2], 'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native_path = root / 'native.json'
            native_path.write_text(json.dumps(native_data, indent=2, allow_nan=True) + '\n')
            specification = {
                'model_sha256': native_data['model_sha256'],
                'native_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
                'room_id': 'fixture-room',
                'frame_axes_world': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'styles': {'architecture': {'color': '#566573'}},
                'section_marks': [], 'views': [view],
            }
            views_path = root / 'views.json'
            views_path.write_text(json.dumps(specification, indent=2) + '\n')
            result = subprocess.run([
                sys.executable, '-B', str(PRODUCER), '--native', str(native_path),
                '--views', str(views_path), '--math-helper', str(MATH_HELPER),
                '--title', 'Fixture Room', '--output-stem', 'fixture-room',
                '--output', str(root / 'output'),
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('selected polygon vertices for nonfinite are non-finite', result.stderr)

    def test_coplanar_boundary_mode_renders_adjacent_faces_without_shared_edge(self):
        native_data = {
            'schema_version': 1, 'status': 'ok', 'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'fixture-mesh',
                'vertices_world_m': [[0, 0, 0], [1, 0, 0], [1, 1, 0],
                                     [0, 1, 0], [2, 0, 0], [2, 1, 0]],
                'polygons': [[0, 1, 2, 3], [1, 4, 5, 2]],
                'loop_triangles': [
                    {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                    {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                    {'polygon_index': 1, 'vertex_indices': [1, 4, 5]},
                    {'polygon_index': 1, 'vertex_indices': [1, 5, 2]},
                ],
            }],
        }
        view = {
            'id': 'E1', 'kind': 'elevation', 'title': 'Fixture', 'note': 'fixture',
            'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0],
            'view_direction_frame': [0, 0, -1],
            'subjects': [{'object_id': 'fixture-mesh', 'style': 'architecture',
                          'face_indices': [0, 1], 'edge_mode': 'coplanar_boundary'}],
            'bounds_frame': [-1, 3, -1, 2], 'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }

        result, manifest = self.run_single_view(view, native_data, return_manifest=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['geometry_pages'], 1)
        self.assertEqual(manifest['rendered_selections'][0]['drawn_faces'], {'fixture-mesh': [0, 1]})
        self.assertAlmostEqual(manifest['rendered_selections'][0]['emitted_length_inside_bounds'], 6.0)

    def test_coplanar_boundary_mode_passes_explicit_boundary_tolerance(self):
        native_data = {
            'schema_version': 1, 'status': 'ok', 'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'drifted-mesh',
                'vertices_world_m': [
                    [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                    [1 + 1.5e-6, 0, 0], [2, 0, 0], [2, 1, 0], [1 + 1.5e-6, 1, 0],
                ],
                'polygons': [[0, 1, 2, 3], [4, 5, 6, 7]],
                'loop_triangles': [],
            }],
        }
        base_view = {
            'kind': 'elevation', 'title': 'Fixture', 'note': 'fixture',
            'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0],
            'view_direction_frame': [0, 0, -1],
            'subjects': [{'object_id': 'drifted-mesh', 'style': 'architecture',
                          'face_indices': [0, 1], 'edge_mode': 'coplanar_boundary'}],
            'bounds_frame': [-1, 3, -1, 2], 'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }

        default_result, default_manifest = self.run_single_view(
            dict(base_view, id='default'), native_data, return_manifest=True)
        explicit_result, explicit_manifest = self.run_single_view(
            dict(base_view, id='explicit', subjects=[dict(base_view['subjects'][0],
                                                          boundary_tolerance_m=5e-6,
                                                          boundary_line_tolerance_m=2e-6)]),
            native_data, return_manifest=True)

        self.assertEqual(default_result.returncode, 0, default_result.stderr)
        self.assertEqual(explicit_result.returncode, 0, explicit_result.stderr)
        self.assertAlmostEqual(
            default_manifest['rendered_selections'][0]['emitted_length_inside_bounds'], 8.0,
            delta=1e-3)
        self.assertAlmostEqual(
            explicit_manifest['rendered_selections'][0]['emitted_length_inside_bounds'], 6.0,
            delta=1e-3)

    def test_coplanar_boundary_mode_rejects_invalid_boundary_tolerance(self):
        view = {
            'id': 'invalid-tolerance', 'kind': 'elevation', 'title': 'Fixture', 'note': 'fixture',
            'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0],
            'view_direction_frame': [0, 0, -1],
            'subjects': [{'object_id': 'fixture-mesh', 'style': 'architecture',
                          'face_indices': [0], 'edge_mode': 'coplanar_boundary',
                          'boundary_tolerance_m': 0}],
            'bounds_frame': [-1, 3, -1, 3], 'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }

        result = self.run_single_view(view)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('boundary tolerance must be finite and positive', result.stderr)
        line_view = dict(view, id='invalid-line-tolerance', subjects=[
            dict(view['subjects'][0], boundary_tolerance_m=1e-7,
                 boundary_line_tolerance_m=0)])
        line_result = self.run_single_view(line_view)
        self.assertNotEqual(line_result.returncode, 0)
        self.assertIn('boundary line tolerance must be finite and positive', line_result.stderr)

    def test_coplanar_boundary_coverage_excludes_fully_interior_tile(self):
        vertices = [[x, y, 0] for y in range(4) for x in range(4)]
        polygons = []
        for row in range(3):
            for column in range(3):
                lower_left = row * 4 + column
                polygons.append([
                    lower_left, lower_left + 1,
                    lower_left + 5, lower_left + 4,
                ])
        native_data = {
            'schema_version': 1, 'status': 'ok', 'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'tiled-mesh', 'vertices_world_m': vertices,
                'polygons': polygons, 'loop_triangles': [],
            }],
        }
        view = {
            'id': 'E1', 'kind': 'elevation', 'title': 'Tiled boundary fixture',
            'note': 'fixture', 'right_frame': [1, 0, 0], 'up_frame': [0, 1, 0],
            'view_direction_frame': [0, 0, -1],
            'subjects': [{'object_id': 'tiled-mesh', 'style': 'architecture',
                          'face_indices': list(range(9)), 'edge_mode': 'coplanar_boundary'}],
            'spatial_clips': [{'axis': 0, 'value_m': 2.5, 'keep_below': True}],
            'bounds_frame': [-0.5, 3.0, -0.5, 3.5],
            'axis_labels': ['horizontal', 'vertical'], 'annotations': [],
        }

        result, manifest = self.run_single_view(view, native_data, return_manifest=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest['rendered_selections'][0]['drawn_faces'], {
            'tiled-mesh': [0, 1, 2, 3, 5, 6, 7, 8],
        })
        self.assertAlmostEqual(manifest['rendered_selections'][0]['emitted_length_inside_bounds'], 11.0)


if __name__ == '__main__':
    unittest.main()
