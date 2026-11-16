"""生成程序图标 icon.ico（用 assets/icon_src.jpg 那张 Q 版立绘）。

做成一枚「白底圆盘 + 粉色细环 + 透明外圈」的贴纸，小尺寸下也认得出来。
Windows 需要多尺寸，一次全写进 ico。
"""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'assets', 'icon_src.jpg')
OUT = os.path.join(ROOT, 'icon.ico')

SIZES = [256, 128, 96, 64, 48, 32, 24, 16]


def content_bbox(img, margin: int = 8):
    """找出非白区域，把立绘四周的白边裁掉。"""
    gray = img.convert('L')
    inv = gray.point(lambda v: 255 if v < 245 else 0)
    bbox = inv.getbbox()
    if not bbox:
        return None
    left, top, right, bottom = bbox
    return (max(0, left - margin), max(0, top - margin),
            min(img.size[0], right + margin), min(img.size[1], bottom + margin))


def render_master() -> Image.Image:
    """先渲一张 1024 的主图，再降采样，边缘更干净。"""
    base = 1024
    src = Image.open(SRC).convert('RGB')
    box = content_bbox(src)
    if box:
        src = src.crop(box)

    # 放进正方形并补白
    side = max(src.size)
    square = Image.new('RGB', (side, side), (255, 255, 255))
    square.paste(src, ((side - src.size[0]) // 2, (side - src.size[1]) // 2))
    square = square.resize((base, base), Image.LANCZOS).convert('RGBA')

    # 圆形遮罩（稍微内缩，给外圈留位置）
    inset = int(base * 0.055)
    disc_size = base - inset * 2
    mask = Image.new('L', (base, base), 0)
    ImageDraw.Draw(mask).ellipse((inset, inset, inset + disc_size, inset + disc_size),
                                 fill=255)
    out = Image.new('RGBA', (base, base), (0, 0, 0, 0))
    out.paste(square, (0, 0), mask)

    # 粉色细环
    ring = Image.new('RGBA', (base, base), (0, 0, 0, 0))
    rw = max(2, int(base * 0.022))
    ImageDraw.Draw(ring).ellipse(
        (inset - rw // 2, inset - rw // 2,
         inset + disc_size + rw // 2, inset + disc_size + rw // 2),
        outline=(255, 127, 168, 255), width=rw)
    out = Image.alpha_composite(out, ring)
    return out


def main():
    if not os.path.exists(SRC):
        print('缺少', SRC)
        return 1

    master = render_master()
    frames = [master.resize((s, s), Image.LANCZOS) for s in SIZES]
    frames[0].save(OUT, format='ICO', sizes=[(s, s) for s in SIZES])
    print(f'已生成 {OUT}  {os.path.getsize(OUT)} bytes  {SIZES}')

    # 顺手存一张 png 预览
    master.resize((256, 256), Image.LANCZOS).save(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'tests', '_icon_preview.png'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
