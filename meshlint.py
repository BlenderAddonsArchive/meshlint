import bpy
import bmesh

SUBPANEL_LABEL = 'Mesh Lint'

LINTS = {
  'nonmanifold': {
    'label': 'Nonmanifold Elements',
    'default': True
  },
  'tris': {
    'label': 'Tris',
    'default': True
  },
  'ngons': {
    'label': 'Ngons',
    'default': True
  },
  'interior_faces': {
    'label': 'Interior Faces',
    'default': True
  },
  'sixplus_poles': {
    'label': '6+-edge Poles',
    'default': False
  },
  # 'unnamed_object'
  # [Your great new idea here] -> Tell me about it: rking@panoptic.com
}

LINTS_LIST = ' / '.join(lint['label'] for lint in LINTS.values())

for sym in LINTS:
    lint = LINTS[sym]
    lint['count'] = '...'
    prop = 'meshlint_check_' + sym
    lint['check_prop'] = prop
    'meshlint_check_' + sym
    setattr(
        bpy.types.Scene,
        prop,
        bpy.props.BoolProperty(default=lint['default'])
    )

bl_info = {
    'name': 'Mesh Lint: Scrutinize Mesh Quality',
    'author': 'rking',
    'version': (1, 0),
    'blender': (2, 6, 3),
    'location': 'Object Data properties > ' + SUBPANEL_LABEL,
    'description': 'Check a mesh for: ' + LINTS_LIST,
    'warning': '',
    'wiki_url': '', # TODO
    'tracker_url': '', # TODO
    'category': 'Mesh' }


def should_show(context):
    obj = context.active_object 
    return obj and 'MESH' == obj.type


class MeshLintSelector(bpy.types.Operator):
    "Uncheck boxes below to prevent those checks from running."
    bl_idname = 'meshlint.select'
    bl_label = "Mesh Lint"

    @classmethod
    def poll(cls, context):
        return should_show(context)

    def execute(self, context):
        obj = context.active_object
        self.ensure_edit_mode()
        self.select_none()
        b = bmesh.from_edit_mesh(obj.data)
        self.enable_anything_select_mode(b)
        for sym in LINTS:
            lint = LINTS[sym]
            lint['count'] = 0
            should_check = getattr(context.scene, lint['check_prop'])
            if should_check:
                method_name = 'check_' + sym
                getattr(type(self), method_name)(self, b)
            else:
                lint['count'] = '(N/A)'

        context.area.tag_redraw()
        return {'FINISHED'}

    def ensure_edit_mode(self):
        if 'EDIT_MESH' != bpy.context.mode:
            bpy.ops.object.editmode_toggle()

    def enable_anything_select_mode(self, b):
        b.select_mode = {'VERT', 'EDGE', 'FACE'}

    def select_none(self):
        bpy.ops.mesh.select_all(action='DESELECT')

    def check_nonmanifold(self, b):
        for elemtype in 'verts', 'edges':
            for elem in getattr(b, elemtype):
                if not elem.is_manifold:
                    elem.select = True
                    LINTS['nonmanifold']['count'] += 1
        print("MeshLint TODO: Deselect mirror-plane verts.")

    def check_tris(self, b):
        for f in b.faces:
            if 3 == len(f.verts):
                f.select = True
                LINTS['tris']['count'] += 1

    def check_ngons(self, b):
        for f in b.faces:
            if 4 < len(f.verts):
                f.select = True
                LINTS['ngons']['count'] += 1

    def check_interior_faces(self, b):
        bpy.ops.mesh.select_interior_faces()
        # ...that one was easy.

    def check_sixplus_poles(self, b):
        for v in b.verts:
            if 5 < len(v.link_edges):
                v.select = True
                LINTS['sixplus_poles']['count'] += 1
                

class MeshLintControl(bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_label = SUBPANEL_LABEL

    def draw(self, context):
        active = context.active_object
        layout = self.layout
        col = layout.column()
        col.operator(
            'meshlint.select', text='Select Lint', icon='RNA'
        )
        if not should_show(context):
            return
        for sym in LINTS:
            f = LINTS[sym]
            col.prop(context.scene, f['check_prop'], text=self.make_label(f))

    def make_label(self, feature):
        count = feature['count']
        label = str(count) + ' ' + feature['label']
        if 1 == count:
            label = label.rstrip('s')
        elif 0 == count:
            label += '!'
        return label
            

def register():
    bpy.utils.register_module(__name__)


def unregister():
    bpy.utils.unregister_module(__name__)


if __name__ == '__main__':
    register()

# vim:ts=4 sw=4 sts=4
