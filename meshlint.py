bl_info = {
    'name': 'MeshLint: Scrutinize Mesh Quality',
    'author': 'rking',
    'version': (0, 2),
    'blender': (2, 6, 3),
    'location': 'Object Data properties > MeshLint',
    'description': 'Check a mesh for: Tris / Ngons / Nonmanifoldness / etc',
    'warning': '',
    'wiki_url': '',
    'tracker_url': '',
    'category': 'Mesh' }

import bpy
import bmesh
import re

SUBPANEL_LABEL = 'MeshLint'

CHECKS = [
  {
    'symbol': 'tris',
    'label': 'Tris',
    'default': True
  },
  {
    'symbol': 'ngons',
    'label': 'Ngons',
    'default': True
  },
  {
    'symbol': 'interior_faces',
    'label': 'Interior Faces',
    'default': True
  },
  {
    'symbol': 'nonmanifold',
    'label': 'Nonmanifold Elements',
    'default': True
  },
  {
    'symbol': 'sixplus_poles',
    'label': '6+-edge Poles',
    'default': False
  },

  # Plus 'Default Name'

  # [Your great new idea here] -> Tell me about it: rking@panoptic.com
]

N_A_STR = '(N/A - disabled)'
TBD_STR = '...'

for lint in CHECKS:
    sym = lint['symbol']
    lint['count'] = TBD_STR
    prop = 'meshlint_check_' + sym
    lint['check_prop'] = prop
    'meshlint_check_' + sym
    setattr(
        bpy.types.Scene,
        prop,
        bpy.props.BoolProperty(default=lint['default']))

class MeshLintAnalyzer:
    def __init__(self):
        self.obj = bpy.context.active_object
        self.ensure_edit_mode()
        self.b = bmesh.from_edit_mesh(self.obj.data)

    def find_problems(self):
        analysis = [] 
        for lint in CHECKS:
            sym = lint['symbol']
            should_check = getattr(bpy.context.scene, lint['check_prop'])
            if not should_check:
                lint['count'] = N_A_STR
                continue
            lint['count'] = 0
            check_method_name = 'check_' + sym
            check_method = getattr(type(self), check_method_name)
            bad = check_method(self)
            report = { 'lint': lint }
            for elemtype in 'verts', 'edges', 'faces': # XXX redundant
                indices = bad.get(elemtype, [])
                report[elemtype] = indices
                lint['count'] += len(indices)
            analysis.append(report)
        return analysis

    @classmethod
    def none_analysis(cls):
        analysis = []
        for lint in CHECKS:
            analysis.append({
                'lint': lint,
                'verts': [],
                'edges': [],
                'faces': []})
        return analysis

    def ensure_edit_mode(self):
        if 'EDIT_MESH' != bpy.context.mode:
            bpy.ops.object.editmode_toggle()

    def check_nonmanifold(self):
        bad = {}
        for elemtype in 'verts', 'edges':
            bad[elemtype] = []
            for elem in getattr(self.b, elemtype):
                if not elem.is_manifold:
                    bad[elemtype].append(elem.index)
        # TODO: Exempt mirror-plane verts.
        # Plus: ...anybody wanna tackle Mirrors with an Object Offset?
        return bad

    def check_tris(self):
        bad = { 'faces': [] }
        for f in self.b.faces:
            if 3 == len(f.verts):
                bad['faces'].append(f.index)
        return bad

    def check_ngons(self):
        bad = { 'faces': [] }
        for f in self.b.faces:
            if 4 < len(f.verts):
                bad['faces'].append(f.index)
        return bad

    def check_interior_faces(self): # translated from editmesh_select.c
        bad = { 'faces': [] }
        for f in self.b.faces:
            if not any(3 > len(e.link_faces) for e in f.edges):
                bad['faces'].append(f.index)
        return bad

    def check_sixplus_poles(self):
        bad = { 'verts': [] }
        for v in self.b.verts:
            if 5 < len(v.link_edges):
                bad['verts'].append(v.index)
        return bad

    def enable_anything_select_mode(self):
        self.b.select_mode = {'VERT', 'EDGE', 'FACE'}

    def select_indices(self, elemtype, indices):
        bmseq = getattr(self.b, elemtype)
        for i in indices:
            # TODO: maybe filter out hidden elements?
            bmseq[i].select = True

    def topology_counts(self):
        # XXX - Is this protected so it only runs with meshes? I don't know
        data = self.obj.data
        return {
            'data': self.obj.data,
            'faces': len(self.b.faces),
            'edges': len(self.b.edges),
            'verts': len(self.b.verts) }


def has_active_mesh(context):
    obj = context.active_object 
    return obj and 'MESH' == obj.type


