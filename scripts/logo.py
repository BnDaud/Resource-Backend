"""Cut the logo out of its black background and export transparent PNG sizes.

    python -m scripts.logo <source.jpg> <output_dir>
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

src, out_dir = sys.argv[1], sys.argv[2].rstrip("/") + "/"
im = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
h, w, _ = im.shape
mx = im.max(axis=2)
gold = ((im[..., 0] - im[..., 2]) > 40) & (mx > 60)

# The dark lower half of the badge is part of the design: find it as the non-gold
# region enclosed by the gold outline and keep it fully opaque.
nongold = ~ndi.binary_dilation(gold, iterations=1)
lab, _ = ndi.label(nongold)
seed = lab[int(h * 0.86), int(w * 0.5)]
lower = (lab == seed) if seed else np.zeros((h, w), bool)

# Black-matte extraction: brightness above the black floor is coverage.
alpha = np.clip((mx - 14.0) / 70.0, 0, 1)
alpha = ndi.gaussian_filter(alpha, 0.6)
alpha[lower] = 1.0
# Drop the soft lens-flare glow that sits away from the gold shapes (looks like smudges on light backgrounds).
near_gold = ndi.binary_dilation(gold, iterations=4)
alpha[~near_gold & ~lower] = 0.0
a3 = np.maximum(alpha, 1e-3)[..., None]
col = np.where(lower[..., None], im, np.clip(im / a3, 0, 255))  # un-premultiply: no dark fringe
out = Image.fromarray(np.dstack([col, alpha * 255]).astype(np.uint8), "RGBA")

bb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
pad = 16
out = out.crop((max(bb[0] - pad, 0), max(bb[1] - pad, 0), min(bb[2] + pad, w), min(bb[3] + pad, h)))
side = max(out.size)
sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
sq.paste(out, ((side - out.width) // 2, (side - out.height) // 2))

sq.save(out_dir + "logo.png")
for n in (512, 192, 64, 32):
    sq.resize((n, n), Image.LANCZOS).save(out_dir + f"logo-{n}.png")
sq.resize((48, 48), Image.LANCZOS).save(out_dir + "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
for name, bg in (("light", (245, 243, 238)), ("navy", (27, 45, 68))):
    p = Image.new("RGBA", (700, 360), bg + (255,))
    big = sq.resize((300, 300), Image.LANCZOS)
    small = sq.resize((64, 64), Image.LANCZOS)
    p.paste(big, (50, 30), big)
    p.paste(small, (450, 150), small)
    p.convert("RGB").save(out_dir + f"_preview_{name}.png")
print(sq.size, "enclosed dark region px:", int(lower.sum()))
