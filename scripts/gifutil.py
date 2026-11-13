"""Shared by trapdemo.py and eggdemo.py: caption strip and GIF writer (Pillow only)."""
from PIL import Image, ImageDraw, ImageFont

SCALE = 2
STRIP = 40                      # caption strip height, below the 448x512 game picture
STEP = 4                        # emulator frames per GIF frame: 60 / 4 = 15 fps
FRAME_MS = 70                   # ~14 fps
HOLD_MS = 2000                  # last frame, before the loop restarts
BG, FG = (32, 32, 32), (255, 255, 255)
PALETTE = [0, 0, 0, 255, 255, 255, 32, 32, 32]


def _font(size=20):
    for name in ('DejaVuSansMono.ttf', 'DejaVuSans.ttf'):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def frame(board, text):
    """The game picture at 2x (nearest-neighbour) with a plain caption strip added underneath."""
    pic = board.image().resize((224 * SCALE, 256 * SCALE), Image.NEAREST)
    out = Image.new('RGB', (pic.width, pic.height + STRIP), BG)
    out.paste(pic, (0, 0))
    d = ImageDraw.Draw(out)
    d.fontmode = '1'
    size = 20
    f = _font(size)
    while d.textlength(text, font=f) > out.width - 16 and size > 8:     # long captions shrink to fit
        size -= 1
        f = _font(size)
    w = d.textlength(text, font=f)
    d.text(((out.width - w) / 2, pic.height + (STRIP - size) / 2 - 2), text, font=f, fill=FG)
    return out


def save(frames, path):
    """frames: RGB images. Four-colour palette, loops forever, last frame held for HOLD_MS."""
    pal = Image.new('P', (1, 1)); pal.putpalette(PALETTE + [0] * (768 - len(PALETTE)))
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=[FRAME_MS] * (len(q) - 1) + [HOLD_MS],
              loop=0, optimize=True, disposal=1)
