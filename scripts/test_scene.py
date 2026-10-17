import bpy, math
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def mat(name, color, metal=0.0, rough=0.4, emit=None):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 4
    return m

# floor
bpy.ops.mesh.primitive_plane_add(size=40)
bpy.context.object.data.materials.append(mat("floor", (0.02, 0.02, 0.03), rough=0.15))
# can
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=0.6, depth=2.2, location=(0, 0, 1.1))
can = bpy.context.object
bpy.ops.object.shade_smooth()
can.data.materials.append(mat("can", (0.55, 0.25, 0.08), metal=0.9, rough=0.25))
# title
bpy.ops.object.text_add(location=(0, -1.2, 2.6), rotation=(math.radians(90), 0, 0))
t = bpy.context.object; t.data.body = "COLD BREW"; t.data.align_x = "CENTER"; t.data.size = 0.55; t.data.extrude = 0.06
t.data.materials.append(mat("txt", (1, 1, 1), emit=(1.0, 0.75, 0.4)))
bpy.ops.object.text_add(location=(0, -1.2, 0.25), rotation=(math.radians(90), 0, 0))
p = bpy.context.object; p.data.body = "$12"; p.data.align_x = "CENTER"; p.data.size = 0.4; p.data.extrude = 0.04
p.data.materials.append(mat("price", (1, 1, 1), emit=(0.3, 0.9, 1.0)))
# lights
for loc, e, c in [((-3, -2, 4), 600, (1, 0.6, 0.3)), ((3, 1, 3), 400, (0.3, 0.6, 1)), ((0, 3, 5), 300, (1, 1, 1))]:
    bpy.ops.object.light_add(type="AREA", location=loc)
    L = bpy.context.object; L.data.energy = e; L.data.color = c; L.data.size = 2
    L.rotation_euler = (loc[0] * 0 + math.atan2(math.hypot(loc[0], loc[1]), loc[2]), 0, math.atan2(loc[1], loc[0]) + math.pi / 2)
# camera
bpy.ops.object.camera_add(location=(0, -7, 2.2), rotation=(math.radians(85), 0, 0))
sc.camera = bpy.context.object
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (0.01, 0.01, 0.015, 1)
# render
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = 32; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = 1080
sc.render.filepath = "/tmp/out/ad.png"
bpy.ops.render.render(write_still=True)
