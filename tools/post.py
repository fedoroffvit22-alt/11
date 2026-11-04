import sys, glob, os, random
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ImageEnhance
import numpy as np
src = sys.argv[1]; dst = sys.argv[2]; os.makedirs(dst, exist_ok=True)
FONT = '/usr/share/fonts/opentype/inter/Inter-Medium.otf'
NAMES = {1:'kuhnya-stolovaya',2:'kuhnya-rabochaya-zona',3:'kuhnya-stoleshnica',4:'spalnya-16',5:'spalnya-16-okna',6:'komnata-13',7:'komnata-13-rabochee-mesto',8:'prihozhaya',9:'sanuzel',10:'sanuzel-tumba-vanna'}
for f in sorted(glob.glob(os.path.join(src, 'raw_*.png'))):
    i = int(os.path.basename(f)[4:6])
    im = Image.open(f).convert('RGB')
    im = ImageEnhance.Contrast(im).enhance(1.04)
    im = ImageEnhance.Color(im).enhance(1.06)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    a = np.asarray(im).astype(np.float32)
    rng = np.random.default_rng(i)
    g = rng.normal(0, 2.2, a.shape[:2])[..., None]
    a = np.clip(a + g, 0, 255).astype(np.uint8)
    im = Image.fromarray(a)
    out = os.path.join(dst, f'{i:02d}-{NAMES[i]}.jpg')
    im.save(out, 'JPEG', quality=92, subsampling=0, optimize=True)
    print(out)
