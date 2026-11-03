"""Лот 142, Аквилон Signal: 3D-сцена квартиры с отделкой Greystone.
Координаты плана: x вправо, y вниз (метры, 1 м ≈ 83 px по планировке застройщика).
В Blender: X = x, Y = -y, Z вверх.
Запуск: python scene.py <номер_кадра> <выход.png> [samples]
"""
import bpy, math, sys, random
from mathutils import Vector, Euler

random.seed(7)
H = 2.80          # натяжной потолок (бетон 2,87)
SILL = 0.40       # подоконник
WTOP = 2.62       # верх окна

# ---------------------------------------------------------------- reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.render.engine = 'CYCLES'
cy = scn.cycles
cy.device = 'CPU'

def P(x, y, z=0.0):
    return Vector((x, -y, z))

# ---------------------------------------------------------------- materials
def node_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; bsdf = nt.nodes['Principled BSDF']
    return m, nt, bsdf

def mat_plain(name, rgb, rough=0.5, metal=0.0, bump=0.0, bump_scale=60.0, coat=0.0, sheen=0.0):
    m, nt, b = node_mat(name)
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if coat: b.inputs['Coat Weight'].default_value = coat
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
        b.inputs['Sheen Roughness'].default_value = 0.6
    if bump:
        tc = nt.nodes.new('ShaderNodeTexCoord'); nz = nt.nodes.new('ShaderNodeTexNoise')
        nz.inputs['Scale'].default_value = bump_scale; nz.inputs['Detail'].default_value = 8
        bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = bump; bp.inputs['Distance'].default_value = 0.002
        nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def mat_fabric(name, rgb, scale=900.0):
    m = mat_plain(name, rgb, rough=0.92, sheen=0.5)
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    tc = nt.nodes.new('ShaderNodeTexCoord'); w = nt.nodes.new('ShaderNodeTexVoronoi')
    w.inputs['Scale'].default_value = scale
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 40; nz.inputs['Detail'].default_value = 6
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs['Factor'].default_value = 0.12
    mix.inputs['A'].default_value = (*rgb, 1); mix.inputs['B'].default_value = (rgb[0]*0.78, rgb[1]*0.78, rgb[2]*0.78, 1)
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector']); nt.links.new(nz.outputs['Fac'], mix.inputs['Factor'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.35; bp.inputs['Distance'].default_value = 0.001
    nt.links.new(tc.outputs['Object'], w.inputs['Vector']); nt.links.new(w.outputs['Distance'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def mat_wood(name, base=(0.52, 0.40, 0.30), dark=(0.33, 0.23, 0.16), scale=3.0, planks=False, rough=0.45, rot90=False):
    m, nt, b = node_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    if rot90: mp.inputs['Rotation'].default_value = (0, 0, math.pi/2)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    vec = mp.outputs['Vector']
    # волокна: растянутый шум + волны
    st = nt.nodes.new('ShaderNodeMapping'); st.inputs['Scale'].default_value = (0.08, 1.0, 1.0)
    nt.links.new(vec, st.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale*6; nz.inputs['Detail'].default_value = 12; nz.inputs['Distortion'].default_value = 0.6
    nt.links.new(st.outputs['Vector'], nz.inputs['Vector'])
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'Y' if not rot90 else 'X'
    wv.inputs['Scale'].default_value = scale*2.2; wv.inputs['Distortion'].default_value = 9; wv.inputs['Detail'].default_value = 6
    nt.links.new(vec, wv.inputs['Vector'])
    mixf = nt.nodes.new('ShaderNodeMath'); mixf.operation = 'MULTIPLY'
    nt.links.new(nz.outputs['Fac'], mixf.inputs[0]); nt.links.new(wv.outputs['Fac'], mixf.inputs[1])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 0.15; ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.75; ramp.color_ramp.elements[1].color = (*base, 1)
    nt.links.new(mixf.outputs[0], ramp.inputs['Fac'])
    col = ramp.outputs['Color']
    if planks:
        br = nt.nodes.new('ShaderNodeTexBrick')
        br.inputs['Scale'].default_value = 1.0
        br.inputs['Mortar Size'].default_value = 0.0018
        br.inputs['Brick Width'].default_value = 1.38
        br.inputs['Row Height'].default_value = 0.193
        br.offset = 0.37; br.squash = 1.0
        br.inputs['Color1'].default_value = (1, 1, 1, 1); br.inputs['Color2'].default_value = (0.86, 0.86, 0.86, 1)
        br.inputs['Mortar'].default_value = (0.25, 0.25, 0.25, 1)
        nt.links.new(vec, br.inputs['Vector'])
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1.0
        nt.links.new(col, mul.inputs['A']); nt.links.new(br.outputs['Color'], mul.inputs['B'])
        col = mul.outputs['Result']
        bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.25; bp.inputs['Distance'].default_value = 0.0015
        nt.links.new(br.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    nt.links.new(col, b.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = rough - 0.08; rr.inputs['To Max'].default_value = rough + 0.1
    nt.links.new(nz.outputs['Fac'], rr.inputs['Value']); nt.links.new(rr.outputs['Result'], b.inputs['Roughness'])
    return m

def mat_marble(name, base=(0.80, 0.76, 0.70), vein=(0.62, 0.58, 0.53), scale=1.4, rough=0.18, tiles=None):
    m, nt, b = node_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale; nz.inputs['Detail'].default_value = 14; nz.inputs['Distortion'].default_value = 3.5
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    wv = nt.nodes.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = scale*0.9; wv.inputs['Distortion'].default_value = 14; wv.inputs['Detail'].default_value = 10
    nt.links.new(tc.outputs['Object'], wv.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = (*vein, 1); e[1].position = 0.07; e[1].color = (*base, 1)
    nt.links.new(wv.outputs['Fac'], ramp.inputs['Fac'])
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.inputs['Factor'].default_value = 0.18
    nt.links.new(ramp.outputs['Color'], mix.inputs['A']); mix.inputs['B'].default_value = (base[0]*0.93, base[1]*0.92, base[2]*0.9, 1)
    nt.links.new(nz.outputs['Fac'], mix.inputs['Factor'])
    col = mix.outputs['Result']
    if tiles:
        br = nt.nodes.new('ShaderNodeTexBrick'); br.offset = 0.0
        br.inputs['Scale'].default_value = 1.0; br.inputs['Mortar Size'].default_value = 0.0022
        br.inputs['Brick Width'].default_value = tiles[0]; br.inputs['Row Height'].default_value = tiles[1]
        br.inputs['Color1'].default_value = (1, 1, 1, 1); br.inputs['Color2'].default_value = (0.97, 0.97, 0.97, 1)
        br.inputs['Mortar'].default_value = (0.62, 0.6, 0.57, 1)
        mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value = tiles[2] if len(tiles) > 2 else (0, 0, 0)
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], br.inputs['Vector'])
        mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'; mul.inputs['Factor'].default_value = 1
        nt.links.new(col, mul.inputs['A']); nt.links.new(br.outputs['Color'], mul.inputs['B']); col = mul.outputs['Result']
        bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.4; bp.inputs['Distance'].default_value = 0.0015
        nt.links.new(br.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    nt.links.new(col, b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = rough
    return m

def mat_glass(name, tint=(0.95, 0.97, 0.97)):
    m, nt, b = node_mat(name)
    b.inputs['Base Color'].default_value = (*tint, 1); b.inputs['Transmission Weight'].default_value = 1.0
    b.inputs['Roughness'].default_value = 0.0; b.inputs['IOR'].default_value = 1.45
    return m

def mat_emit(name, rgb, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    o = nt.nodes.new('ShaderNodeOutputMaterial'); e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*rgb, 1); e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], o.inputs[0]); return m

def mat_sheer(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes['Principled BSDF']; o = nt.nodes['Material Output']
    b.inputs['Base Color'].default_value = (0.93, 0.92, 0.9, 1); b.inputs['Roughness'].default_value = 0.9
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent'); tr.inputs['Color'].default_value = (0.95, 0.94, 0.92, 1)
    tp = nt.nodes.new('ShaderNodeBsdfTransparent')
    m1 = nt.nodes.new('ShaderNodeMixShader'); m1.inputs[0].default_value = 0.55
    m2 = nt.nodes.new('ShaderNodeMixShader'); m2.inputs[0].default_value = 0.45
    nt.links.new(b.outputs[0], m1.inputs[1]); nt.links.new(tr.outputs[0], m1.inputs[2])
    nt.links.new(m1.outputs[0], m2.inputs[1]); nt.links.new(tp.outputs[0], m2.inputs[2])
    nt.links.new(m2.outputs[0], o.inputs['Surface'])
    return m

def mat_laminate(name, base=(0.56, 0.47, 0.38)):
    """ламинат: доски 1380x193, у каждой своя тональность, волокна вдоль доски"""
    m, nt, b = node_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    br = nt.nodes.new('ShaderNodeTexBrick'); br.offset = 0.37; br.squash = 1.0
    br.inputs['Scale'].default_value = 1.0; br.inputs['Mortar Size'].default_value = 0.0012
    br.inputs['Brick Width'].default_value = 1.38; br.inputs['Row Height'].default_value = 0.193
    br.inputs['Bias'].default_value = 0.0
    br.inputs['Color1'].default_value = (0.0, 0.0, 0.0, 1); br.inputs['Color2'].default_value = (1, 1, 1, 1)
    br.inputs['Mortar'].default_value = (0.5, 0.5, 0.5, 1)
    nt.links.new(tc.outputs['Object'], br.inputs['Vector'])
    # смещение текстуры волокон по доскам: берём значение цвета доски как сдвиг
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(br.outputs['Color'], sep.inputs['Color'])
    off = nt.nodes.new('ShaderNodeCombineXYZ'); nt.links.new(sep.outputs[0], off.inputs['X']); nt.links.new(sep.outputs[0], off.inputs['Y'])
    sc = nt.nodes.new('ShaderNodeVectorMath'); sc.operation = 'SCALE'; sc.inputs['Scale'].default_value = 37.0
    nt.links.new(off.outputs[0], sc.inputs[0])
    add = nt.nodes.new('ShaderNodeVectorMath'); add.operation = 'ADD'
    nt.links.new(tc.outputs['Object'], add.inputs[0]); nt.links.new(sc.outputs[0], add.inputs[1])
    st = nt.nodes.new('ShaderNodeMapping'); st.inputs['Scale'].default_value = (0.9, 28.0, 1.0)
    nt.links.new(add.outputs[0], st.inputs['Vector'])
    nz = nt.nodes.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 2.2; nz.inputs['Detail'].default_value = 15; nz.inputs['Roughness'].default_value = 0.62; nz.inputs['Distortion'].default_value = 0.25
    nt.links.new(st.outputs['Vector'], nz.inputs['Vector'])
    nz2 = nt.nodes.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 0.7; nz2.inputs['Detail'].default_value = 3
    nt.links.new(st.outputs['Vector'], nz2.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB'); e = ramp.color_ramp.elements
    e[0].position = 0.30; e[0].color = (base[0]*0.70, base[1]*0.66, base[2]*0.62, 1)
    e[1].position = 0.70; e[1].color = (base[0]*1.08, base[1]*1.06, base[2]*1.04, 1)
    mixv = nt.nodes.new('ShaderNodeMath'); mixv.operation = 'ADD'
    nt.links.new(nz.outputs['Fac'], mixv.inputs[0]); nt.links.new(nz2.outputs['Fac'], mixv.inputs[1])
    half = nt.nodes.new('ShaderNodeMath'); half.operation = 'MULTIPLY'; half.inputs[1].default_value = 0.5
    nt.links.new(mixv.outputs[0], half.inputs[0])
    nt.links.new(half.outputs[0], ramp.inputs['Fac'])
    # тональность доски ±8%
    tone = nt.nodes.new('ShaderNodeMapRange'); tone.inputs['To Min'].default_value = 0.90; tone.inputs['To Max'].default_value = 1.08
    nt.links.new(sep.outputs[0], tone.inputs['Value'])
    mul = nt.nodes.new('ShaderNodeVectorMath'); mul.operation = 'SCALE'
    nt.links.new(ramp.outputs['Color'], mul.inputs[0]); nt.links.new(tone.outputs['Result'], mul.inputs['Scale'])
    # фаска-шов
    gap = nt.nodes.new('ShaderNodeMix'); gap.data_type = 'RGBA'
    nt.links.new(br.outputs['Fac'], gap.inputs['Factor']); nt.links.new(mul.outputs[0], gap.inputs['A']); gap.inputs['B'].default_value = (0.12, 0.10, 0.08, 1)
    nt.links.new(gap.outputs['Result'], b.inputs['Base Color'])
    rr = nt.nodes.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.32; rr.inputs['To Max'].default_value = 0.48
    nt.links.new(nz.outputs['Fac'], rr.inputs['Value']); nt.links.new(rr.outputs['Result'], b.inputs['Roughness'])
    bp = nt.nodes.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.3; bp.inputs['Distance'].default_value = 0.0015; bp.invert = True
    nt.links.new(br.outputs['Fac'], bp.inputs['Height']); nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

M = {}
M['wall'] = mat_plain('wall', (0.80, 0.785, 0.76), rough=0.88, bump=0.05, bump_scale=180)       # обои под окраску, тёплый светло-серый
M['accent'] = mat_plain('accent', (0.53, 0.52, 0.50), rough=0.9, bump=0.05, bump_scale=180)     # Greystone: акцентная серая стена
M['ceil'] = mat_plain('ceil', (0.86, 0.86, 0.85), rough=0.55)                                   # натяжной матовый
M['floor'] = mat_laminate('floor')  # ламинат дуб серо-бежевый
M['skirt'] = mat_plain('skirt', (0.78, 0.77, 0.75), rough=0.4)
M['door'] = mat_plain('door', (0.72, 0.71, 0.69), rough=0.35)                                   # МДФ светло-серый
M['black'] = mat_plain('black', (0.02, 0.02, 0.02), rough=0.35, metal=0.6)
M['chrome'] = mat_plain('chrome', (0.8, 0.8, 0.8), rough=0.08, metal=1.0)
M['frame'] = mat_plain('frame', (0.10, 0.10, 0.10), rough=0.4, metal=0.3)                       # окна графит
M['sillw'] = mat_plain('sillw', (0.88, 0.88, 0.87), rough=0.3)
M['glass'] = mat_glass('glass')
M['tile_wall'] = mat_marble('tile_wall', base=(0.74, 0.69, 0.62), vein=(0.66, 0.61, 0.55), tiles=(1.2, 0.6), rough=0.22)
M['tile_floor'] = mat_marble('tile_floor', base=(0.68, 0.63, 0.57), vein=(0.60, 0.55, 0.50), tiles=(0.6, 0.6), rough=0.3)
M['ceramic'] = mat_plain('ceramic', (0.93, 0.93, 0.92), rough=0.08, coat=0.6)
M['vanity'] = mat_plain('vanity', (0.90, 0.90, 0.89), rough=0.3)
M['cab'] = mat_plain('cab', (0.40, 0.385, 0.37), rough=0.55)                                    # фасады кухни, тёплый серый
M['cabwood'] = mat_wood('cabwood', base=(0.36, 0.25, 0.17), dark=(0.22, 0.15, 0.10), scale=2.5, rough=0.5, rot90=True)
M['counter'] = mat_marble('counter', base=(0.82, 0.80, 0.77), vein=(0.6, 0.58, 0.55), scale=0.9, rough=0.25)
M['oak'] = mat_wood('oak', base=(0.45, 0.32, 0.22), dark=(0.28, 0.19, 0.13), scale=4, rough=0.5)
M['tabletop'] = mat_marble('tabletop', base=(0.88, 0.87, 0.85), vein=(0.7, 0.69, 0.67), scale=1.2, rough=0.2)
M['boucle'] = mat_fabric('boucle', (0.47, 0.44, 0.40), scale=1400)
M['linen'] = mat_fabric('linen', (0.82, 0.80, 0.76), scale=2200)
M['duvet'] = mat_fabric('duvet', (0.86, 0.85, 0.83), scale=2600)
M['throw'] = mat_fabric('throw', (0.52, 0.46, 0.40), scale=700)
M['grey_fab'] = mat_fabric('grey_fab', (0.38, 0.38, 0.37), scale=1500)
M['curtain'] = mat_fabric('curtain', (0.55, 0.54, 0.52), scale=1800)
M['sheer'] = mat_sheer('sheer')
M['appliance'] = mat_plain('appliance', (0.02, 0.02, 0.02), rough=0.15, coat=1.0)
M['white_app'] = mat_plain('white_app', (0.9, 0.9, 0.89), rough=0.25, coat=0.5)
M['pot'] = mat_plain('pot', (0.25, 0.24, 0.22), rough=0.7)
M['leaf'] = mat_plain('leaf', (0.08, 0.16, 0.06), rough=0.45)
M['rug'] = mat_fabric('rug', (0.62, 0.58, 0.52), scale=500)
M['book1'] = mat_plain('book1', (0.55, 0.45, 0.35), rough=0.7)
M['book2'] = mat_plain('book2', (0.25, 0.28, 0.30), rough=0.7)
M['lampshade'] = mat_glass('lampshade', tint=(0.92, 0.9, 0.86))
M['mirror'] = mat_plain('mirror', (0.9, 0.9, 0.9), rough=0.0, metal=1.0)
M['led'] = mat_emit('led', (1.0, 0.86, 0.68), 18)
M['bulb'] = mat_emit('bulb', (1.0, 0.78, 0.5), 30)
M['screen'] = mat_plain('screen', (0.01, 0.01, 0.012), rough=0.05, coat=1.0)

# ---------------------------------------------------------------- geometry helpers
def bevel(o, w=0.006, seg=3):
    md = o.modifiers.new('bev', 'BEVEL'); md.width = w; md.segments = seg; md.limit_method = 'ANGLE'
    return o

def box(name, x0, y0, z0, x1, y1, z1, mat, bev=0.004, seg=3):
    """плановые координаты: x0..x1, y0..y1 (вниз), z0..z1"""
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object; o.name = name
    o.scale = (abs(x1-x0), abs(y1-y0), abs(z1-z0))
    o.location = ((x0+x1)/2, -(y0+y1)/2, (z0+z1)/2)
    bpy.ops.object.transform_apply(scale=True)
    o.data.materials.append(mat)
    if bev: bevel(o, bev, seg)
    return o

def soft(name, x0, y0, z0, x1, y1, z1, mat, r=0.04, sub=2, disp=0.0, dscale=3.0):
    """мягкий элемент (подушка, матрас)"""
    o = box(name, x0, y0, z0, x1, y1, z1, mat, bev=r, seg=4)
    s = o.modifiers.new('sub', 'SUBSURF'); s.levels = sub; s.render_levels = sub
    if disp:
        t = bpy.data.textures.new(name+'_t', 'CLOUDS'); t.noise_scale = 0.25
        d = o.modifiers.new('disp', 'DISPLACE'); d.texture = t; d.strength = disp; d.mid_level = 0.5
    bpy.ops.object.shade_smooth()
    return o

def cyl(name, x, y, z0, z1, r, mat, verts=48, bev=0.003):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=z1-z0, location=(x, -y, (z0+z1)/2))
    o = bpy.context.active_object; o.name = name; o.data.materials.append(mat)
    if bev: bevel(o, bev, 2)
    bpy.ops.object.shade_smooth(); return o

def sphere(name, x, y, z, r, mat, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=r, location=(x, -y, z))
    o = bpy.context.active_object; o.name = name; o.scale = scale; o.data.materials.append(mat)
    bpy.ops.object.shade_smooth(); return o

def plane_v(name, x0, y0, x1, y1, z0, z1, mat):
    """вертикальная плоскость между точками плана"""
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    v = [bm.verts.new(P(x0, y0, z0)), bm.verts.new(P(x1, y1, z0)), bm.verts.new(P(x1, y1, z1)), bm.verts.new(P(x0, y0, z1))]
    bm.faces.new(v); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); scn.collection.objects.link(o); o.data.materials.append(mat); return o

# ---------------------------------------------------------------- shell
T_EXT, T_INT = 0.30, 0.12
X_FAC = 7.60           # внутренняя грань фасада (окна)
def wall_x(x, y0, y1, t, openings=(), name='w'):
    """стена вдоль y на линии x (грань со стороны комнаты = x, толщина наружу +t). openings: (y0,y1,z0,z1)"""
    segs = [(y0, y1, 0, H + 0.1)]
    for (a, b, z0, z1) in openings:
        new = []
        for (s0, s1, q0, q1) in segs:
            if b <= s0 or a >= s1 or q0 != 0: new.append((s0, s1, q0, q1)); continue
            if a > s0: new.append((s0, a, 0, H+0.1))
            new.append((a, b, 0, z0)) if z0 > 0 else None
            new.append((a, b, z1, H+0.1))
            if b < s1: new.append((b, s1, 0, H+0.1))
        segs = [s for s in new if s]
    for i, (s0, s1, q0, q1) in enumerate(segs):
        if q1 - q0 > 0.001: box(f'{name}{i}', x, s0, q0, x+t, s1, q1, M['wall'], bev=0)

def wall_y(y, x0, x1, t, openings=(), name='w', mat=None):
    segs = [(x0, x1, 0, H + 0.1)]
    for (a, b, z0, z1) in openings:
        new = []
        for (s0, s1, q0, q1) in segs:
            if b <= s0 or a >= s1 or q0 != 0: new.append((s0, s1, q0, q1)); continue
            if a > s0: new.append((s0, a, 0, H+0.1))
            if z0 > 0: new.append((a, b, 0, z0))
            new.append((a, b, z1, H+0.1))
            if b < s1: new.append((b, s1, 0, H+0.1))
        segs = new
    for i, (s0, s1, q0, q1) in enumerate(segs):
        if q1 - q0 > 0.001: box(f'{name}{i}', s0, y, q0, s1, y+t, q1, mat or M['wall'], bev=0)

WIN = {'A_top': (4.90, 6.90), 'A_r': (2.55, 3.60), 'B': (5.10, 7.10), 'K': (8.70, 10.90)}
# фасад x=7.6
wall_x(X_FAC, -0.1, 11.2, T_EXT, openings=[(WIN['A_r'][0], WIN['A_r'][1], SILL, WTOP), (WIN['B'][0], WIN['B'][1], SILL, WTOP), (WIN['K'][0], WIN['K'][1], SILL, WTOP)], name='fac')
wall_y(0.25 - T_EXT, 3.0, 7.9, T_EXT, openings=[(WIN['A_top'][0], WIN['A_top'][1], SILL, WTOP)], name='topw')      # верх комнаты A
wall_x(3.30 - T_INT, 0.0, 6.0, T_INT, name='a_left')                                            # левая стена A
wall_y(3.95, 4.30, X_FAC, T_INT, name='ab')                                                      # между A и B
wall_x(4.30 - T_INT, 3.95, 8.15, T_INT, openings=[(7.05, 7.90, 0, 2.10)], name='b_left')         # дверь в B
wall_y(6.00 - T_INT, 0.25, 3.30, T_INT, name='hall_top')
wall_y(6.00 - T_INT, 3.30, 4.30, T_INT, openings=[(3.40, 4.20, 0, 2.10)], name='a_door')         # дверь в A
wall_x(0.25 - T_EXT, 5.8, 8.3, T_EXT, openings=[(7.00, 7.92, 0, 2.15)], name='entr')             # входная
wall_y(8.15, 0.25, 7.6, T_INT, openings=[(1.35, 2.05, 0, 2.10), (3.45, 4.25, 0, 2.10)], name='hk') # санузел / кухня
wall_x(2.80, 8.15, 11.05, T_INT, name='bk')                                                     # санузел | кухня
wall_x(0.55 - T_INT, 8.15, 11.05, T_INT, name='b_l')
wall_y(11.05, 0.3, 7.9, T_EXT, name='bot')

# пол и потолок
box('floor', 0.0, -0.2, -0.05, 7.6, 11.1, 0.0, M['floor'], bev=0)
box('floor_bath', 0.55, 8.27, 0.0, 2.80, 11.05, 0.008, M['tile_floor'], bev=0)
ceil = box('ceil', -0.2, -0.3, H, 8.0, 11.4, H + 0.05, M['ceil'], bev=0)

# плинтус
def skirt_x(x, y0, y1, side):
    box('sk', x if side > 0 else x - 0.012, y0, 0, x + 0.012 if side > 0 else x, y1, 0.08, M['skirt'], bev=0.002)
def skirt_y(y, x0, x1, side):
    box('sk', x0, y if side > 0 else y - 0.012, 0, x1, y + 0.012 if side > 0 else y, 0.08, M['skirt'], bev=0.002)
skirt_x(3.30, 0.25, 3.95, 1); skirt_y(0.25, 3.3, 7.6, 1); skirt_y(3.95, 3.3, 7.6, -1)
skirt_y(3.95 + T_INT, 4.3, 7.6, 1); skirt_x(4.30, 4.07, 7.05, 1); skirt_y(8.15, 4.3, 7.6, -1)
skirt_y(8.15 + T_INT, 2.92, 7.6, 1); skirt_x(2.92, 8.27, 11.05, 1); skirt_y(11.05, 2.92, 7.6, -1)
skirt_y(6.0, 0.25, 3.3, 1); skirt_y(8.15, 0.25, 1.35, -1); skirt_y(8.15, 2.05, 3.45, -1)

# окна: рама, стекло, подоконник, откосы
def window_x(y0, y1, name):
    x = X_FAC
    box(name+'_sill', x - 0.22, y0 - 0.03, SILL - 0.03, x + 0.08, y1 + 0.03, SILL, M['sillw'], bev=0.004)
    # рама
    fx = x + 0.10
    box(name+'_fb', fx, y0, SILL, fx + 0.07, y1, SILL + 0.06, M['frame'], bev=0.003)
    box(name+'_ft', fx, y0, WTOP - 0.06, fx + 0.07, y1, WTOP, M['frame'], bev=0.003)
    box(name+'_fl', fx, y0, SILL, fx + 0.07, y0 + 0.06, WTOP, M['frame'], bev=0.003)
    box(name+'_fr', fx, y1 - 0.06, SILL, fx + 0.07, y1, WTOP, M['frame'], bev=0.003)
    n = 2 if y1 - y0 < 1.4 else 3
    for i in range(1, n):
        yy = y0 + (y1 - y0) * i / n
        box(name+f'_im{i}', fx, yy - 0.035, SILL, fx + 0.07, yy + 0.035, WTOP, M['frame'], bev=0.003)
    g = box(name+'_g', fx + 0.03, y0 + 0.05, SILL + 0.05, fx + 0.04, y1 - 0.05, WTOP - 0.05, M['glass'], bev=0)
    g.visible_shadow = False
def window_y(x0, x1, name):
    y = 0.25
    box(name+'_sill', x0 - 0.03, y - 0.08, SILL - 0.03, x1 + 0.03, y + 0.22, SILL, M['sillw'], bev=0.004)
    fy = y - 0.17
    box(name+'_fb', x0, fy, SILL, x1, fy + 0.07, SILL + 0.06, M['frame'], bev=0.003)
    box(name+'_ft', x0, fy, WTOP - 0.06, x1, fy + 0.07, WTOP, M['frame'], bev=0.003)
    box(name+'_fl', x0, fy, SILL, x0 + 0.06, fy + 0.07, WTOP, M['frame'], bev=0.003)
    box(name+'_fr', x1 - 0.06, fy, SILL, x1, fy + 0.07, WTOP, M['frame'], bev=0.003)
    xm = (x0 + x1) / 2; box(name+'_im', xm - 0.035, fy, SILL, xm + 0.035, fy + 0.07, WTOP, M['frame'], bev=0.003)
    g = box(name+'_g', x0 + 0.05, fy + 0.03, SILL + 0.05, x1 - 0.05, fy + 0.04, WTOP - 0.05, M['glass'], bev=0)
    g.visible_shadow = False
window_x(*WIN['A_r'], 'wA'); window_x(*WIN['B'], 'wB'); window_x(*WIN['K'], 'wK'); window_y(*WIN['A_top'], 'wAt')

# шторы: тюль + серые портьеры на потолочном карнизе
def fold_panel(name, x, a, b, z0, z1, amp, period, mat):
    import bmesh
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    n = max(8, int((b - a) / period * 12))
    cols = []
    for i in range(n + 1):
        y = a + (b - a) * i / n
        dx = amp * math.sin(2 * math.pi * (y - a) / period + random.random() * 0.2)
        cols.append((bm.verts.new(P(x + dx, y, z0)), bm.verts.new(P(x + dx * 0.6, y, z1))))
    for i in range(n):
        bm.faces.new((cols[i][0], cols[i + 1][0], cols[i + 1][1], cols[i][1]))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); scn.collection.objects.link(o)
    o.data.materials.append(mat)
    for p in o.data.polygons: p.use_smooth = True
    o.modifiers.new('solid', 'SOLIDIFY').thickness = 0.003
    return o

def curtain_x(y0, y1, name, open_frac=0.25):
    x = X_FAC - 0.14
    box(name+'_rail', x - 0.03, y0 - 0.30, H - 0.03, x + 0.04, y1 + 0.30, H, M['skirt'], bev=0)
    fold_panel(name+'_sheer', x + 0.04, y0 - 0.20, y1 + 0.20, 0.02, H - 0.04, 0.022, 0.11, M['sheer'])
    w = (y1 - y0) * open_frac
    fold_panel(name+'_l', x - 0.02, y0 - 0.28, y0 - 0.28 + w, 0.01, H - 0.04, 0.045, 0.14, M['curtain'])
    fold_panel(name+'_r', x - 0.02, y1 + 0.28 - w, y1 + 0.28, 0.01, H - 0.04, 0.045, 0.14, M['curtain'])

curtain_x(*WIN['K'], 'cK', 0.16); curtain_x(*WIN['B'], 'cB', 0.18); curtain_x(*WIN['A_r'], 'cA', 0.22)

# двери МДФ
def door_panel_y(x0, x1, y, side, name, open_deg=0):
    t = 0.04
    box(name+'_frame_l', x0 - 0.06, y - 0.07, 0, x0, y + T_INT + 0.07, 2.16, M['door'], bev=0.003)
    box(name+'_frame_r', x1, y - 0.07, 0, x1 + 0.06, y + T_INT + 0.07, 2.16, M['door'], bev=0.003)
    box(name+'_frame_t', x0 - 0.06, y - 0.07, 2.10, x1 + 0.06, y + T_INT + 0.07, 2.16, M['door'], bev=0.003)
    d = box(name+'_leaf', x0 - 0.04, y + T_INT/2 - t/2, 0.0, x1 + 0.04, y + T_INT/2 + t/2, 2.14, M['door'], bev=0.002)
    h = box(name+'_h', x1 - 0.09, y + T_INT/2 - t/2 - 0.05, 1.0, x1 - 0.07, y + T_INT/2 + t/2 + 0.05, 1.02, M['black'], bev=0.003)
    if open_deg:
        piv = P(x0, y + T_INT/2)
        for o in (d, h):
            o.data.transform(__import__('mathutils').Matrix.Translation(-(Vector((o.location.x, o.location.y, 0)) - piv)))
            o.location = piv + Vector((0, 0, 0)) + (o.location - o.location)
        for o in (d, h):
            o.location = Vector((piv.x, piv.y, o.location.z)); o.rotation_euler = (0, 0, math.radians(open_deg) * side)
def door_frame_x(y0, y1, x, name):
    box(name+'_fl', x - 0.07, y0 - 0.06, 0, x + T_INT + 0.07, y0, 2.16, M['door'], bev=0.003)
    box(name+'_fr', x - 0.07, y1, 0, x + T_INT + 0.07, y1 + 0.06, 2.16, M['door'], bev=0.003)
    box(name+'_ft', x - 0.07, y0 - 0.06, 2.10, x + T_INT + 0.07, y1 + 0.06, 2.16, M['door'], bev=0.003)

door_panel_y(3.45, 4.25, 8.15, 1, 'dK', open_deg=0)
door_panel_y(1.35, 2.05, 8.15, -1, 'dBath', open_deg=0)
door_panel_y(3.40, 4.20, 6.0 - T_INT, 1, 'dA', open_deg=0)
door_frame_x(7.05, 7.90, 4.30 - T_INT, 'dB')
# входная дверь (тёмная)
box('entr_leaf', 0.25 - T_EXT + 0.1, 6.96, 0.0, 0.25 - T_EXT + 0.16, 7.96, 2.18, M['pot'], bev=0.002)
box('entr_trim', 0.25, 6.94, 0.0, 0.27, 7.98, 2.20, M['door'], bev=0.002)
box('entr_trim_hole', 0.27, 7.0, 0.0, 0.271, 7.92, 2.15, M['pot'], bev=0)
box('entr_h', 0.25 - 0.02, 7.80, 1.0, 0.25, 7.83, 1.18, M['black'], bev=0.002)

# ---------------------------------------------------------------- освещение
world = bpy.data.worlds.new('w'); scn.world = world; world.use_nodes = True
wn = world.node_tree; bg = wn.nodes['Background']
sky = wn.nodes.new('ShaderNodeTexSky')
try:
    sky.sky_type = 'NISHITA'
except Exception:
    pass
for attr, val in [('sun_elevation', math.radians(24)), ('sun_rotation', math.radians(110)), ('altitude', 30), ('air_density', 1.2), ('dust_density', 2.5)]:
    try: setattr(sky, attr, val)
    except Exception: pass
try: sky.sun_disc = False
except Exception: pass
wn.links.new(sky.outputs['Color'], bg.inputs['Color']); bg.inputs['Strength'].default_value = 1.0

sun = bpy.data.lights.new('sun', 'SUN'); sun.energy = 5.0; sun.angle = math.radians(1.2); sun.color = (1.0, 0.93, 0.84)
so = bpy.data.objects.new('sun', sun); scn.collection.objects.link(so)
SUN_DIR = Vector((-0.80, -0.35, -0.48)).normalized()
so.rotation_euler = SUN_DIR.to_track_quat('-Z', 'Y').to_euler()

# мягкие порталы в окнах (заполняющий свет неба)
def portal_x(y0, y1):
    l = bpy.data.lights.new('portal', 'AREA'); l.shape = 'RECTANGLE'; l.size = y1 - y0; l.size_y = WTOP - SILL
    l.energy = 420 * (y1 - y0); l.color = (0.92, 0.95, 1.0)
    try: l.cycles.is_portal = False
    except Exception: pass
    o = bpy.data.objects.new('portal', l); scn.collection.objects.link(o)
    o.location = (X_FAC + 0.25, -(y0 + y1)/2, (SILL + WTOP)/2); o.rotation_euler = (0, -math.pi/2, 0)
    o.visible_camera = False
for k in ('A_r', 'B', 'K'): portal_x(*WIN[k])
l = bpy.data.lights.new('portalT', 'AREA'); l.shape = 'RECTANGLE'; l.size = 2.0; l.size_y = WTOP - SILL; l.energy = 250; l.color = (0.92, 0.95, 1.0)
o = bpy.data.objects.new('portalT', l); scn.collection.objects.link(o); o.location = (5.9, -0.0, (SILL+WTOP)/2); o.rotation_euler = (-math.pi/2, 0, 0); o.visible_camera = False

# вид из окна: двор, деревья, соседние башни (размыто)
box('ground', 8.5, -40, -18.0, 80, 60, -17.95, mat_plain('gr', (0.30, 0.33, 0.27), rough=1.0), bev=0)
twr = mat_plain('twr', (0.42, 0.42, 0.42), rough=0.6, metal=0.2)
for (x, y, w, d, h) in [(34, -6, 16, 16, 60), (36, 22, 15, 15, 64), (62, 6, 20, 18, 40), (48, 40, 14, 14, 52)]:
    box('twr', x, y, -18, x + w, y + d, h - 18, twr, bev=0)
treem = mat_plain('tree', (0.13, 0.20, 0.10), rough=0.9)
for i in range(60):
    tx = random.uniform(10, 32); ty = random.uniform(-15, 26)
    sphere('tree', tx, ty, random.uniform(-14, -10), random.uniform(1.8, 3.4), treem, scale=(1, 1, 1.3))

def ceiling_spot(x, y, power=12):
    cyl('spot', x, y, H - 0.006, H + 0.001, 0.045, M['black'], bev=0)
    cyl('spotl', x, y, H - 0.008, H - 0.006, 0.03, M['bulb'], bev=0)
    l = bpy.data.lights.new('s', 'SPOT'); l.energy = power; l.spot_size = math.radians(80); l.spot_blend = 0.6; l.color = (1.0, 0.82, 0.62); l.shadow_soft_size = 0.03
    o = bpy.data.objects.new('s', l); scn.collection.objects.link(o); o.location = (x, -y, H - 0.02)

# ---------------------------------------------------------------- КУХНЯ (x 2.92–7.6, y 8.27–11.05)
KX0, KY0, KX1, KY1 = 2.92, 8.27, X_FAC, 11.05
# угловая кухня вдоль левой стены (x=2.92) и нижней (y=11.05) — как на плане
D = 0.60
# нижние модули вдоль левой стены y 8.95..11.05
box('k_base_l', KX0, 8.95, 0.10, KX0 + D, KY1 - D, 0.86, M['cab'], bev=0.003)
box('k_base_b', KX0, KY1 - D, 0.10, 5.30, KY1, 0.86, M['cab'], bev=0.003)
box('k_plinth', KX0, 8.97, 0.0, KX0 + D - 0.05, KY1 - 0.05, 0.10, M['black'], bev=0)
box('k_plinth2', KX0, KY1 - D + 0.05, 0.0, 5.28, KY1, 0.10, M['black'], bev=0)
# швы фасадов
for yy in [9.55, 10.05]:
    box('seam', KX0 + D, yy - 0.0015, 0.12, KX0 + D + 0.002, yy + 0.0015, 0.85, M['black'], bev=0)
for xx in [3.95, 4.55]:
    box('seam', xx - 0.0015, KY1 - D - 0.002, 0.12, xx + 0.0015, KY1 - D, 0.85, M['black'], bev=0)
box('seam_h', KX0 + D, 8.95, 0.48, KX0 + D + 0.002, KY1 - D, 0.483, M['black'], bev=0)
# столешница
box('k_top_l', KX0, 8.95, 0.86, KX0 + D + 0.02, KY1, 0.90, M['counter'], bev=0.003)
box('k_top_b', KX0, KY1 - D - 0.02, 0.86, 5.32, KY1, 0.90, M['counter'], bev=0.003)
# фартук
box('k_splash_l', KX0, 8.95, 0.90, KX0 + 0.012, KY1, 1.52, M['counter'], bev=0)
box('k_splash_b', KX0, KY1 - 0.012, 0.90, 5.32, KY1, 1.52, M['counter'], bev=0)
# верхние шкафы до потолка
box('k_up_l', KX0, 8.95, 1.52, KX0 + 0.35, KY1 - 0.35, H - 0.002, M['cab'], bev=0.003)
box('k_up_b', KX0 + 0.35, KY1 - 0.35, 1.52, 5.32, KY1, H - 0.002, M['cab'], bev=0.003)
for yy in [9.55, 10.15]:
    box('seamu', KX0 + 0.35, yy - 0.0015, 1.53, KX0 + 0.352, yy + 0.0015, H - 0.01, M['black'], bev=0)
box('led_l', KX0 + 0.20, 8.97, 1.505, KX0 + 0.32, KY1 - 0.36, 1.515, M['led'], bev=0)
# пенал под дерево со встроенной духовкой: у двери, y 8.27..8.95
box('k_tall', KX0, 8.30, 0.0, KX0 + D, 8.95, H - 0.002, M['cabwood'], bev=0.003)
box('oven', KX0 + D, 8.38, 0.86, KX0 + D + 0.005, 8.88, 1.45, M['appliance'], bev=0.002)
box('oven_disp', KX0 + D + 0.005, 8.55, 1.38, KX0 + D + 0.007, 8.71, 1.42, M['led'], bev=0)
# варочная и мойка
box('hob', KX0 + 0.06, 9.55, 0.90, KX0 + 0.58, 10.15, 0.905, M['appliance'], bev=0.002)
box('sink', 4.0, KY1 - 0.52, 0.86, 4.55, KY1 - 0.10, 0.905, M['chrome'], bev=0.01)
box('sink_in', 4.03, KY1 - 0.49, 0.70, 4.52, KY1 - 0.13, 0.906, mat_plain('sink_d', (0.35, 0.35, 0.35), rough=0.3, metal=1.0), bev=0.01)
cyl('tap', 4.28, KY1 - 0.06, 0.90, 1.22, 0.014, M['black'])
box('tap_s', 4.27, KY1 - 0.30, 1.19, 4.29, KY1 - 0.05, 1.22, M['black'], bev=0.006)
# декор на столешнице
cyl('kettle', KX0 + 0.25, 10.55, 0.90, 1.12, 0.08, M['white_app'])
box('coffee', 3.35, KY1 - 0.38, 0.90, 3.65, KY1 - 0.08, 1.24, M['white_app'], bev=0.02)
for i, c in enumerate([M['black'], M['pot'], M['black']]):
    cyl('bottle', 4.85 + i * 0.09, KY1 - 0.12, 0.90, 1.18 - i * 0.03, 0.03, c)
cyl('board', 5.05, KY1 - 0.06, 0.90, 1.30, 0.13, M['oak'], verts=6, bev=0.002)
# обеденная зона у окна
TX, TY = 6.35, 9.75
cyl('t_top', TX, TY, 0.735, 0.76, 0.55, M['tabletop'], verts=96)
cyl('t_leg', TX, TY, 0.0, 0.735, 0.06, M['oak'])
cyl('t_base', TX, TY, 0.0, 0.03, 0.30, M['oak'])
def chair(x, y, ang):
    import mathutils
    g = []
    g.append(soft('ch_seat', x - 0.24, y - 0.23, 0.42, x + 0.24, y + 0.23, 0.50, M['boucle'], r=0.04))
    g.append(soft('ch_back', x - 0.25, y + 0.14, 0.52, x + 0.25, y + 0.24, 0.80, M['boucle'], r=0.045))
    for dx, dy in [(-0.2, -0.19), (0.2, -0.19), (-0.2, 0.19), (0.2, 0.19)]:
        g.append(cyl('ch_leg', x + dx, y + dy, 0.0, 0.43, 0.017, M['oak'], verts=16))
    pivot = P(x, y)
    R = mathutils.Matrix.Rotation(ang, 4, 'Z')
    for o in g:
        o.location = pivot + R @ (o.location - pivot); o.rotation_euler = (0, 0, ang)
for k, a in enumerate([0, math.pi/2, math.pi, -math.pi/2]):
    cx = TX + 0.72 * math.sin(a); cyy = TY + 0.72 * math.cos(a)
    chair(cx, cyy, -a + math.pi)
# ваза на столе
cyl('vase', TX - 0.08, TY + 0.06, 0.76, 0.98, 0.065, mat_plain('vase_c', (0.78, 0.74, 0.68), rough=0.6))
cyl('vase_n', TX - 0.08, TY + 0.06, 0.98, 1.02, 0.03, mat_plain('vase_c2', (0.78, 0.74, 0.68), rough=0.6))
for i in range(5):
    bpy.ops.mesh.primitive_cylinder_add(vertices=6, radius=0.0035, depth=0.55, location=(TX - 0.08, -(TY + 0.06), 1.25))
    o = bpy.context.active_object; o.rotation_euler = (random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), 0); o.data.materials.append(M['oak'])
# подвесные светильники
for dx in (-0.18, 0.18):
    cyl('cord', TX + dx, TY, 1.62, H, 0.003, M['black'], verts=8, bev=0)
    sphere('shade', TX + dx, TY, 1.50, 0.13, M['lampshade'])
    sphere('bulb', TX + dx, TY, 1.50, 0.025, M['bulb'])
    l = bpy.data.lights.new('pend', 'POINT'); l.energy = 9; l.color = (1, 0.75, 0.5); l.shadow_soft_size = 0.03
    o = bpy.data.objects.new('pend', l); scn.collection.objects.link(o); o.location = (TX + dx, -TY, 1.50)
# торшер у окна
cyl('fl_base', 7.28, 10.92, 0.0, 0.02, 0.16, M['black'])
cyl('fl_pole', 7.28, 10.92, 0.02, 1.55, 0.012, M['black'], verts=12)
cyl('fl_shade', 7.28, 10.92, 1.45, 1.70, 0.20, mat_plain('shade_f', (0.86, 0.83, 0.78), rough=0.9), verts=48)
ceiling_spot(4.0, 9.0, 10); ceiling_spot(4.0, 10.2, 10)

# ---------------------------------------------------------------- КОМНАТА A 16,4 (x 3.3–7.6, y 0.25–3.95) — спальня
AX0, AY0, AX1, AY1 = 3.30, 0.25, X_FAC, 3.95
# акцентная стена за кроватью: перегородка A|B (y=3.95), изголовье к ней
box('accA', 4.4, 3.95 - 0.004, 0, 7.6, 3.95, H, M['accent'], bev=0)
BX0, BX1 = 4.85, 6.65  # кровать 160
soft('bed_head', BX0 - 0.10, 3.82, 0.25, BX1 + 0.10, 3.95, 1.25, M['grey_fab'], r=0.04)
box('bed_frame', BX0, 1.75, 0.08, BX1, 3.85, 0.38, M['grey_fab'], bev=0.03)
soft('mattress', BX0 + 0.02, 1.78, 0.38, BX1 - 0.02, 3.83, 0.58, M['linen'], r=0.05)
soft('duvet', BX0 - 0.03, 1.72, 0.50, BX1 + 0.03, 3.20, 0.66, M['duvet'], r=0.06, disp=0.025)
soft('throwA', BX0 - 0.05, 1.70, 0.62, BX1 + 0.05, 2.25, 0.68, M['throw'], r=0.03, disp=0.01)
for i, (a, b) in enumerate([(BX0 + 0.08, BX0 + 0.80), (BX1 - 0.80, BX1 - 0.08)]):
    soft('pil', a, 3.45, 0.58, b, 3.80, 0.78, M['linen'], r=0.07, disp=0.012).rotation_euler = (math.radians(-12), 0, 0)
soft('pil2', BX0 + 0.45, 3.25, 0.58, BX1 - 0.45, 3.45, 0.76, M['throw'], r=0.07)
for x0 in (BX0 - 0.55, BX1 + 0.08):
    box('nstand', x0, 3.45, 0.0, x0 + 0.45, 3.93, 0.50, M['oak'], bev=0.006)
    cyl('lampb', x0 + 0.22, 3.70, 0.50, 0.80, 0.035, M['black'])
    sphere('lamps', x0 + 0.22, 3.70, 0.88, 0.10, M['lampshade'], scale=(1, 1, 0.8))
    l = bpy.data.lights.new('nl', 'POINT'); l.energy = 4; l.color = (1, 0.72, 0.45); l.shadow_soft_size = 0.05
    o = bpy.data.objects.new('nl', l); scn.collection.objects.link(o); o.location = (x0 + 0.22, -3.70, 0.88)
# шкаф в нише у левой стены (как на плане) x 3.30–3.92, y 0.6–2.9
box('wardA', 3.30, 0.40, 0.0, 3.92, 2.95, H - 0.002, M['door'], bev=0.003)
for yy in (1.25, 2.1):
    box('wseam', 3.92, yy - 0.0015, 0.02, 3.922, yy + 0.0015, H - 0.02, M['black'], bev=0)
for yy in (1.20, 1.30, 2.05, 2.15):
    box('wh', 3.92, yy, 0.95, 3.94, yy + 0.012, 1.35, M['black'], bev=0.002)
# ковёр
box('rugA', 4.6, 1.25, 0.0, 6.9, 3.6, 0.012, M['rug'], bev=0.004)
# кресло у окна и столик
soft('armA', 6.65, 0.55, 0.0, 7.35, 1.20, 0.42, M['boucle'], r=0.08)
soft('armA_b', 6.65, 0.50, 0.40, 7.35, 0.68, 0.85, M['boucle'], r=0.07)
cyl('sideA', 6.30, 1.45, 0.0, 0.52, 0.20, M['oak'])
for i in range(3):
    box('book', 6.18, 1.40 + i*0.002, 0.52 + i*0.03, 6.42, 1.58, 0.545 + i*0.03, [M['book1'], M['book2'], M['white_app']][i], bev=0.002)
# картина над кроватью
box('artA', 5.15, 3.93, 1.40, 6.35, 3.95, 2.10, mat_plain('art', (0.70, 0.66, 0.60), rough=0.8, bump=0.3, bump_scale=8), bev=0.002)
box('artAf', 5.13, 3.925, 1.38, 6.37, 3.95, 2.12, M['oak'], bev=0.002)
ceiling_spot(4.6, 1.0, 9); ceiling_spot(6.3, 1.0, 9)

# ---------------------------------------------------------------- КОМНАТА B 13,5 (x 4.3–7.6, y 4.07–8.15) — спальня/кабинет
BXL = 4.30
box('accB', BXL, 4.07, 0, BXL + 0.004, 7.0, H, M['wall'], bev=0)
# кровать 140 головой к стене A|B (как на плане), y 4.07..6.1
B2X0, B2X1 = 5.30, 6.75
soft('bed2_head', B2X0 - 0.08, 4.07, 0.25, B2X1 + 0.08, 4.20, 1.10, M['boucle'], r=0.04)
box('bed2_frame', B2X0, 4.15, 0.08, B2X1, 6.20, 0.36, M['boucle'], bev=0.03)
soft('mat2', B2X0 + 0.02, 4.18, 0.36, B2X1 - 0.02, 6.17, 0.55, M['linen'], r=0.05)
soft('duv2', B2X0 - 0.03, 4.85, 0.48, B2X1 + 0.03, 6.25, 0.63, M['duvet'], r=0.06, disp=0.025)
soft('thr2', B2X0 - 0.04, 5.70, 0.60, B2X1 + 0.04, 6.27, 0.66, M['grey_fab'], r=0.03, disp=0.01)
for (a, b) in [(B2X0 + 0.06, B2X0 + 0.70), (B2X1 - 0.70, B2X1 - 0.06)]:
    soft('pil3', a, 4.22, 0.55, b, 4.55, 0.74, M['linen'], r=0.07, disp=0.012)
# шкаф у левой стены (на плане) x 4.30–4.90, y 4.07–6.6
box('wardB', BXL, 4.07, 0.0, BXL + 0.58, 6.65, H - 0.002, M['door'], bev=0.003)
for yy in (4.95, 5.80):
    box('wseamB', BXL + 0.58, yy - 0.0015, 0.02, BXL + 0.582, yy + 0.0015, H - 0.02, M['black'], bev=0)
# рабочее место у окна
box('desk', 6.95, 6.35, 0.72, 7.55, 7.75, 0.75, M['oak'], bev=0.004)
for (x, y) in [(7.0, 6.4), (7.5, 6.4), (7.0, 7.7), (7.5, 7.7)]:
    box('dleg', x - 0.015, y - 0.015, 0.0, x + 0.015, y + 0.015, 0.72, M['black'], bev=0.002)
box('monitor', 7.40, 6.80, 0.95, 7.42, 7.40, 1.30, M['screen'], bev=0.004)
box('mon_st', 7.42, 7.08, 0.75, 7.46, 7.12, 0.95, M['black'], bev=0.002)
soft('dchair', 6.45, 6.80, 0.42, 6.90, 7.30, 0.50, M['grey_fab'], r=0.04)
soft('dchair_b', 6.38, 6.80, 0.50, 6.48, 7.30, 0.92, M['grey_fab'], r=0.04)
cyl('dch_leg', 6.67, 7.05, 0.05, 0.42, 0.02, M['black'])
cyl('dch_base', 6.67, 7.05, 0.02, 0.06, 0.26, M['black'], verts=5)
box('rugB', 5.1, 5.6, 0.0, 6.9, 7.6, 0.012, M['rug'], bev=0.004)
ceiling_spot(5.4, 5.0, 8); ceiling_spot(5.4, 7.2, 8)

# ---------------------------------------------------------------- ПРИХОЖАЯ 9,4 (x 0.25–4.3, y 6.0–8.15)
box('wardH', 0.30, 6.0, 0.0, 3.25, 6.62, H - 0.002, M['door'], bev=0.003)
for xx in (1.05, 1.80, 2.55):
    box('hseam', xx - 0.0015, 6.62, 0.02, xx + 0.0015, 6.622, H - 0.02, M['black'], bev=0)
box('benchH', 0.30, 7.95, 0.0, 1.20, 8.13, 0.45, M['oak'], bev=0.004)
box('hookrail', 0.29, 6.75, 1.65, 0.31, 6.95, 1.68, M['black'], bev=0)
ceiling_spot(1.0, 7.3, 10); ceiling_spot(2.4, 7.3, 10); ceiling_spot(3.8, 6.8, 10)
box('rugH', 0.9, 6.95, 0.0, 2.9, 7.85, 0.01, M['rug'], bev=0.003)
box('artH', 1.6, 8.13, 1.25, 2.5, 8.15, 1.85, mat_plain('artH', (0.62, 0.58, 0.52), rough=0.8, bump=0.3, bump_scale=6), bev=0.002)
box('artHf', 1.58, 8.125, 1.23, 2.52, 8.15, 1.87, M['black'], bev=0.002)
cyl('vaseH', 0.6, 8.04, 0.45, 0.75, 0.07, M['pot'])

# ---------------------------------------------------------------- САНУЗЕЛ 4,5 (x 0.55–2.80, y 8.27–11.05)
SX0, SY0, SX1, SY1 = 0.55, 8.27, 2.80, 11.05
# плитка на стенах до потолка
box('tW_l', SX0, SY0, 0.0, SX0 + 0.01, SY1, H, M['tile_wall'], bev=0)
box('tW_r', SX1 - 0.01, SY0, 0.0, SX1, SY1, H, M['tile_wall'], bev=0)
box('tW_b', SX0, SY1 - 0.01, 0.0, SX1, SY1, H, M['tile_wall'], bev=0)
box('tW_t1', SX0, SY0, 0.0, 1.35, SY0 + 0.01, H, M['tile_wall'], bev=0)
box('tW_t2', 2.05, SY0, 0.0, SX1, SY0 + 0.01, H, M['tile_wall'], bev=0)
box('tW_t3', 1.35, SY0, 2.10, 2.05, SY0 + 0.01, H, M['tile_wall'], bev=0)
# ванна вдоль нижней стены
box('tub', SX0 + 0.01, SY1 - 0.71, 0.0, SX1 - 0.01, SY1 - 0.01, 0.58, M['ceramic'], bev=0.02)
box('tub_in', SX0 + 0.08, SY1 - 0.64, 0.12, SX1 - 0.08, SY1 - 0.08, 0.59, mat_plain('tubin', (0.92, 0.92, 0.91), rough=0.05), bev=0.06)
box('screen_g', 1.7, SY1 - 0.72, 0.58, 1.71, SY1 - 0.01, 2.0, M['glass'], bev=0)
box('screen_f', 1.695, SY1 - 0.72, 0.58, 1.715, SY1 - 0.70, 2.0, M['black'], bev=0)
cyl('shower_bar', SX0 + 0.35, SY1 - 0.03, 0.9, 2.05, 0.011, M['black'])
cyl('shower_head', SX0 + 0.35, SY1 - 0.12, 2.0, 2.02, 0.10, M['black'], bev=0.002)
box('mixer', SX0 + 0.25, SY1 - 0.06, 0.78, SX0 + 0.45, SY1 - 0.02, 0.84, M['black'], bev=0.01)
# подвесной унитаз на левой стене
box('inst_panel', SX0 + 0.01, 9.60, 0.95, SX0 + 0.02, 9.85, 1.10, M['black'], bev=0.002)
soft('wc', SX0 + 0.01, 9.55, 0.36, SX0 + 0.55, 9.92, 0.42, M['ceramic'], r=0.12)
soft('wc_b', SX0 + 0.01, 9.55, 0.20, SX0 + 0.20, 9.92, 0.40, M['ceramic'], r=0.08)
# стиральная машина в углу (на плане) x 0.55–1.15, y 8.27–8.9 → под столешницей
box('wm', SX0 + 0.02, SY0 + 0.05, 0.0, SX0 + 0.62, SY0 + 0.65, 0.85, M['white_app'], bev=0.02)
cyl('wm_door', SX0 + 0.32, SY0 + 0.66, 0.30, 0.31, 0.17, M['glass'], verts=48)
# тумба с раковиной у правой стены (на плане две раковины → одна широкая)
box('van', SX1 - 0.47, 8.95, 0.45, SX1 - 0.01, 9.95, 0.90, M['vanity'], bev=0.004)
box('van_seam', SX1 - 0.472, 8.95, 0.67, SX1 - 0.47, 9.95, 0.673, M['black'], bev=0)
box('van_top', SX1 - 0.48, 8.94, 0.88, SX1 - 0.01, 9.96, 0.92, M['ceramic'], bev=0.01)
box('van_bowl', SX1 - 0.40, 9.15, 0.86, SX1 - 0.10, 9.75, 0.921, mat_plain('bowl', (0.9, 0.9, 0.89), rough=0.05), bev=0.04)
box('van_tap', SX1 - 0.06, 9.43, 0.92, SX1 - 0.03, 9.47, 1.12, M['black'], bev=0.006)
box('van_tap_s', SX1 - 0.20, 9.43, 1.09, SX1 - 0.03, 9.47, 1.12, M['black'], bev=0.006)
box('mirB_f', SX1 - 0.022, 9.03, 1.08, SX1 - 0.01, 9.87, 2.12, M['black'], bev=0.004)
box('mirB', SX1 - 0.03, 9.06, 1.11, SX1 - 0.022, 9.84, 2.09, M['mirror'], bev=0.002)
box('shelf', SX1 - 0.14, 10.0, 1.55, SX1 - 0.01, 10.35, 1.57, M['black'], bev=0.002)
for i in range(4):
    cyl('btl', SX1 - 0.07, 10.05 + i*0.08, 1.57, 1.70 + random.uniform(-0.03, 0.03), 0.025, [M['black'], M['white_app'], M['pot'], M['black']][i])
# полотенцесушитель на левой стене
for z in [0.95, 1.10, 1.25, 1.40, 1.55]:
    box('towel', SX0 + 0.06, 10.05, z, SX0 + 0.085, 10.55, z + 0.02, M['black'], bev=0.008)
box('towel_v1', SX0 + 0.05, 10.04, 0.9, SX0 + 0.09, 10.07, 1.6, M['black'], bev=0.01)
box('towel_v2', SX0 + 0.05, 10.53, 0.9, SX0 + 0.09, 10.56, 1.6, M['black'], bev=0.01)
soft('towel_f', SX0 + 0.08, 10.10, 0.98, SX0 + 0.13, 10.50, 1.45, M['linen'], r=0.02)
ceiling_spot(1.3, 9.2, 28); ceiling_spot(1.9, 10.3, 28); ceiling_spot(1.3, 10.3, 20)
box('led_mir', SX1 - 0.035, 9.06, 2.10, SX1 - 0.025, 9.84, 2.12, M['led'], bev=0)

# ---------------------------------------------------------------- камеры (x, y, z) -> (tx, ty, tz), фокусное
CAMS = {
 1: ('Кухня-столовая', (3.75, 8.45, 1.45), (7.0, 10.3, 1.05), 16, 1.9),
 2: ('Кухня: рабочая зона', (7.25, 8.50, 1.50), (3.3, 10.7, 1.1), 17, 1.6),
 3: ('Кухня: столешница и фартук', (4.75, 9.45, 1.45), (3.4, 10.95, 1.0), 26, 1.5),
 4: ('Спальня 16,4 м²', (4.10, 0.50, 1.50), (6.4, 3.5, 0.75), 16, -1.2),
 5: ('Спальня 16,4 м²: окна', (4.15, 3.30, 1.45), (6.8, 0.6, 1.2), 17, -1.4),
 6: ('Комната 13,5 м²', (5.80, 7.95, 1.50), (6.1, 4.3, 0.8), 16, 1.1),
 7: ('Комната 13,5 м²: рабочее место', (4.55, 7.60, 1.50), (7.4, 6.3, 1.0), 18, 1.1),
 8: ('Прихожая', (3.9, 7.85, 1.55), (0.5, 6.6, 1.15), 16, 1.6),
 9: ('Санузел', (1.15, 8.45, 1.55), (2.2, 10.6, 0.9), 14, 1.0),
 10: ('Санузел: тумба и ванна', (0.85, 8.75, 1.50), (2.6, 9.8, 1.0), 15, 1.0),
}

def setup_cam(i):
    name, (x, y, z), (tx, ty, tz), lens, ev = CAMS[i]
    cam = bpy.data.cameras.new('cam'); cam.lens = lens; cam.sensor_width = 36
    cam.dof.use_dof = True; cam.dof.aperture_fstop = 8.0
    o = bpy.data.objects.new('cam', cam); scn.collection.objects.link(o)
    o.location = P(x, y, z)
    d = P(tx, ty, tz) - o.location
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    cam.dof.focus_distance = d.length * 0.7
    # двухточечная перспектива: вертикали вертикальны (как у интерьерного фотографа)
    pitch = math.atan2(d.z, math.hypot(d.x, d.y))
    yaw = math.atan2(d.y, d.x) - math.pi/2
    o.rotation_euler = (math.pi/2, 0, yaw)
    cam.shift_y = math.tan(pitch) * lens / 36
    scn.camera = o
    return name, ev

if __name__ == '__main__':
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    idx = int(argv[0]); out = argv[1]; samples = int(argv[2]) if len(argv) > 2 else 256
    res = argv[3] if len(argv) > 3 else '1920x1440'
    name, ev = setup_cam(idx)
    r = scn.render; r.resolution_x, r.resolution_y = map(int, res.split('x')); r.resolution_percentage = 100
    r.image_settings.file_format = 'PNG'; r.filepath = out
    cy.samples = samples; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
    cy.use_denoising = True
    try: cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception: pass
    cy.max_bounces = 8; cy.diffuse_bounces = 4; cy.glossy_bounces = 4; cy.transmission_bounces = 8; cy.caustics_reflective = False; cy.caustics_refractive = False
    cy.sample_clamp_indirect = 8
    r.threads_mode = 'AUTO'
    vs = scn.view_settings
    for vt in ('AgX', 'Filmic'):
        try: vs.view_transform = vt; break
        except Exception: pass
    try: vs.look = 'AgX - Medium High Contrast'
    except Exception: pass
    vs.exposure = float(argv[4]) if len(argv) > 4 else ev
    bpy.ops.render.render(write_still=True)
    print('DONE', idx, name, out)