# XXX Reconsider these global vars & funcs as a class or so.
previous_topology_counts = None
previous_analysis = None
@bpy.app.handlers.persistent
def repeated_check(dummy):
    global previous_topology_counts
    global previous_analysis
    if 'EDIT_MESH' != bpy.context.mode:
        return
    analyzer = MeshLintAnalyzer()
    now_counts = analyzer.topology_counts()
    if not None is previous_topology_counts:
        previous_data_name = previous_topology_counts['data'].name
    else:
        previous_data_name = None
    now_name = now_counts['data'].name
    if None is previous_topology_counts \
            or now_counts != previous_topology_counts:
        if not previous_data_name == now_name:
            before = MeshLintAnalyzer.none_analysis()
        analysis = analyzer.find_problems()
        diff_msg = diff_analyses(previous_analysis, analysis)
        if not None is diff_analyses:
            print(diff_msg) # TODO - make a happy message thing.
        previous_topology_counts = now_counts
        previous_analysis = analysis


def diff_analyses(before, analysis):
    if None is before:
        before = MeshLintAnalyzer.none_analysis()
    report_strings = []
    for i in range(len(analysis)):
        report_before = before[i]
        report = analysis[i]
        check_elem_strings = []
        for elemtype in 'verts', 'edges', 'faces': # XXX redundant
            elem_list_before = report_before[elemtype]
            elem_list = report[elemtype]
            if len(elem_list) > len(elem_list_before):
                count_diff = len(elem_list) - len(elem_list_before)
                elem_string = depluralize(count=count_diff, string=elemtype)
                check_elem_strings.append(str(count_diff) + ' ' + elem_string)
        if len(check_elem_strings):
            report_strings.append(
                report['lint']['label'] + ': ' + ', '.join(check_elem_strings))
    if len(report_strings):
        return 'MeshLint found ' + ', '.join(report_strings)
    return None

is_live_global = False

class MeshLintVitalizer(bpy.types.Operator):
    'Toggles the real-time execution of the checks'
    bl_idname = 'meshlint.live_toggle'
    bl_label = 'MeshLint Live Toggle'

    @classmethod
    def poll(cls, context):
        return has_active_mesh(context) and 'EDIT_MESH' == bpy.context.mode

    def execute(self, context):
        global is_live_global
        if is_live_global:
            bpy.app.handlers.scene_update_post.remove(repeated_check)
            is_live_global = False
        else:
            bpy.app.handlers.scene_update_post.append(repeated_check)
            is_live_global = True
        return {'FINISHED'}

class MeshLintSelector(bpy.types.Operator):
    'Uncheck boxes below to prevent those checks from running'
    bl_idname = 'meshlint.select'
    bl_label = 'MeshLint Select'

    @classmethod
    def poll(cls, context):
        return has_active_mesh(context)

    def execute(self, context):
        analyzer = MeshLintAnalyzer()
        analyzer.enable_anything_select_mode()
        self.select_none()
        analysis = analyzer.find_problems()
        for lint in analysis:
            for elemtype in 'verts', 'edges', 'faces': # XXX redundant
                indices = lint[elemtype]
                analyzer.select_indices(elemtype, indices)
        # XXX Note. This doesn't quite get it done. I don't know if it's a
        # problem in my script or in the redraw, but sometimes you have to
        # move the 3D View to get the selection to show. =( I need to first
        # figure out the exact circumstances that cause it, then go about
        # debugging.
        context.area.tag_redraw()
        global previous_analysis
        previous_analysis = analysis # used in repeated_check()
        return {'FINISHED'}

    def select_none(self):
        bpy.ops.mesh.select_all(action='DESELECT')
                

