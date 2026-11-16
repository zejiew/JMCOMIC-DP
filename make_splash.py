"""生成启动画面 splash.png（用 assets/logo_src.jpg 那张 DP/JMCOMIC 图）。

深色底 + 圆角 logo + 标题 + 作者水印，和 logo 本身的黑橙配色统一。
PyInstaller 的 --splash 会在解压 exe 的那几秒里显示它。
"""

import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, 'assets', 'logo_src.jpg')
OUT = os.path.join(ROOT, 'splash.png')

W, H = 560, 300
BG = (22, 22, 22)
ORANGE = (242, 162, 27)
WHITE = (255, 255, 255)
GRAY = (150, 150, 150)

# 作者信息（与 jmfav/theme.py 保持一致）
AUTHOR = '星汐'
AUTHOR_ID = 'zejiew'
CREDIT = f'构建 BY {AUTHOR}'


def load_font(size, bold=False):
    cands = []
    if bold:
        cands += [r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\segoeuib.ttf']
    cands += [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\segoeui.ttf']
    for path in cands:
        if os.path.exists(path):
            try:
                idx = 1 if path.endswith('bd.ttc') else 0
                return ImageFont.truetype(path, size, index=idx)
            except Exception:
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue
    return ImageFont.load_default()


def rounded_logo(src, size, radius_ratio=0.18):
    side = min(src.size)
    left = (src.size[0] - side) // 2
    top = (src.size[1] - side) // 2
    img = src.crop((left, top, left + side, top + side)).resize(
        (size, size), Image.LANCZOS).convert('RGBA')

    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size - 1, size - 1), radius=int(size * radius_ratio), fill=255)
    img.putalpha(mask)
    return img


def draw_watermark(canvas, d):
    """右下角作者水印：橙色胶囊 + 深色字，和 logo 配色呼应。"""
    f_credit = load_font(13, bold=True)
    f_id = load_font(11)

    text = CREDIT
    bbox = d.textbbox((0, 0), text, font=f_credit)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    idtext = f'@{AUTHOR_ID}'
    bbox2 = d.textbbox((0, 0), idtext, font=f_id)
    tw2 = bbox2[2] - bbox2[0]

    pad_x, pad_y, gap = 11, 6, 8
    badge_w = pad_x * 2 + tw + gap + tw2
    badge_h = pad_y * 2 + max(th, bbox2[3] - bbox2[1])

    margin = 14
    right = W - margin
    bottom = H - margin - 12      # 让开底部标语一行
    left = right - badge_w
    top = bottom - badge_h

    overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((left, top, right, bottom),
                         radius=badge_h // 2, fill=(ORANGE[0], ORANGE[1], ORANGE[2], 235))

    ty = top + pad_y - bbox[1]
    od.text((left + pad_x, ty), text, font=f_credit, fill=(30, 26, 18, 255))
    od.text((left + pad_x + tw + gap, ty + 1), idtext, font=f_id,
            fill=(60, 48, 30, 255))

    merged = Image.alpha_composite(canvas.convert('RGBA'), overlay)
    canvas.paste(merged.convert('RGB'), (0, 0))


def main():
    if not os.path.exists(SRC):
        print('缺少', SRC)
        return 1

    canvas = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(canvas)

    # 顶部一条橙色细线，呼应 logo 的橙
    d.rectangle((0, 0, W, 4), fill=ORANGE)

    src = Image.open(SRC).convert('RGB')
    logo_size = 190
    logo = rounded_logo(src, logo_size)
    logo_x, logo_y = 30, 44
    canvas.paste(logo, (logo_x, logo_y), logo)

    # 文字
    f_title = load_font(36, bold=True)
    f_sub = load_font(15)
    text_x = logo_x + logo_size + 28
    d.text((text_x, 88), 'JM 下载器', font=f_title, fill=WHITE)
    d.text((text_x, 140), '正在启动，请稍候…', font=f_sub, fill=GRAY)

    # 作者水印（右下角）
    draw_watermark(canvas, ImageDraw.Draw(canvas))

    # 左下角小字
    f_tiny = load_font(11)
    d.text((16, H - 16), 'for JMCOMIC', font=f_tiny, fill=(90, 90, 90), anchor='ls')

    canvas.save(OUT, format='PNG')
    print(f'已生成 {OUT}  {os.path.getsize(OUT)} bytes  {W}x{H}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
