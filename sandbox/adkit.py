"""adkit: small helper library for building 3D product ads in headless Blender.

Uploaded into the sandbox at /opt/adkit/adkit.py. Scripts written by the agent
import it with `from adkit import *`.
"""
import bpy
import math
import os
from mathutils import Vector

FONT_DIR = "/opt/fonts"
FONTS = {
    "anton": "Anton-Regular.ttf",
    "poppins": "Poppins-Bold.ttf",
    "poppins-regular": "Poppins-Regular.ttf",
    "bebas": "BebasNeue-Regular.ttf",
}


def hex_rgb(h):
    """'#ff8800' -> (r, g, b) in linear space."""
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb)


def _rgb(c):
    return hex_rgb(c) if isinstance(c, str) else tuple(c[:3])


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    return scene


def render_settings(res=1080, samples=32, aspect=1.0, fps=24, frames=1):
    # The runner overrides quality for fast draft passes.
    res = int(os.environ.get("AD_RES", res))
    samples = int(os.environ.get("AD_SAMPLES", samples))
    frames = int(os.environ.get("AD_FRAMES_N", frames))
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 6
    s.render.resolution_x = int(res * aspect) if aspect >= 1 else res
    s.render.resolution_y = res if aspect >= 1 else int(res / aspect)
    s.render.resolution_percentage = 100
    s.render.fps = fps
    s.frame_start = 1
    s.frame_end = frames
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Punchy"


def world(color="#0a0a10", strength=1.0):
    bg = bpy.context.scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (*_rgb(color), 1)
    bg.inputs[1].default_value = strength


def material(name, color="#ffffff", metallic=0.0, roughness=0.4, emission=None,
             emission_strength=3.0, transmission=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*_rgb(color), 1)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = roughness
    b.inputs["Transmission Weight"].default_value = transmission
    b.inputs["Coat Weight"].default_value = coat
    if emission:
        b.inputs["Emission Color"].default_value = (*_rgb(emission), 1)
        b.inputs["Emission Strength"].default_value = emission_strength
    return m


def image_material(name, path, roughness=0.35, metallic=0.0, base_color=None):
    """Material that wraps an image (label, logo, product photo) via UVs."""
    m = material(name, base_color or "#ffffff", metallic, roughness)
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    tex.extension = "CLIP" if base_color else "REPEAT"
    b = nt.nodes["Principled BSDF"]
    if base_color:
        # Blend image over base color using its alpha, so a logo sits on a colored surface.
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.inputs[6].default_value = (*_rgb(base_color), 1)
        nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
        nt.links.new(tex.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    else:
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


def _assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return obj


def _active():
    return bpy.context.view_layer.objects.active


def look_at(obj, target=(0, 0, 0)):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def floor(color="#111116", roughness=0.2, size=60):
    bpy.ops.mesh.primitive_plane_add(size=size)
    return _assign(_active(), material("floor", color, roughness=roughness))


def backdrop(color="#111116", roughness=0.5, radius=6, size=40):
    """Seamless curved studio backdrop (cyclorama)."""
    bpy.ops.mesh.primitive_plane_add(size=size)
    o = _active()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    for v in o.data.vertices:
        v.select = v.co.y > 0
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, size / 2)})
    bpy.ops.object.mode_set(mode="OBJECT")
    bev = o.modifiers.new("bevel", "BEVEL")
    bev.width = radius
    bev.segments = 24
    bev.limit_method = "ANGLE"
    o.location.y = 4
    bpy.ops.object.shade_smooth()
    return _assign(o, material("backdrop", color, roughness=roughness))


def can(label=None, color="#c0c0c0", radius=0.6, height=2.2, location=(0, 0, 0), metallic=0.85):
    """Beverage can. `label` = image path wrapped around the body."""
    x, y, z = location
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=height, location=(x, y, z + height / 2))
    body = _active()
    bev = body.modifiers.new("bevel", "BEVEL")
    bev.width = radius * 0.12
    bev.segments = 6
    bpy.ops.object.shade_smooth()
    mat = image_material("label", label, 0.3, 0.4) if label else material("can", color, metallic, 0.25)
    _assign(body, mat)
    return body