class MeshLintControl(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_label = SUBPANEL_LABEL

    def draw(self, context):
        layout = self.layout
        self.add_main_buttons(layout)
        if 'EDIT_MESH' == bpy.context.mode:
            self.add_rows(layout, context)

    def add_main_buttons(self, layout):
        split = layout.split()
        left = split.column()
        left.operator(
            'meshlint.select', text='Select Lint', icon='EDITMODE_HLT')

        right = split.column()
        global is_live_global
        if is_live_global:
            live_label = 'pause checking...'
            play_pause = 'PAUSE'
        else:
            live_label = 'Continuous Check!'
            play_pause = 'PLAY'
        right.operator('meshlint.live_toggle', text=live_label, icon=play_pause)

    def add_rows(self, layout, context):
        col = layout.column()
        active = context.active_object
        if not has_active_mesh(context):
            return
        for lint in CHECKS:
            # TODO - switch back to the big buttons. The checkboxes are lame.
            count = lint['count']
            if count in (TBD_STR, N_A_STR):
                label = str(count) + ' ' + lint['label']
                reward = 'SOLO_OFF'
            elif 0 == count:
                label = 'No %s!' % lint['label']
                reward = 'SOLO_ON'
            else:
                label = str(count) + 'x ' + lint['label']
                label = depluralize(count=count, string=label)
                reward = 'ERROR'
            row = col.row()
            row.prop(context.scene, lint['check_prop'], text='')
            row.label(label, icon=reward)
        if self.has_bad_name(active.name):
            col.row().label(
                '...and "%s" is not a great name, BTW.' % active.name)

    def has_bad_name(self, name):
        default_names = [
            'BezierCircle',
            'BezierCurve',
            'Circle',
            'Cone',
            'Cube',
            'CurvePath',
            'Cylinder',
            'Grid',
            'Icosphere',
            'Mball',
            'Monkey',
            'NurbsCircle',
            'NurbsCurve',
            'NurbsPath',
            'Plane',
            'Sphere',
            'Surface',
            'SurfCircle',
            'SurfCurve',
            'SurfCylinder',
            'SurfPatch',
            'SurfSphere',
            'SurfTorus',
            'Text',
        ]
        pat = '(%s)\.?\d*$' % '|'.join(default_names)
        return re.match(pat, name)


def depluralize(**args):
    if 1 == args['count']:
        return args['string'].rstrip('s')
    else:
        return args['string']
           

def register():
    bpy.utils.register_module(__name__)


def unregister():
    bpy.utils.unregister_module(__name__)


import unittest
import warnings
import time

class TestUtilities(unittest.TestCase):
    def test_depluralize(self):
        self.assertEqual(
            'foo',
            depluralize(count=1, string='foos'))
        self.assertEqual(
            'foos',
            depluralize(count=2, string='foos'))


class TestAnalysis(unittest.TestCase):
    def test_comparison(self):
        a = MeshLintAnalyzer.none_analysis()
        b = MeshLintAnalyzer.none_analysis()
        self.assertEqual(
            None,
            diff_analyses(
                MeshLintAnalyzer.none_analysis(),
                MeshLintAnalyzer.none_analysis()),
            'Two none_analysis()s')
        self.assertEqual(
            "MeshLint found SomeCheck: 4 verts",
            diff_analyses(
                None,
                [
                    {
                        'lint': { 'label': 'SomeCheck' },
                        'verts': [1,2,3,4],
                        'edges': [],
                        'faces': [],
                    },
                ]),
            'When there was no previous analysis')
        self.assertEqual(
            "MeshLint found CheckA: 2 edges, CheckC: 4 verts, 1 face",
            diff_analyses(
                [
                    { 'lint': { 'label': 'CheckA' },
                      'verts': [], 'edges': [1,4], 'faces': [], },
                    { 'lint': { 'label': 'CheckB' },
                      'verts': [], 'edges': [2,3], 'faces': [], },
                    { 'lint': { 'label': 'CheckC' },
                      'verts': [], 'edges': [], 'faces': [2,3], },
                ],
                [
                    { 'lint': { 'label': 'CheckA' },
                      'verts': [], 'edges': [1,4,5,6], 'faces': [], },
                    { 'lint': { 'label': 'CheckB' },
                      'verts': [], 'edges': [2,3], 'faces': [], },
                    { 'lint': { 'label': 'CheckC' },
                      'verts': [1,2,3,4], 'edges': [], 'faces': [2,3,5], },
                ]),
            'Complex comparison of analyses')

class QuietOnSuccessTestresult(unittest.TextTestResult):
    def startTest(self, test):
        pass

    def addSuccess(self, test):
        pass


class QuietTestRunner(unittest.TextTestRunner):
    resultclass = QuietOnSuccessTestresult

    def run(self, test):
        # Ugh. I really shouldn't have to include this much code, but they
        # left it so unrefactored I don't know what else to do. - rking
        "Run the given test case or test suite."
        result = self._makeResult()
        unittest.registerResult(result)
        result.failfast = self.failfast
        result.buffer = self.buffer
        with warnings.catch_warnings():
            if self.warnings:
                # if self.warnings is set, use it to filter all the warnings
                warnings.simplefilter(self.warnings)
                # if the filter is 'default' or 'always', special-case the
                # warnings from the deprecated unittest methods to show them
                # no more than once per module, because they can be fairly
                # noisy.  The -Wd and -Wa flags can be used to bypass this
                # only when self.warnings is None.
                if self.warnings in ['default', 'always']:
                    warnings.filterwarnings('module',
                            category=DeprecationWarning,
                            message='Please use assert\w+ instead.')
            startTime = time.time()
            startTestRun = getattr(result, 'startTestRun', None)
            if startTestRun is not None:
                startTestRun()
            try:
                test(result)
            finally:
                stopTestRun = getattr(result, 'stopTestRun', None)
                if stopTestRun is not None:
                    stopTestRun()
            stopTime = time.time()
        timeTaken = stopTime - startTime
        result.printErrors()
        run = result.testsRun

        expectedFails = unexpectedSuccesses = skipped = 0
        try:
            results = map(len, (result.expectedFailures,
                                result.unexpectedSuccesses,
                                result.skipped))
        except AttributeError:
            pass
        else:
            expectedFails, unexpectedSuccesses, skipped = results

        infos = []
        if not result.wasSuccessful():
            self.stream.write("FAILED")
            failed, errored = len(result.failures), len(result.errors)
            if failed:
                infos.append("failures=%d" % failed)
            if errored:
                infos.append("errors=%d" % errored)
        if skipped:
            infos.append("skipped=%d" % skipped)
        if expectedFails:
            infos.append("expected failures=%d" % expectedFails)
        if unexpectedSuccesses:
            infos.append("unexpected successes=%d" % unexpectedSuccesses)
        return result

if __name__ == '__main__':
    unittest.main(testRunner=QuietTestRunner, argv=['dummy'], exit=False)
    register()

# vim:ts=4 sw=4 sts=4
