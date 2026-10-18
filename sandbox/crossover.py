"""CreateOS x Stripe crossover film: two energy rings converge and lock, wordmark reveal."""
import sys
sys.path.insert(0, "/opt/adkit")
from adkit import *
import bpy, math

FRAMES = 96
reset()
render_settings(res=432, samples=10, aspect=16 / 9, frames=FRAMES)
s = bpy.context.scene
s.cycles.max_bounces = 4
world("#04040a", 0.15)
floor("#07070d", roughness=0.08)

VIOLET, CYAN, PINK = "#635bff", "#22e0ff", "#ff4fa3"

def ring(color, loc, rot):
    o = torus(major=1.05, minor=0.07, location=loc, rotation=rot, color=color, emission=color, metallic=0.2)
    o.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 6
    return o

# Two rings fly in from the sides and interlock at the centre.
r1 = ring(VIOLET, (-5, 0, 1.6), (90, 0, 0))
r2 = ring(CYAN, (5, 0, 1.6), (90, 0, 90))
for o, x0 in ((r1, -5), (r2, 5)):
    o.location.x = x0
    o.keyframe_insert("location", frame=1)
    o.location.x = -0.45 if x0 < 0 else 0.45
    o.keyframe_insert("location", frame=36)
    o.rotation_euler.z += math.radians(200)
    o.keyframe_insert("rotation_euler", frame=FRAMES)
for o in (r1, r2):
    for fc in o.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.easing = "EASE_OUT"

# Core orb that ignites when the rings lock.
core = sphere(radius=0.28, location=(0, 0, 1.6), color="#ffffff", emission="#ffffff")
em = core.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
em.default_value = 0
em.keyframe_insert("default_value", frame=34)
em.default_value = 25
em.keyframe_insert("default_value", frame=40)
em.default_value = 8
em.keyframe_insert("default_value", frame=52)

# Floating sparks
import random
random.seed(7)
for i in range(14):
    c = random.choice([VIOLET, CYAN, PINK])
    sp = sphere(radius=random.uniform(0.03, 0.07),
                location=(random.uniform(-4, 4), random.uniform(-1, 3), random.uniform(0.3, 3.4)),
                color=c, emission=c)
    sp.keyframe_insert("location", frame=1)
    sp.location.z += random.uniform(0.4, 0.9)
    sp.keyframe_insert("location", frame=FRAMES)

# Wordmark rises in after the lock.
def rise(obj, f0, f1, z0, z1):
    obj.location.z = z0
    obj.scale = (0.001, 0.001, 0.001)
    obj.keyframe_insert("location", frame=f0)
    obj.keyframe_insert("scale", frame=f0)
    obj.location.z = z1
    obj.scale = (1, 1, 1)
    obj.keyframe_insert("location", frame=f1)
    obj.keyframe_insert("scale", frame=f1)

t1 = text("CreateOS", location=(-1.95, -0.6, 0), size=0.62, color="#ffffff", emission=CYAN,
          emission_strength=1.2, font="poppins", extrude=0.06)
tx = text("x", location=(0, -0.6, 0), size=0.5, color="#ffffff", emission=PINK, emission_strength=3, font="poppins")
t2 = text("Stripe", location=(1.75, -0.6, 0), size=0.62, color="#ffffff", emission=VIOLET,
          emission_strength=1.6, font="poppins", extrude=0.06)
sub = text("BUILD AGENTS THAT RUN CODE", location=(0, -0.6, 0), size=0.2, color="#c8c8da",
           emission="#c8c8da", emission_strength=0.8, font="poppins-regular", extrude=0.01)
rise(t1, 42, 56, -0.4, 0.38)
rise(tx, 46, 58, -0.4, 0.42)
rise(t2, 44, 58, -0.4, 0.38)
rise(sub, 58, 70, -0.6, 0.02)

area_light((-4, -3, 4), (0, 0, 1), 400, CYAN, 3)
area_light((4, -3, 4), (0, 0, 1), 400, VIOLET, 3)
area_light((0, 4, 5), (0, 0, 1), 600, PINK, 3)

# Slow push-in with a slight rise.
cam = camera(location=(0, -10.5, 2.4), target=(0, 0, 1.1), lens=40)
cam.keyframe_insert("location", frame=1)
cam.location = (0, -8.2, 1.9)
cam.keyframe_insert("location", frame=FRAMES)

render_frames()
