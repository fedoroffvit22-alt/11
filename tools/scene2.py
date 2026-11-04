"""v2: телевизоры по планировке, мебель по образцам застройщика, вид из окна, новые ракурсы.
Запуск: python scene2.py <кадр> <out.png> [samples] [WxH] [ev]"""
import sys, math, random
sys.argv_saved = list(sys.argv)
import scene as S
from scene import *          # box, soft, cyl, sphere, M, P, mat_plain, mat_fabric, bpy, ...
import bmesh, mathutils
random.seed(11)

def kill(*prefixes):
    for o in list(bpy.data.objects):
        if any(o.name.startswith(p) for p in prefixes):
            bpy.data.objects.remove(o, do_unlink=True)

# ---------- дерево без «ряби»
def swap_mat(old, new):
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for i, sl in enumerate(o.material_slots):
                if sl.material and sl.material.name == old: o.material_slots[i].material = new
oak2 = S.mat_laminate('oak2', base=(0.50, 0.37, 0.26)); swap_mat('oak', oak2); M['oak'] = oak2
cw2 = S.mat_laminate('cabwood2', base=(0.38, 0.26, 0.17)); swap_mat('cabwood', cw2); M['cabwood'] = cw2
M['orange'] = mat_plain('orange2', (0.85, 0.30, 0.03), rough=0.45, bump=0.2, bump_scale=300)

# ---------- вид из окна: фото ЖК вместо коробок
kill('twr', 'tree', 'ground')
img = bpy.data.images.load('/home/user/11/landing/img/towers-park-2400.webp')
mb = bpy.data.materials.new('backdrop'); mb.use_nodes = True; nt = mb.node_tree
for n in list(nt.nodes): nt.nodes.remove(n)
o_ = nt.nodes.new('ShaderNodeOutputMaterial'); em = nt.nodes.new('ShaderNodeEmission'); tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img
lp = nt.nodes.new('ShaderNodeLightPath'); mx = nt.nodes.new('ShaderNodeMixShader'); tr = nt.nodes.new('ShaderNodeBsdfTransparent')
nt.links.new(tx.outputs['Color'], em.inputs['Color']); em.inputs['Strength'].default_value = 1.5
nt.links.new(lp.outputs['Is Camera Ray'], mx.inputs[0]); nt.links.new(tr.outputs[0], mx.inputs[1]); nt.links.new(em.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], o_.inputs['Surface'])
def backdrop(loc, rot, w):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    b = bpy.context.active_object; b.name = 'backdrop'; b.scale = (w, w * 1350 / 2400, 1); b.data.materials.append(mb)
    b.visible_shadow = False
backdrop((34, -5.5, 9.0), (math.pi/2, 0, math.pi/2), 60)          # за фасадом с окнами (x+)
backdrop((5.9, 30, 9.0), (math.pi/2, 0, math.pi), 60)              # за верхним окном спальни (y+ в Blender)

# ---------- кухня: фасады с рамкой (как на образце), техника, декор
FR = mat_plain('cab_fr', (0.43, 0.415, 0.40), rough=0.5)
def shaker_x(x, y0, y1, z0, z1, mat=FR, w=0.055, t=0.007):
    box('sh', x, y0 + w, z0, x + t, y1 - w, z0 + w, mat, bev=0.0015); box('sh', x, y0 + w, z1 - w, x + t, y1 - w, z1, mat, bev=0.0015)
    box('sh', x, y0, z0, x + t, y0 + w, z1, mat, bev=0.0015); box('sh', x, y1 - w, z0, x + t, y1, z1, mat, bev=0.0015)
def shaker_y(y, x0, x1, z0, z1, mat=FR, w=0.055, t=0.007):
    box('sh', x0 + w, y - t, z0, x1 - w, y, z0 + w, mat, bev=0.0015); box('sh', x0 + w, y - t, z1 - w, x1 - w, y, z1, mat, bev=0.0015)
    box('sh', x0, y - t, z0, x0 + w, y, z1, mat, bev=0.0015); box('sh', x1 - w, y - t, z0, x1, y, z1, mat, bev=0.0015)
