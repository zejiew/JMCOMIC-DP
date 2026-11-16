"""作者水印测试：确认界面角标与启动页水印都没丢。"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from jmfav import theme


def main():
    ok = True

    def check(label, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label + (f'  {extra}' if extra else ''))
        if not cond:
            ok = False

    # 1. 常量
    check('作者名', theme.AUTHOR == '星汐', theme.AUTHOR)
    check('作者 ID', theme.AUTHOR_ID == 'zejiew', theme.AUTHOR_ID)
    check('角标文案', theme.CREDIT == '构建 BY 星汐', theme.CREDIT)
    check('带 ID 文案', 'zejiew' in theme.CREDIT_LONG, theme.CREDIT_LONG)

    # 2. 横幅能画出来（宽窗口带 ID）
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    theme.apply_theme(root)
    theme.font_family()

    wide = theme.make_header_image(1300, 76)
    check('宽横幅生成', wide is not None and wide.width() == 1300)

    narrow = theme.make_header_image(600, 76)
    check('窄横幅生成', narrow is not None and narrow.width() >= 520)

    # 3. 角标绘制本身不崩（窄到 260 以下时应该静默跳过）
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (300, 76), (255, 240, 246))
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default()
    try:
        theme._draw_credit_badge(d, img, f, theme.CREDIT, 300, 76)
        check('超窄时不崩', True)
    except Exception as exc:
        check('超窄时不崩', False, str(exc))

    root.destroy()

    # 4. 启动图文件里确实有橙色水印像素
    splash = os.path.join(ROOT, 'splash.png')
    if os.path.exists(splash):
        from PIL import Image as I
        im = I.open(splash).convert('RGB')
        w, h = im.size
        # 右下角区域找橙色
        found = False
        for y in range(int(h * 0.7), h):
            for x in range(int(w * 0.5), w):
                r, g, b = im.getpixel((x, y))
                if r > 200 and 120 < g < 200 and b < 80:
                    found = True
                    break
            if found:
                break
        check('启动图右下角有橙色水印', found, f'{w}x{h}')
    else:
        check('启动图存在', False, 'splash.png 缺失')

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
