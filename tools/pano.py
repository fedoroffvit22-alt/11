"""360-панорамы для Kuula: python pano.py <ids через запятую> <outdir> [samples] [WxH]"""
import sys, os, math
argv = sys.argv[1:]; sys.argv = ['x']
import scene2 as T
from scene import bpy, scn, P
# двери открыты: убираем полотна
T.kill('dK_leaf', 'dK_h', 'dBath_leaf', 'dBath_h', 'dA_leaf', 'dA_h')
PANOS = {
 1: ('kuhnya', (5.00, 9.50, 1.50), 0, 1.4),
 2: ('spalnya-16', (5.90, 1.30, 1.50), 0, -0.9),
 3: ('komnata-13', (6.20, 6.85, 1.50), 0, 0.9),
 4: ('prihozhaya-vhod', (1.40, 7.35, 1.50), 0, 1.4),
 5: ('prihozhaya-koridor', (3.80, 7.10, 1.50), 0, 1.4),
 6: ('sanuzel', (1.65, 9.35, 1.50), 0, 1.0),
}
ids = [int(x) for x in argv[0].split(',')]; out = argv[1]
samples = int(argv[2]) if len(argv) > 2 else 64; W, H = map(int, (argv[3] if len(argv) > 3 else '4096x2048').split('x'))
os.makedirs(out, exist_ok=True)
r = scn.render; r.resolution_x, r.resolution_y, r.resolution_percentage = W, H, 100
r.image_settings.file_format = 'JPEG'; r.image_settings.quality = 94
cy = scn.cycles; cy.samples = samples; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015; cy.use_denoising = True
try: cy.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
cy.max_bounces = 10; cy.diffuse_bounces = 5; cy.glossy_bounces = 4; cy.transmission_bounces = 8; cy.sample_clamp_indirect = 8
vs = scn.view_settings; vs.view_transform = 'AgX'
try: vs.look = 'AgX - Medium High Contrast'
except Exception: pass
for i in ids:
    slug, (x, y, z), yaw, ev = PANOS[i]
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA': bpy.data.objects.remove(o, do_unlink=True)
    cam = bpy.data.cameras.new('pano'); cam.type = 'PANO'
    try: cam.panorama_type = 'EQUIRECTANGULAR'
    except Exception: cam.cycles.panorama_type = 'EQUIRECTANGULAR'
    o = bpy.data.objects.new('pano', cam); scn.collection.objects.link(o)
    o.location = P(x, y, z); o.rotation_euler = (math.pi / 2, 0, math.radians(yaw) - math.pi / 2)
    scn.camera = o; vs.exposure = ev
    r.filepath = os.path.join(out, f'pano-{i}-{slug}.jpg')
    bpy.ops.render.render(write_still=True)
    print('DONE', i, slug, r.filepath, flush=True)