KX0, KY1, D = 2.92, 11.05, 0.60
for a, b in [(8.96, 9.54), (9.56, 10.04), (10.06, 10.44)]: shaker_x(KX0 + D, a, b, 0.12, 0.47); shaker_x(KX0 + D, a, b, 0.49, 0.85)
for a, b in [(3.53, 3.94), (3.96, 4.54), (4.56, 5.29)]: shaker_y(KY1 - D, a, b, 0.12, 0.85)
for a, b in [(8.96, 9.54), (9.56, 10.14), (10.16, 10.69)]: shaker_x(KX0 + 0.35, a, b, 1.53, 2.78)
for a, b in [(3.96, 4.64), (4.66, 5.31)]: shaker_y(KY1 - 0.35, a, b, 1.53, 2.78)
kill('seam', 'kettle', 'coffee', 'bottle', 'board', 'vase', 'Cylinder', 'fl_')
# чайник
cyl('kettle_b', KX0 + 0.26, 10.62, 0.90, 1.10, 0.085, M['white_app'])
cyl('kettle_l', KX0 + 0.26, 10.62, 1.10, 1.12, 0.06, M['black'])
bpy.ops.mesh.primitive_torus_add(major_radius=0.07, minor_radius=0.012, location=(KX0 + 0.26, -10.53, 1.02), rotation=(0, math.pi/2, 0))
bpy.context.active_object.data.materials.append(M['black'])
# кофемашина
soft('cm_body', 3.32, KY1 - 0.40, 0.90, 3.62, KY1 - 0.06, 1.25, M['white_app'], r=0.035)
box('cm_front', 3.38, KY1 - 0.405, 1.0, 3.56, KY1 - 0.40, 1.18, M['black'], bev=0.01)
cyl('cm_cup', 3.47, KY1 - 0.30, 0.90, 0.97, 0.035, M['ceramic'])
# доски и бутылки
box('board1', 5.05, KY1 - 0.05, 0.90, 5.30, KY1 - 0.025, 1.32, M['oak'], bev=0.01)
box('board2', 4.90, KY1 - 0.07, 0.90, 5.12, KY1 - 0.05, 1.20, M['cabwood'], bev=0.01)
for i, c in enumerate([M['black'], M['pot'], M['black']]):
    cyl('btl', 4.66 + i * 0.075, KY1 - 0.12, 0.90, 1.20 - i * 0.04, 0.028, c)
# ваза с фруктами на столе
TX, TY = 6.35, 9.75
cyl('bowl', TX + 0.12, TY - 0.10, 0.76, 0.84, 0.15, M['ceramic'], verts=64)
for i in range(5):
    sphere('fruit', TX + 0.12 + random.uniform(-0.07, 0.07), TY - 0.10 + random.uniform(-0.07, 0.07), 0.86 + random.uniform(0, 0.03), 0.04, M['orange'])
def eucalyptus(x, y, z0, n_stems=7, h=0.5, spread=0.22, name='eu'):
    green = mat_plain('euc', (0.30, 0.38, 0.31), rough=0.55)
    for s in range(n_stems):
        ax, ay = random.uniform(-0.35, 0.35), random.uniform(-0.35, 0.35)
        for k in range(10):
            t = (k + 1) / 10
            px = x + math.sin(ay) * h * t + random.uniform(-0.01, 0.01)
            py = y + math.sin(ax) * h * t + random.uniform(-0.01, 0.01)
            pz = z0 + h * t * 0.9
            for side in (-1, 1):
                lf = sphere(name, px + side * 0.018, py, pz, 0.022 + 0.008 * (1 - t), green, scale=(1, 1, 0.12))
                lf.rotation_euler = (random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2), random.uniform(0, 6.28))
cyl('vase2', TX - 0.12, TY + 0.10, 0.76, 0.95, 0.055, mat_plain('vasec', (0.75, 0.71, 0.65), rough=0.6))
eucalyptus(TX - 0.12, TY + 0.10, 0.92, n_stems=6, h=0.42)
# торшер — в угол у верхнего края окна
cyl('fl2_base', 7.28, 8.50, 0.0, 0.02, 0.16, M['black']); cyl('fl2_pole', 7.28, 8.50, 0.02, 1.55, 0.012, M['black'], verts=12)
cyl('fl2_shade', 7.28, 8.50, 1.45, 1.70, 0.20, mat_plain('shade2', (0.86, 0.83, 0.78), rough=0.9), verts=48)
# телевизор на стене кухни (по плану — верхняя стена кухни, напротив стола)
def tv_wall_y(y, x0, x1, z0, facing_down=True, name='tv'):
    t = 0.035
    if facing_down:
        box(name, x0, y, z0, x1, y + t, z0 + (x1 - x0) * 0.5625, M['screen'], bev=0.004)
    else:
        box(name, x0, y - t, z0, x1, y, z0 + (x1 - x0) * 0.5625, M['screen'], bev=0.004)