def bottle(label=None, color="#2a6b3a", height=2.6, radius=0.5, location=(0, 0, 0), glass=True):
    """Bottle from a revolved profile; optional label band."""
    x, y, z = location
    pts = [(0, 0), (radius, 0), (radius, height * 0.6), (radius * 0.45, height * 0.82),
           (radius * 0.3, height * 0.9), (radius * 0.3, height), (0, height)]
    curve = bpy.data.curves.new("profile", "CURVE")
    curve.dimensions = "2D"
    sp = curve.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, (px, pz) in zip(sp.points, pts):
        p.co = (px, pz, 0, 1)
    o = bpy.data.objects.new("bottle", curve)
    bpy.context.collection.objects.link(o)
    o.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    scr = o.modifiers.new("screw", "SCREW")
    scr.steps = 64
    scr.render_steps = 64
    scr.axis = "Y"
    bpy.ops.object.modifier_apply(modifier="screw")
    o.rotation_euler = (0, 0, 0)
    bpy.ops.object.transform_apply(rotation=True)
    o.location = (x, y, z)
    bpy.ops.object.shade_smooth()
    if glass:
        _assign(o, material("glass", color, 0, 0.05, transmission=1.0))
    else:
        _assign(o, material("bottle", color, 0.1, 0.3, coat=1.0))
    if label:
        bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius * 1.01, depth=height * 0.3,
                                            location=(x, y, z + height * 0.32), end_fill_type="NOTHING")
        band = _active()
        bpy.ops.object.shade_smooth()
        _assign(band, image_material("label", label))
    return o


def box(label=None, color="#ffffff", size=(1.4, 0.5, 2.0), location=(0, 0, 0), bevel=0.03):
    """Product box / package. `label` image is mapped on every face."""
    x, y, z = location
    bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, z + size[2] / 2))
    o = _active()
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    if bevel:
        b = o.modifiers.new("bevel", "BEVEL")
        b.width = bevel
        b.segments = 4
    bpy.ops.object.shade_smooth()
    o.data.shade_smooth() if hasattr(o.data, "shade_smooth") else None
    _assign(o, image_material("box", label, base_color=color) if label else material("box", color, 0, 0.35))
    return o


def card(image, width=2.0, location=(0, 0, 1.2), thickness=0.03, rotation=(90, 0, 0)):
    """Flat card showing an image at its own aspect ratio (product photo, logo, poster)."""
    img = bpy.data.images.load(image)
    w, h = img.size
    height = width * h / max(w, 1)
    bpy.ops.mesh.primitive_plane_add(size=1, location=location,
                                     rotation=tuple(math.radians(r) for r in rotation))
    o = _active()
    o.scale = (width, height, 1)
    bpy.ops.object.transform_apply(scale=True)
    if thickness:
        s = o.modifiers.new("solid", "SOLIDIFY")
        s.thickness = thickness
    m = material("card", "#ffffff", 0, 0.3)
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    m.node_tree.links.new(tex.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    return _assign(o, m)


def pedestal(radius=1.2, height=0.4, color="#1b1b22", location=(0, 0, 0), roughness=0.3):
    x, y, z = location
    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=radius, depth=height, location=(x, y, z + height / 2))
    o = _active()
    b = o.modifiers.new("bevel", "BEVEL")
    b.width = 0.03
    b.segments = 4
    bpy.ops.object.shade_smooth()
    return _assign(o, material("pedestal", color, 0.1, roughness))


