from adkit import *
import bpy
import math

reset()
render_settings(res=1080, samples=64, aspect=1.0)
world("#15110e", strength=0.28)
backdrop("#12100e", roughness=0.8)

scene = bpy.context.scene
scene.view_settings.view_transform = "AgX"
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.use_file_extension = True
scene.render.engine = "CYCLES"
scene.cycles.use_denoising = True
scene.render.filter_size = 1.0

# Restrained charcoal, cream, and amber palette.
body_mat = material("Satin charcoal aluminum", color="#343936",
                    metallic=0.58, roughness=0.32, coat=0.22)
silver_mat = material("Brushed aluminum", color="#adb1a8",
                      metallic=0.85, roughness=0.27)
lid_mat = material("Recessed aluminum lid", color="#777e76",
                   metallic=0.8, roughness=0.34)
dark_mat = material("Tab opening", color="#131714",
                    metallic=0.2, roughness=0.45)

pedestal(radius=1.01, height=0.22, color="#29231d",
         location=(0, 0, 0))

# Explicit lathed geometry avoids unwanted handle-like components.
segments = 96
profile = [
    (0.505, 0.23), (0.548, 0.25), (0.573, 0.30),
    (0.596, 0.38), (0.600, 0.46),
    (0.600, 2.22), (0.591, 2.30),
    (0.555, 2.39), (0.535, 2.43)
]
vertices = []
for radius, z in profile:
    for i in range(segments):
        angle = 2 * math.pi * i / segments
        vertices.append((radius * math.cos(angle),
                         radius * math.sin(angle), z))
faces = []
for j in range(len(profile) - 1):
    for i in range(segments):
        k = (i + 1) % segments
        faces.append((j * segments + i, j * segments + k,
                      (j + 1) * segments + k, (j + 1) * segments + i))
faces.append(tuple(reversed(range(segments))))
faces.append(tuple((len(profile) - 1) * segments + i
                   for i in range(segments)))
mesh = bpy.data.meshes.new("Standard 12oz can profile")
mesh.from_pydata(vertices, [], faces)
mesh.update()
body = bpy.data.objects.new("Nova cold brew can", mesh)
bpy.context.collection.objects.link(body)
body.data.materials.append(body_mat)
for polygon in mesh.polygons:
    polygon.use_smooth = len(polygon.vertices) == 4

def cylinder(name, radius, depth, z, mat):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=96, radius=radius, depth=depth, location=(0, 0, z))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    bevel = obj.modifiers.new("Soft machined edges", "BEVEL")
    bevel.width = 0.008
    bevel.segments = 2
    obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj

cylinder("Clearly defined recessed lid", 0.528, 0.025, 2.437, lid_mat)
for z, radius, thickness in [(2.451, 0.533, 0.022),
                              (0.267, 0.543, 0.018)]:
    torus(major=radius, minor=thickness, location=(0, 0, z),
          rotation=(0, 0, 0), color="#b6b9ac", metallic=0.85)

# The pull tab lies flat on the lid, inside the can silhouette.
opening = sphere(radius=1, location=(0, 0.19, 2.455),
                 color="#111613", roughness=0.5)
opening.name = "Dark drinking aperture"
opening.scale = (0.15, 0.19, 0.008)

tab = torus(major=0.105, minor=0.029, location=(0, -0.055, 2.478),
            rotation=(0, 0, 0), color="#c3c5b8", metallic=0.85)
tab.name = "Flat aluminum pull tab"
tab.scale = (0.82, 1.47, 0.31)
rivet = sphere(radius=0.037, location=(0, 0.058, 2.471),
               color="#bfc2b5", roughness=0.28, metallic=0.8)
rivet.scale.z = 0.28

# Small horizontal accents stay on the body, never above the lid.
for z in (0.43, 2.235):
    torus(major=0.601, minor=0.009, location=(0, 0, z),
          rotation=(0, 0, 0), color="#bc884b", metallic=0.65)

# Confident, uncluttered label: no unreadable microcopy.
def label(body, z, size, color, width, font="poppins"):
    obj = text(body, location=(0, -0.616, z), size=size,
               color=color, font=font, extrude=0.0015)
    bpy.context.view_layer.update()
    if obj.dimensions.x > width:
        factor = width / obj.dimensions.x
        obj.scale *= factor
    return obj

label("NOVA", 1.70, 0.47, "#fff0d1", 1.04, "anton")
label("COLD BREW", 1.37, 0.205, "#fff0d1", 1.04)
label("NITRO", 1.01, 0.24, "#efb666", 0.86)
label("12oz", 0.64, 0.19, "#eee1c6", 0.65)

# Large campaign lockup above the product.
text("NOVA", location=(0, 0, 3.40), size=0.71,
     color="#f3e3c5", font="anton", extrude=0.008)
text("COLD BREW", location=(0, -0.01, 3.10), size=0.25,
     color="#dcb37d", font="poppins", extrude=0.002)

# Price is deliberately large, with no tiny supporting caption.
text("$12", location=(-1.48, -0.10, 0.70), size=0.57,
     color="#f4e3c5", font="anton", extrude=0.006)

bean_mat = material("Roasted coffee", color="#49291a",
                    metallic=0.05, roughness=0.4, coat=0.15)
crease_mat = material("Natural bean crease", color="#180c07",
                      metallic=0.0, roughness=0.8)

def coffee_bean(location, scale, rotation):
    root = bpy.data.objects.new("Floating coffee bean", None)
    bpy.context.collection.objects.link(root)
    root.location = location
    root.rotation_euler = tuple(math.radians(a) for a in rotation)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12)
    bean = bpy.context.object
    bean.parent = root
    bean.location = (0, 0, 0)
    bean.scale = (scale * 0.64, scale * 0.40, scale)
    bean.data.materials.append(bean_mat)
    for polygon in bean.data.polygons:
        polygon.use_smooth = True

    curve = bpy.data.curves.new("Bean seam", "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = scale * 0.055
    curve.bevel_resolution = 2
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(4)
    for i, point in enumerate(spline.bezier_points):
        t = -0.78 + i * 0.39
        point.co = (
            math.sin(t * 3) * scale * 0.10,
            -scale * 0.40 * math.sqrt(max(0.05, 1 - t * t)),
            t * scale)
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"
    seam = bpy.data.objects.new("Coffee bean groove", curve)
    bpy.context.collection.objects.link(seam)
    seam.parent = root
    curve.materials.append(crease_mat)

# Beans flank the hero without crossing its label or the QR reserve.
coffee_bean((-1.26, 0.12, 2.62), 0.22, (12, -32, -20))
coffee_bean((-1.55, 0.20, 1.84), 0.16, (-15, 35, 28))
coffee_bean((1.26, 0.20, 2.70), 0.21, (18, 42, -32))
coffee_bean((1.51, 0.34, 1.95), 0.16, (-12, -30, 20))

# Broad frontal illumination reveals the satin body and cream print.
area_light(location=(-0.7, -5.0, 4.0), target=(0, 0, 1.45),
           energy=650, color="#fff1da", size=4.0)
area_light(location=(-3.6, -2.4, 3.7), target=(0, 0, 1.5),
           energy=240, color="#e9e5db", size=2.6)
area_light(location=(2.6, 1.1, 3.5), target=(0, 0, 1.5),
           energy=700, color="#ff9e43", size=2.0)
area_light(location=(0.4, 0.1, 5.5), target=(0, 0, 1.4),
           energy=300, color="#f2e4c9", size=2.4)

camera(location=(0, -8.8, 3.65), target=(0, 0, 1.88), lens=58)

render_still()