tv_wall_y(8.27, 5.35, 6.35, 1.30, True, 'tv_k')

# новые стулья: мягкое сиденье, гнутая спинка, каркас из дуба (как на образце)
kill('ch_')
def arc_band(name, cx, cy, z0, z1, r, a0, a1, mat):
    me = bpy.data.meshes.new(name); bm = bmesh.new(); n = 24; cols = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        cols.append((bm.verts.new(P(x, y, z0)), bm.verts.new(P(x, y, z1))))
    for i in range(n): bm.faces.new((cols[i][0], cols[i + 1][0], cols[i + 1][1], cols[i][1]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); scn.collection.objects.link(o); o.data.materials.append(mat)
    o.modifiers.new('s', 'SOLIDIFY').thickness = 0.045
    sb = o.modifiers.new('sub', 'SUBSURF'); sb.levels = 2; sb.render_levels = 2
    for p in o.data.polygons: p.use_smooth = True
    return o
def chair2(x, y, face):
    """face — угол, куда смотрит сидящий (радианы, в плане)"""
    parts = []
    parts.append(soft('ch_seat', x - 0.23, y - 0.22, 0.43, x + 0.23, y + 0.22, 0.51, M['boucle'], r=0.06))
    back_ang = face + math.pi
    parts.append(arc_band('ch_back', x, y, 0.58, 0.80, 0.24, back_ang - 1.2, back_ang + 1.2, M['boucle']))
    parts.append(arc_band('ch_rail', x, y, 0.55, 0.575, 0.255, back_ang - 1.1, back_ang + 1.1, M['oak']))
    for a in (face + 0.75, face - 0.75, back_ang + 0.75, back_ang - 0.75):
        lx, ly = x + 0.2 * math.cos(a), y + 0.2 * math.sin(a)
        l = cyl('ch_leg', lx, ly, 0.0, 0.45, 0.016, M['oak'], verts=16)
        l.rotation_euler = (math.sin(a) * 0.08, -math.cos(a) * 0.08, 0) if False else (0.0, 0.0, 0.0)
    return parts
for a in [0, math.pi/2, math.pi, -math.pi/2]:
    cx, cyy = TX + 0.70 * math.cos(a), TY + 0.70 * math.sin(a)
    chair2(cx, cyy, a + math.pi)

# ---------- спальня 16,4: кровать по плану, изголовье со стёжкой, ТВ у окна
kill('bed_', 'mattress', 'duvet', 'throwA', 'pil', 'nstand', 'lampb', 'lamps', 'nl', 'rugA', 'armA', 'sideA', 'book', 'artA')
for o in list(bpy.data.objects):
    if o.type == 'LIGHT' and o.name.startswith('nl'): bpy.data.objects.remove(o, do_unlink=True)
def tilt(o, rx):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    o.rotation_euler = (rx, 0, 0)

def bed(x0, x1, y_head, y_foot, head_dir, fab, name):
    """head_dir=+1 — изголовье на большем y (внизу плана)"""
    yh, yf = y_head, y_foot
    lo, hi = min(yh, yf), max(yh, yf)
    # изголовье со стёжкой
    hz0, hz1 = 0.30, 1.20
    tb = 0.10
    hy0, hy1 = (yh - tb, yh) if head_dir > 0 else (yh, yh + tb)
    n = 8
    for i in range(n):
        a = x0 - 0.08 + (x1 - x0 + 0.16) * i / n; b = x0 - 0.08 + (x1 - x0 + 0.16) * (i + 1) / n
        soft(name + '_hb', a + 0.004, hy0, hz0, b - 0.004, hy1, hz1, fab, r=0.045)
    box(name + '_frame', x0, lo + (0.08 if head_dir < 0 else 0), 0.10, x1, hi - (0.08 if head_dir > 0 else 0), 0.36, fab, bev=0.03)
    box(name + '_legs', x0 + 0.05, lo + 0.1, 0.0, x1 - 0.05, hi - 0.1, 0.10, M['black'], bev=0)
    m0, m1 = (lo + 0.02, hi - 0.10) if head_dir > 0 else (lo + 0.10, hi - 0.02)
    soft(name + '_mat', x0 + 0.02, m0, 0.36, x1 - 0.02, m1, 0.56, M['linen'], r=0.05)
    # одеяло: верх + свисающие края
    d0, d1 = (lo - 0.04, hi - 0.55) if head_dir > 0 else (lo + 0.55, hi + 0.04)
    soft(name + '_duv', x0 - 0.05, d0, 0.52, x1 + 0.05, d1, 0.62, M['duvet'], r=0.05, disp=0.018)
    soft(name + '_duvL', x0 - 0.07, d0, 0.26, x0 - 0.03, d1, 0.60, M['duvet'], r=0.02, disp=0.01)
    soft(name + '_duvR', x1 + 0.03, d0, 0.26, x1 + 0.07, d1, 0.60, M['duvet'], r=0.02, disp=0.01)
    fe = d0 if head_dir > 0 else d1
    soft(name + '_duvF', x0 - 0.05, fe - 0.02 if head_dir > 0 else fe - 0.02, 0.24, x1 + 0.05, fe + 0.02, 0.60, M['duvet'], r=0.02, disp=0.01)
    # отворот одеяла
    tz = (hi - 0.75, hi - 0.55) if head_dir > 0 else (lo + 0.55, lo + 0.75)
    soft(name + '_fold', x0 - 0.04, tz[0], 0.60, x1 + 0.04, tz[1], 0.66, M['linen'], r=0.03)
    # плед на ногах
    pz = (lo + 0.05, lo + 0.55) if head_dir > 0 else (hi - 0.55, hi - 0.05)
    soft(name + '_throw', x0 - 0.06, pz[0], 0.60, x1 + 0.06, pz[1], 0.67, M['throw'], r=0.03, disp=0.012)
    # подушки, прислонены к изголовью
    w = (x1 - x0) / 2
    for i in range(2):
        a = x0 + 0.05 + i * w; b = a + w - 0.10
        py0, py1 = (hi - 0.30, hi - 0.10) if head_dir > 0 else (lo + 0.10, lo + 0.30)
        p = soft(name + '_pil', a, py0, 0.56, b, py1, 0.98, M['linen'], r=0.08, disp=0.01)
        tilt(p, math.radians(-18 * head_dir))
    dp0, dp1 = (hi - 0.48, hi - 0.30) if head_dir > 0 else (lo + 0.30, lo + 0.48)
    p = soft(name + '_dec', (x0 + x1) / 2 - 0.30, dp0, 0.58, (x0 + x1) / 2 + 0.30, dp1, 0.88, M['grey_fab'], r=0.07)
    tilt(p, math.radians(-12 * head_dir))
def nightstand(x0, y0, y1, name, mat=None):
    box(name, x0, y0, 0.0, x0 + 0.45, y1, 0.48, mat or M['oak'], bev=0.006)
    box(name + '_dr', x0 + 0.03, y0 - 0.002 if False else y0, 0.30, x0 + 0.42, y0 + 0.002, 0.31, M['black'], bev=0)
    cyl(name + '_lb', x0 + 0.22, (y0 + y1) / 2, 0.48, 0.52, 0.06, M['ceramic'])
    cyl(name + '_lp', x0 + 0.22, (y0 + y1) / 2, 0.52, 0.78, 0.012, M['black'], verts=12)
    sh = cyl(name + '_ls', x0 + 0.22, (y0 + y1) / 2, 0.74, 0.92, 0.13, mat_plain('lsh', (0.9, 0.88, 0.84), rough=0.9), verts=48)
    l = bpy.data.lights.new('nl2', 'POINT'); l.energy = 6; l.color = (1, 0.72, 0.45); l.shadow_soft_size = 0.08
    o = bpy.data.objects.new('nl2', l); scn.collection.objects.link(o); o.location = (x0 + 0.22, -(y0 + y1) / 2, 0.82)
BX0, BX1 = 5.15, 6.75
bed(BX0, BX1, 3.95, 1.80, +1, M['grey_fab'], 'bedA')
nightstand(BX0 - 0.55, 3.45, 3.92, 'nsA1'); nightstand(BX1 + 0.08, 3.45, 3.92, 'nsA2')
box('rugA2', 4.65, 1.30, 0.0, 7.25, 3.70, 0.012, M['rug'], bev=0.004)
box('artA2', 5.35, 3.915, 1.38, 6.55, 3.935, 2.06, mat_plain('art2', (0.72, 0.68, 0.62), rough=0.85, bump=0.35, bump_scale=6), bev=0.002)
box('artA2f', 5.32, 3.93, 1.35, 6.58, 3.95, 2.09, M['oak'], bev=0.002)
# консоль и ТВ у верхнего окна (по плану)
box('consA', 5.05, 0.27, 0.0, 6.75, 0.70, 0.36, M['oak'], bev=0.006)
for xx in (5.62, 6.18):
    box('consAs', xx - 0.001, 0.70, 0.03, xx + 0.001, 0.702, 0.34, M['black'], bev=0)
box('tvA_st', 5.85, 0.40, 0.36, 5.95, 0.50, 0.46, M['black'], bev=0.004)
box('tvA', 5.29, 0.44, 0.46, 6.51, 0.475, 0.46 + 1.22 * 0.5625, M['screen'], bev=0.004)
# кресло в углу у шкафа
soft('armA2', 4.05, 0.50, 0.0, 4.75, 1.15, 0.44, M['boucle'], r=0.09)
soft('armA2b', 4.05, 0.42, 0.40, 4.75, 0.62, 0.84, M['boucle'], r=0.08)
cyl('sideA2', 4.95, 1.35, 0.0, 0.50, 0.19, M['oak'])
for i in range(3):
    box('bookA', 4.85, 1.28, 0.50 + i * 0.03, 5.06, 1.44, 0.525 + i * 0.03, [M['book1'], M['book2'], M['white_app']][i], bev=0.002)

# ---------- комната 13,5: кровать по плану, ТВ на нижней стене
kill('bed2', 'mat2', 'duv2', 'thr2', 'pil3', 'rugB')
B2X0, B2X1 = 5.45, 6.95
bed(B2X0, B2X1, 4.07, 6.15, -1, M['boucle'], 'bedB')
nightstand(6.98, 4.10, 4.55, 'nsB')
box('rugB2', 5.0, 5.5, 0.0, 7.2, 7.4, 0.012, M['rug'], bev=0.004)
box('consB', 5.35, 7.75, 0.0, 6.95, 8.15, 0.40, M['oak'], bev=0.006)
tv_wall_y(8.15, 5.54, 6.76, 0.95, False, 'tv_b')
kill('desk', 'dleg', 'monitor', 'mon_st', 'dchair', 'dch_')
# рабочее место у окна, ближе к шкафу? нет — у окна сверху (y 5.1..)
box('desk2', 7.0, 6.45, 0.72, 7.55, 7.55, 0.745, M['oak'], bev=0.004)
for (x, y) in [(7.04, 6.5), (7.5, 6.5), (7.04, 7.5), (7.5, 7.5)]:
    box('dl', x - 0.014, y - 0.014, 0.0, x + 0.014, y + 0.014, 0.72, M['black'], bev=0.002)
box('lapt', 7.18, 6.80, 0.745, 7.45, 7.15, 0.76, M['chrome'], bev=0.004)
cyl('dlamp', 7.45, 7.40, 0.745, 1.15, 0.01, M['black'], verts=10); sphere('dlamps', 7.42, 7.40, 1.15, 0.07, M['lampshade'])
soft('dch2', 6.55, 6.80, 0.44, 6.95, 7.20, 0.52, M['grey_fab'], r=0.05)
arc_band('dch2b', 6.75, 7.0, 0.60, 0.85, 0.21, math.pi - 1.1, math.pi + 1.1, M['grey_fab'])
for a in (0.8, -0.8, math.pi + 0.8, math.pi - 0.8):
    cyl('dch2l', 6.75 + 0.18 * math.cos(a), 7.0 + 0.18 * math.sin(a), 0.0, 0.45, 0.014, M['black'], verts=12)
cyl('potB', 4.95, 7.85, 0.0, 0.45, 0.17, M['pot']); eucalyptus(4.95, 7.85, 0.40, n_stems=8, h=0.7)

# ---------- прихожая: декор
kill('artH')
box('artH2', 2.38, 8.12, 1.22, 3.12, 8.14, 1.72, mat_plain('artH', (0.62, 0.58, 0.52), rough=0.8, bump=0.3, bump_scale=6), bev=0.002)
box('artH2f', 2.35, 8.135, 1.19, 3.15, 8.15, 1.75, M['black'], bev=0.002)
cyl('potH', 0.55, 6.85, 0.0, 0.40, 0.15, M['pot']); eucalyptus(0.55, 6.85, 0.36, n_stems=7, h=0.65)

def trim_y(x0, x1, y, name):
    for yy in (y - 0.012, y + S.T_INT):
        box(name+'_tl', x0 - 0.07, yy, 0, x0 + 0.01, yy + 0.012, 2.20, M['door'], bev=0.002)
        box(name+'_tr', x1 - 0.01, yy, 0, x1 + 0.07, yy + 0.012, 2.20, M['door'], bev=0.002)
        box(name+'_tt', x0 - 0.07, yy, 2.12, x1 + 0.07, yy + 0.012, 2.20, M['door'], bev=0.002)
trim_y(3.45, 4.25, 8.15, 'trK'); trim_y(1.35, 2.05, 8.15, 'trB'); trim_y(3.40, 4.20, 6.0 - S.T_INT, 'trA')


# ---------- санузел v2: ванна 1,75 м, шторка вдоль края, нормальный подвесной унитаз
kill('tub', 'screen_', 'shower_', 'mixer', 'wc', 'inst_panel')
SX0, SY0, SX1, SY1 = 0.55, 8.27, 2.80, 11.05
TX0, TY0 = 1.04, SY1 - 0.72          # ванна x 1.04–2.79, y 10.33–11.04
box('tub2', TX0, TY0, 0.0, SX1 - 0.01, SY1 - 0.01, 0.56, M['ceramic'], bev=0.025, seg=4)
box('tub2_in', TX0 + 0.07, TY0 + 0.07, 0.16, SX1 - 0.08, SY1 - 0.08, 0.565, mat_plain('tubin2', (0.93, 0.93, 0.92), rough=0.04), bev=0.08, seg=6)
box('tub2_rim', TX0, TY0, 0.555, SX1 - 0.01, TY0 + 0.012, 0.575, M['ceramic'], bev=0.006)
# пенал-ниша слева от ванны (как на плане)
box('bath_nook', SX0 + 0.01, TY0, 0.0, TX0 - 0.005, SY1 - 0.01, 1.90, M['vanity'], bev=0.004)
box('bath_nook_s', SX0 + 0.012, TY0 - 0.001, 0.95, TX0 - 0.007, TY0 + 0.001, 0.953, M['black'], bev=0)
# стеклянная шторка 80 см вдоль открытого края, со стороны лейки (левый конец)
box('scr_g', TX0 + 0.02, TY0 + 0.03, 0.575, TX0 + 0.82, TY0 + 0.04, 2.00, M['glass'], bev=0.002)
box('scr_p', TX0 + 0.005, TY0 + 0.025, 0.575, TX0 + 0.03, TY0 + 0.045, 2.00, M['black'], bev=0.002)
box('scr_t', TX0 + 0.02, TY0 + 0.025, 1.985, TX0 + 0.82, TY0 + 0.045, 2.00, M['black'], bev=0.001)
# смеситель, штанга и лейка на длинной стене со стороны шторки
box('mix2', TX0 + 0.30, SY1 - 0.055, 0.80, TX0 + 0.50, SY1 - 0.01, 0.86, M['black'], bev=0.012)
cyl('mix2_sp', TX0 + 0.40, SY1 - 0.10, 0.74, 0.76, 0.014, M['black'], verts=16)
cyl('bar2', TX0 + 0.40, SY1 - 0.03, 0.95, 2.00, 0.011, M['black'], verts=16)
cyl('head2', TX0 + 0.40, SY1 - 0.14, 2.00, 2.015, 0.11, M['black'], bev=0.002)
box('arm2', TX0 + 0.39, SY1 - 0.14, 2.015, TX0 + 0.41, SY1 - 0.02, 2.03, M['black'], bev=0.003)
box('niche_sh', TX0 + 0.75, SY1 - 0.10, 1.20, TX0 + 1.05, SY1 - 0.01, 1.215, M['black'], bev=0.002)
for i, c in enumerate([M['white_app'], M['black'], M['pot']]):
    cyl('btl2', TX0 + 0.80 + i * 0.09, SY1 - 0.055, 1.215, 1.38 - i * 0.03, 0.026, c, verts=24)
# подвесной унитаз на левой стене
WY = 9.74
box('inst2', SX0 + 0.01, WY - 0.12, 0.98, SX0 + 0.022, WY + 0.12, 1.14, M['black'], bev=0.004)
box('inst2_b', SX0 + 0.022, WY - 0.004, 1.00, SX0 + 0.026, WY + 0.004, 1.12, mat_plain('btn', (0.15, 0.15, 0.15), rough=0.3), bev=0)
soft('wc2_tank', SX0 + 0.01, WY - 0.17, 0.25, SX0 + 0.22, WY + 0.17, 0.42, M['ceramic'], r=0.07)
bowl = sphere('wc2_bowl', SX0 + 0.33, WY, 0.33, 1.0, M['ceramic'], scale=(0.24, 0.175, 0.11))
bpy.ops.object.select_all(action='DESELECT'); bowl.select_set(True); bpy.context.view_layer.objects.active = bowl
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
seat = sphere('wc2_seat', SX0 + 0.32, WY, 0.43, 1.0, M['ceramic'], scale=(0.245, 0.18, 0.018))
lidb = soft('wc2_hinge', SX0 + 0.06, WY - 0.12, 0.42, SX0 + 0.12, WY + 0.12, 0.45, M['ceramic'], r=0.02)
kill('towel')
for z in [0.95, 1.10, 1.25, 1.40, 1.55]:
    box('towel2', SX0 + 0.06, 9.99, z, SX0 + 0.085, 10.29, z + 0.02, M['black'], bev=0.008)
box('towel2_v1', SX0 + 0.05, 9.98, 0.9, SX0 + 0.09, 10.01, 1.6, M['black'], bev=0.01)
box('towel2_v2', SX0 + 0.05, 10.27, 0.9, SX0 + 0.09, 10.30, 1.6, M['black'], bev=0.01)
soft('towel2_f', SX0 + 0.08, 10.03, 0.98, SX0 + 0.13, 10.25, 1.45, M['linen'], r=0.02)
# коврик
box('bmat', 1.25, TY0 - 0.62, 0.008, 2.05, TY0 - 0.10, 0.02, M['linen'], bev=0.008)

# ---------- свет: чуть теплее, меньше заливки
for o in bpy.data.objects:
    if o.type == 'LIGHT' and o.data.type == 'AREA': o.data.energy *= 0.8

# ---------- ракурсы
S.CAMS.clear()
S.CAMS.update({
 1: ('Кухня-столовая', (3.75, 8.45, 1.42), (7.0, 10.4, 1.05), 18, 1.6),
 2: ('Кухня: гарнитур', (7.30, 10.82, 1.45), (3.4, 8.9, 1.15), 18, 1.4),
 3: ('Обеденная зона и ТВ', (4.75, 10.70, 1.38), (7.0, 8.4, 1.15), 20, 1.4),
 4: ('Спальня 16,4 м²', (7.28, 0.62, 1.48), (4.6, 3.55, 0.85), 18, -1.0),
 5: ('Спальня 16,4 м²: окна и ТВ', (4.05, 3.70, 1.48), (7.0, 1.1, 1.0), 18, -1.0),
 6: ('Комната 13,5 м²', (7.30, 7.95, 1.48), (4.9, 4.3, 0.9), 18, 0.9),
 7: ('Комната 13,5 м²: ТВ и рабочее место', (4.98, 4.35, 1.50), (6.6, 8.1, 0.95), 18, 0.9),
 8: ('Прихожая', (0.55, 7.55, 1.50), (4.0, 6.45, 1.15), 16, 1.5),
 9: ('Санузел', (1.15, 8.45, 1.55), (2.2, 10.6, 0.9), 14, 1.0),
 10: ('Санузел: тумба и ванна', (0.85, 8.75, 1.50), (2.6, 9.8, 1.0), 15, 1.0),
})
S.CAMS.update({
 11: ('Кухня: окно и обеденная зона', (5.95, 10.65, 1.40), (7.45, 9.1, 1.1), 24, 1.3),
 12: ('Кухня: пенал и духовка', (4.85, 9.35, 1.40), (2.95, 8.70, 1.30), 20, 1.5),
 13: ('Кухня: варочная панель', (4.35, 9.85, 1.30), (2.95, 9.95, 0.95), 24, 1.5),
 14: ('Кухня: вид на дверь', (6.55, 10.55, 1.48), (3.85, 8.05, 1.15), 20, 1.4),
 15: ('Кухня: стол', (5.55, 9.15, 1.60), (6.35, 9.8, 0.76), 35, 1.3),
 16: ('Спальня 16,4 м²: кровать', (5.95, 1.15, 1.45), (5.95, 3.9, 0.95), 22, -0.9),
 17: ('Спальня 16,4 м²: шкаф', (6.95, 2.45, 1.45), (3.4, 1.3, 1.3), 20, -0.9),
 18: ('Спальня 16,4 м²: тумба', (4.95, 2.95, 1.05), (4.82, 3.7, 0.72), 35, -0.6),
 19: ('Спальня 16,4 м²: кресло', (5.25, 2.25, 1.40), (4.3, 0.7, 0.6), 24, -0.9),
 20: ('Комната 13,5 м²: кровать', (6.15, 7.55, 1.45), (6.15, 4.07, 0.9), 20, 0.9),
 21: ('Комната 13,5 м²: стол у окна', (6.35, 6.25, 1.35), (7.4, 7.2, 0.85), 28, 0.8),
 22: ('Комната 13,5 м²: шкаф и дверь', (6.90, 5.20, 1.50), (4.4, 7.4, 1.2), 18, 0.9),
 23: ('Комната 13,5 м²: от двери', (4.45, 7.45, 1.50), (7.3, 5.6, 1.0), 16, 0.9),
 24: ('Прихожая: к входной двери', (2.20, 8.00, 1.50), (0.3, 6.4, 1.2), 16, 1.5),
 25: ('Прихожая: к кухне', (1.00, 6.95, 1.50), (3.9, 8.15, 1.1), 18, 1.5),
 26: ('Прихожая: шкаф и вход', (2.00, 7.95, 1.40), (0.3, 6.6, 1.0), 20, 1.5),
 27: ('Санузел: унитаз и полотенцесушитель', (2.12, 8.45, 1.50), (0.6, 10.2, 0.8), 16, 1.0),
 28: ('Санузел: раковина', (1.45, 9.45, 1.45), (2.78, 9.45, 1.25), 22, 1.0),
 29: ('Санузел: ванна', (2.20, 9.55, 1.55), (1.0, 10.9, 0.8), 18, 1.0),
 30: ('Санузел: общий вид сверху', (1.70, 8.35, 2.10), (1.7, 10.4, 0.4), 14, 1.0),
})

if __name__ == '__main__':
    argv = sys.argv[1:]
    ids = [int(x) for x in argv[0].split(',')]; out = argv[1]; samples = int(argv[2]) if len(argv) > 2 else 128
    res = argv[3] if len(argv) > 3 else '1600x1200'
    r = scn.render; r.resolution_x, r.resolution_y = map(int, res.split('x')); r.resolution_percentage = 100
    r.image_settings.file_format = 'PNG'; r.filepath = out
    cy = scn.cycles
    cy.samples = samples; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.012
    cy.use_denoising = True
    try: cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception: pass
    cy.max_bounces = 10; cy.diffuse_bounces = 5; cy.glossy_bounces = 4; cy.transmission_bounces = 8
    cy.caustics_reflective = False; cy.caustics_refractive = False; cy.sample_clamp_indirect = 8
    vs = scn.view_settings; vs.view_transform = 'AgX'
    try: vs.look = 'AgX - Medium High Contrast'
    except Exception: pass
    import os
    for idx in ids:
        for o in list(bpy.data.objects):
            if o.type == 'CAMERA': bpy.data.objects.remove(o, do_unlink=True)
        name, ev = S.setup_cam(idx)
        vs.exposure = float(argv[4]) if len(argv) > 4 else ev
        r.filepath = os.path.join(out, f'raw_{idx:02d}.png') if len(ids) > 1 or os.path.isdir(out) else out
        bpy.ops.render.render(write_still=True)
        print('DONE', idx, name, r.filepath, flush=True)