def text(body, location=(0, -1.5, 2.8), size=0.5, color="#ffffff", emission=None, emission_strength=3.0,
         extrude=0.05, font="anton", align="CENTER", rotation=(90, 0, 0), metallic=0.0, bevel=0.01):
    """3D text, upright and facing -Y (towards the default camera)."""
    bpy.ops.object.text_add(location=location, rotation=tuple(math.radians(r) for r in rotation))
    o = _active()
    o.data.body = body
    o.data.align_x = align
    o.data.align_y = "CENTER"
    o.data.size = size
    o.data.extrude = extrude
    o.data.bevel_depth = bevel
    path = os.path.join(FONT_DIR, FONTS.get(font, font))
    if os.path.exists(path):
        o.data.font = bpy.data.fonts.load(path)
    return _assign(o, material("text_" + body[:8], color, metallic, 0.3, emission, emission_strength))


def sphere(radius=0.3, location=(1.5, 0, 1.5), color="#ff4fa3", emission=None, roughness=0.2, metallic=0.0):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=location, segments=48, ring_count=24)
    o = _active()
    bpy.ops.object.shade_smooth()
    return _assign(o, material("sphere", color, metallic, roughness, emission))


def torus(major=0.5, minor=0.12, location=(-1.6, 0.5, 2.2), rotation=(60, 20, 0), color="#7a5cff",
          emission=None, metallic=0.6):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, location=location,
                                     rotation=tuple(math.radians(r) for r in rotation))
    o = _active()
    bpy.ops.object.shade_smooth()
    return _assign(o, material("torus", color, metallic, 0.25, emission))


def area_light(location, target=(0, 0, 1), energy=500, color="#ffffff", size=2.0):
    bpy.ops.object.light_add(type="AREA", location=location)
    o = _active()
    o.data.energy = energy
    o.data.color = _rgb(color)
    o.data.size = size
    look_at(o, target)
    return o


def studio_lights(key="#ffffff", rim="#ffffff", fill="#ffffff", strength=1.0, target=(0, 0, 1.2)):
    """Classic key / fill / rim setup around the origin."""
    return [
        area_light((-3.5, -3.0, 4.0), target, 700 * strength, key, 3),
        area_light((3.5, -2.0, 2.5), target, 250 * strength, fill, 3),
        area_light((0.5, 3.5, 4.5), target, 900 * strength, rim, 2),
    ]


def camera(location=(0, -7.5, 2.0), target=(0, 0, 1.3), lens=50):
    bpy.ops.object.camera_add(location=location)
    o = _active()
    o.data.lens = lens
    look_at(o, target)
    bpy.context.scene.camera = o
    return o


def turntable(obj, frames=48, turns=1.0):
    """Spin an object around Z over the frame range (seamless loop)."""
    obj.rotation_euler.z = 0
    obj.keyframe_insert("rotation_euler", index=2, frame=1)
    obj.rotation_euler.z = 2 * math.pi * turns
    obj.keyframe_insert("rotation_euler", index=2, frame=frames + 1)
    for fc in obj.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def orbit_camera(cam, target=(0, 0, 1.3), frames=48, degrees=30):
    """Gently swing the camera around the target for a looping parallax move."""
    empty = bpy.data.objects.new("pivot", None)
    bpy.context.collection.objects.link(empty)
    empty.location = target
    cam.parent = empty
    cam.location = Vector(cam.location) - Vector(target)
    for f, a in ((1, -degrees / 2), (frames // 2 + 1, degrees / 2), (frames + 1, -degrees / 2)):
        empty.rotation_euler.z = math.radians(a)
        empty.keyframe_insert("rotation_euler", index=2, frame=f)


def render_still(path=None):
    path = path or os.environ.get("AD_OUT", "/work/out/ad.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s = bpy.context.scene
    s.render.image_settings.file_format = "PNG"
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("ADKIT_RENDERED", path)


def render_frames(directory=None):
    directory = directory or os.environ.get("AD_FRAMES", "/work/out/frames")
    os.makedirs(directory, exist_ok=True)
    s = bpy.context.scene
    s.render.image_settings.file_format = "PNG"
    s.render.filepath = os.path.join(directory, "f_")
    bpy.ops.render.render(animation=True)
    print("ADKIT_FRAMES", directory)
