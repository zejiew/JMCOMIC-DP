"""二次元风格的配色、字体与素材加载。

整体走「樱粉 + 天空蓝 + 淡紫」的轻甜路线：浅粉底、白卡片、粉色主按钮、
天蓝点缀，日志区用深紫做对比。改配色只改这一个文件。

素材：
- ``assets/icon_src.jpg`` 运行时图标（Q 版立绘），抠白底后做圆形头像
- ``assets/logo_src.jpg`` 启动 logo（DP / JMCOMIC），用于启动图与顶部 Logo
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import ttk

# --------------------------------------------------------------------------- #
# 配色
# --------------------------------------------------------------------------- #

PALETTE = {
    'bg': '#FFF6FA',            # 主背景：极浅樱粉
    'bg_deep': '#FFEDF4',       # 次级背景
    'card': '#FFFFFF',          # 卡片
    'card_alt': '#FFF3F8',      # 卡片内浅色块
    'pink': '#FF7FA8',          # 主粉
    'pink_dark': '#EE5D8C',     # 深粉（文字/强调）
    'pink_light': '#FFD3E3',    # 浅粉（边框 / hover）
    'pink_pale': '#FFE9F1',     # 更浅（未选中 tab）
    'blue': '#5FB8E8',          # 天空蓝
    'blue_light': '#CFEAFB',    # 浅蓝
    'lav': '#B49CF0',           # 淡紫
    'text': '#3E4356',          # 正文深灰蓝
    'text_soft': '#6E7488',     # 次要文字
    'text_muted': '#9AA0B4',    # 提示文字
    'border': '#F4D2E1',        # 常规描边
    'ok': '#3FB98D',            # 成功
    'warn': '#F0A63C',          # 警告
    'err': '#F2617A',           # 错误
    'log_bg': '#2E2A3B',        # 日志底色：深紫
    'log_fg': '#ECE7F5',        # 日志正文
    'log_time': '#9C8FC4',      # 日志时间戳
}

# 勾选符号（列表第一列）
CHECK_ON = '♥'
CHECK_OFF = '♡'

# 作者信息（界面角标与启动页水印都用这里，改一处就全跟着变）
AUTHOR = '星汐'
AUTHOR_ID = 'zejiew'
CREDIT = f'构建 BY {AUTHOR}'
CREDIT_LONG = f'构建 BY {AUTHOR} · @{AUTHOR_ID}'

# --------------------------------------------------------------------------- #
# 字体
# --------------------------------------------------------------------------- #

_FALLBACK = ('Microsoft YaHei UI', '微软雅黑', 'Segoe UI', 'TkDefaultFont')
_family = None


def font_family() -> str:
    """挑一个系统里真有的中文字体（缓存）。"""
    global _family
    if _family:
        return _family
    try:
        import tkinter.font as tkfont
        families = set(tkfont.families())
        for name in _FALLBACK:
            if name in families:
                _family = name
                return name
    except Exception:
        pass
    _family = 'TkDefaultFont'
    return _family


def f(size: int = 9, bold: bool = False):
    """造一个 tk 字体元组。"""
    return (font_family(), size, 'bold' if bold else 'normal')


# --------------------------------------------------------------------------- #
# 素材
# --------------------------------------------------------------------------- #

def assets_dir() -> str:
    """打包后素材在 _MEIPASS/assets，开发时在项目根/assets。"""
    base = getattr(sys, '_MEIPASS', None)
    if base:
        return os.path.join(base, 'assets')
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, 'assets')


def _source_image(name: str):
    from PIL import Image
    path = os.path.join(assets_dir(), name)
    if not os.path.exists(path):
        return None
    try:
        return Image.open(path).convert('RGB')
    except Exception:
        return None


def _white_to_alpha(img, low: int = 234, high: int = 252):
    """白底抠透明（保留备用）。

    注意：本项目的立绘背景有浅色点阵装饰，抠白会留下大量碎点，
    所以头像默认不走这条路，而是做成「白底圆盘」。
    """
    img = img.convert('RGBA')
    px = img.load()
    w, h = img.size
    span = max(1, high - low)
    for y in range(h):
        for x in range(w):
            r, g, b, _a = px[x, y]
            v = min(r, g, b)
            if v >= high:
                alpha = 0
            elif v <= low:
                alpha = 255
            else:
                alpha = int(255 * (high - v) / span)
            px[x, y] = (r, g, b, alpha)
    return img


def _circle_mask(size: int):
    from PIL import Image, ImageDraw
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    return mask


_avatar_pil_cache = {}


def avatar_pil(size: int):
    """圆形、透明底的 Q 版头像（PIL 图），带缓存。"""
    if size in _avatar_pil_cache:
        return _avatar_pil_cache[size]

    src = _source_image('icon_src.jpg')
    if src is None:
        return None

    from PIL import Image
    # 裁掉四周白边，让角色占满整个圆
    bbox = _content_bbox(src)
    if bbox:
        src = src.crop(bbox)

    # 放进正方形、补白，再裁圆 —— 用白底圆盘而不是抠图：
    # 原画背景本来就有浅色点阵，抠白会留一堆碎点，白盘更干净也更像贴纸。
    side = max(src.size)
    square = Image.new('RGB', (side, side), (255, 255, 255))
    square.paste(src, ((side - src.size[0]) // 2, (side - src.size[1]) // 2))
    square = square.resize((size, size), Image.LANCZOS).convert('RGBA')
    square.putalpha(_circle_mask(size))

    _avatar_pil_cache[size] = square
    return square


def _content_bbox(img, margin: int = 6):
    """找出非白区域的包围盒（用于裁边）。"""
    from PIL import Image
    gray = img.convert('L')
    # 反相：非白变亮
    inv = gray.point(lambda v: 255 if v < 245 else 0)
    bbox = inv.getbbox()
    if not bbox:
        return None
    left, top, right, bottom = bbox
    left = max(0, left - margin)
    top = max(0, top - margin)
    right = min(img.size[0], right + margin)
    bottom = min(img.size[1], bottom + margin)
    if right - left < 16 or bottom - top < 16:
        return None
    return (left, top, right, bottom)


_photo_cache = {}


def avatar_photo(size: int):
    """给 tk 用的头像 PhotoImage（调用方需保持引用）。"""
    key = ('avatar', size)
    if key in _photo_cache:
        return _photo_cache[key]
    pil = avatar_pil(size)
    if pil is None:
        return None
    try:
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(pil)
    except Exception:
        return None
    _photo_cache[key] = photo
    return photo


def logo_photo(height: int):
    """启动 logo 的圆角贴纸版（tk 用）。"""
    key = ('logo', height)
    if key in _photo_cache:
        return _photo_cache[key]

    src = _source_image('logo_src.jpg')
    if src is None:
        return None

    from PIL import Image, ImageDraw
    w, h = src.size
    side = min(w, h)
    src = src.crop(((w - side) // 2, (h - side) // 2,
                    (w + side) // 2, (h + side) // 2))
    src = src.resize((height, height), Image.LANCZOS).convert('RGBA')

    radius = max(4, height // 5)
    mask = Image.new('L', (height, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, height - 1, height - 1),
                                           radius=radius, fill=255)
    src.putalpha(mask)

    try:
        from PIL import ImageTk
        photo = ImageTk.PhotoImage(src)
    except Exception:
        return None
    _photo_cache[key] = photo
    return photo


def _font_file(bold: bool) -> str:
    for path in (r'C:\Windows\Fonts\msyhbd.ttc' if bold
                 else r'C:\Windows\Fonts\msyh.ttc',
                 r'C:\Windows\Fonts\msyh.ttc',
                 r'C:\Windows\Fonts\simhei.ttf',
                 r'C:\Windows\Fonts\segoeui.ttf'):
        if os.path.exists(path):
            return path
    return ''


def make_header_image(width: int, height: int,
                      title: str = 'JM 下载器',
                      subtitle: str = '禁漫收藏 · 一键打包下载',
                      credit: str = CREDIT):
    """顶部横幅：粉→紫→蓝渐变 + 圆形头像 + 标题 + 右下角作者角标。

    ``credit`` 画在横幅右下角（截图里用户指的那个位置）。
    """
    from PIL import Image, ImageDraw, ImageFont, ImageTk

    width = max(520, int(width))
    height = max(60, int(height))

    # 渐变
    stops = [(0.0, (255, 228, 239)), (0.46, (244, 232, 255)), (1.0, (214, 238, 252))]
    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    for x in range(width):
        t = x / max(1, width - 1)
        for i in range(len(stops) - 1):
            a_pos, a_col = stops[i]
            b_pos, b_col = stops[i + 1]
            if a_pos <= t <= b_pos:
                k = 0 if b_pos == a_pos else (t - a_pos) / (b_pos - a_pos)
                draw.line([(x, 0), (x, height)],
                          fill=tuple(int(a_col[j] + (b_col[j] - a_col[j]) * k)
                                     for j in range(3)))
                break

    # 右上角小圆点装饰
    for cx, cy, r in ((width - 118, 15, 5), (width - 92, 33, 3),
                      (width - 148, 45, 4), (width - 58, 21, 3),
                      (width - 176, 20, 2)):
        if cx > 300:
            draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255))

    # 头像贴上去
    avatar_size = height - 14
    pil = avatar_pil(avatar_size)
    ax, ay = 10, (height - avatar_size) // 2
    if pil is not None:
        canvas = img.convert('RGBA')
        # 白色半透明圆底，让头像在白底上有"贴纸"感
        halo = Image.new('RGBA', (avatar_size + 10, avatar_size + 10), (0, 0, 0, 0))
        ImageDraw.Draw(halo).ellipse((0, 0, avatar_size + 9, avatar_size + 9),
                                     fill=(255, 255, 255, 210))
        canvas.alpha_composite(halo, (ax - 5, ay - 5))
        canvas.alpha_composite(pil, (ax, ay))
        img = canvas.convert('RGB')

    draw = ImageDraw.Draw(img)

    # 文字
    f_title_path = _font_file(True)
    f_sub_path = _font_file(False)
    title_size = max(13, int(height * 0.29))
    sub_size = max(9, int(height * 0.165))
    credit_size = max(9, int(height * 0.155))
    try:
        f_title = ImageFont.truetype(f_title_path, title_size) if f_title_path else None
        f_sub = ImageFont.truetype(f_sub_path, sub_size) if f_sub_path else None
        f_credit = (ImageFont.truetype(f_sub_path, credit_size)
                    if f_sub_path else None)
    except Exception:
        f_title = f_sub = f_credit = None

    text_x = (ax + avatar_size + 14) if pil is not None else 16
    if f_title is not None:
        draw.text((text_x, height // 2 - int(height * 0.26)), title,
                  font=f_title, fill=(62, 67, 86))
    if f_sub is not None:
        draw.text((text_x, height // 2 + int(height * 0.06)), subtitle,
                  font=f_sub, fill=(126, 132, 152))

    # 右下角作者角标：淡粉胶囊 + 深粉字，不抢主体但看得见
    if credit and f_credit is not None:
        # 窗口够宽就带上 @zejiew，窄了就只留「构建 BY 星汐」
        text = credit
        if width >= 900:
            text = CREDIT_LONG
        _draw_credit_badge(draw, img, f_credit, text, width, height)

    return ImageTk.PhotoImage(img)


def _draw_credit_badge(draw, img, font, text: str, width: int, height: int):
    """在横幅右下角画一个半透明胶囊角标。"""
    from PIL import Image, ImageDraw

    try:
        bbox = draw.textbbox((0, 0), text, font=font)
    except Exception:
        return
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 10, 4
    badge_w, badge_h = tw + pad_x * 2, th + pad_y * 2

    margin = 12
    right = width - margin
    bottom = height - margin
    left = right - badge_w
    top = bottom - badge_h
    if left < 260:      # 窗口太窄就不画，免得压住标题
        return

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((left, top, right, bottom),
                         radius=badge_h // 2, fill=(255, 255, 255, 170),
                         outline=(255, 211, 227, 220), width=1)
    od.text((left + pad_x - bbox[0], top + pad_y - bbox[1]), text,
            font=font, fill=(214, 84, 128, 255))

    merged = Image.alpha_composite(img.convert('RGBA'), overlay)
    img.paste(merged.convert('RGB'), (0, 0))


# --------------------------------------------------------------------------- #
# 自绘勾选框（clam 默认那个黑底 X 太扎眼）
# --------------------------------------------------------------------------- #

_indicator_keep = {}


def _heart_points(cx: float, cy: float, scale: float):
    """用两个圆+一个三角拼一个爱心（16px 下也认得出来）。"""
    r = 3.1 * scale
    left_c = (cx - 2.9 * scale, cy - 1.6 * scale)
    right_c = (cx + 2.9 * scale, cy - 1.6 * scale)
    tip = (cx, cy + 6.0 * scale)
    return r, left_c, right_c, tip


def _draw_heart(draw, cx, cy, scale, color):
    r, (lx, ly), (rx, ry), (tx, ty) = _heart_points(cx, cy, scale)
    draw.ellipse((lx - r, ly - r, lx + r, ly + r), fill=color)
    draw.ellipse((rx - r, ry - r, rx + r, ry + r), fill=color)
    draw.polygon([(lx - r + 0.4, ly + 0.4), (rx + r - 0.4, ry + 0.4), (tx, ty)],
                 fill=color)


def _make_indicator(checked: bool, size: int = 17, disabled: bool = False):
    """生成一张勾选框小图（PhotoImage）。"""
    from PIL import Image, ImageDraw, ImageTk

    scale = 3
    px = size * scale
    img = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    radius = int(px * 0.30)
    if checked:
        fill = (243, 168, 196, 255) if disabled else (255, 127, 168, 255)
        outline = fill
    else:
        fill = (255, 248, 251, 255) if not disabled else (250, 245, 248, 255)
        outline = (244, 210, 225, 255) if not disabled else (238, 232, 236, 255)

    d.rounded_rectangle((1, 1, px - 2, px - 2), radius=radius,
                        fill=fill, outline=outline, width=max(1, scale))

    if checked:
        _draw_heart(d, px / 2, px / 2 - 0.5 * scale, scale * 0.92,
                    (255, 255, 255, 255))

    img = img.resize((size, size), Image.LANCZOS)
    return ImageTk.PhotoImage(img)


def _ensure_indicator(style: ttk.Style, root) -> None:
    """把自绘勾选框接进 ttk 的 Checkbutton 布局。"""
    if _indicator_keep:
        return

    try:
        off = _make_indicator(False)
        on = _make_indicator(True)
        off_dis = _make_indicator(False, disabled=True)
        on_dis = _make_indicator(True, disabled=True)
    except Exception:
        return

    _indicator_keep.update({'off': off, 'on': on,
                            'off_dis': off_dis, 'on_dis': on_dis})
    try:
        style.element_create(
            'Cute.check', 'image',
            off, ('selected', on), ('disabled', off_dis),
            ('selected', 'disabled', on_dis),
            border=1, sticky='w',
        )
        style.layout('Cute.TCheckbutton', [
            ('Checkbutton.padding', {'sticky': 'nswe', 'children': [
                ('Cute.check', {'side': 'left', 'sticky': ''}),
                ('Checkbutton.focus', {'side': 'left', 'sticky': 'w', 'children': [
                    ('Checkbutton.label', {'sticky': 'nswe'}),
                ]}),
            ]}),
        ])
    except tk.TclError:
        pass


# --------------------------------------------------------------------------- #
# 自绘圆角按钮（ttk 原生是方角，用 9-patch 贴图做圆角）
# --------------------------------------------------------------------------- #

_button_keep = {}


def _rounded_patch(fill, size=40, radius=11, outline=None, outline_w=1):
    """生成一张圆角矩形贴图，交给 ttk 用 border 做成 9-patch。"""
    from PIL import Image, ImageDraw, ImageTk

    scale = 4
    px = size * scale
    img = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (0, 0, px - 1, px - 1),
        radius=radius * scale,
        fill=fill,
        outline=outline,
        width=max(1, outline_w * scale) if outline else 0,
    )
    img = img.resize((size, size), Image.LANCZOS)
    return ImageTk.PhotoImage(img)


def _ensure_rounded_buttons(style: ttk.Style) -> None:
    """给三种按钮做圆角版本；任何一步失败就保留纯色方案。"""
    if _button_keep:
        return

    P = PALETTE
    specs = {
        'Accent': {
            'normal': (255, 127, 168, 255),
            'active': (238, 93, 140, 255),
            'pressed': (224, 74, 122, 255),
            'disabled': (255, 211, 227, 255),
        },
        'Soft': {
            'normal': (255, 233, 241, 255),
            'active': (255, 211, 227, 255),
            'pressed': (255, 196, 216, 255),
            'disabled': (253, 246, 249, 255),
        },
        'Stop': {
            'normal': (255, 255, 255, 255),
            'active': (255, 237, 240, 255),
            'pressed': (255, 224, 230, 255),
            'disabled': (251, 247, 249, 255),
        },
    }

    try:
        for key, colors in specs.items():
            imgs = {}
            for state, rgba in colors.items():
                outline = (255, 211, 227, 255) if key != 'Accent' else None
                imgs[state] = _rounded_patch(rgba, outline=outline)
            _button_keep[key] = imgs

            elem = f'Cute.{key}.button'
            style.element_create(
                elem, 'image',
                imgs['normal'],
                ('active', imgs['active']),
                ('pressed', imgs['pressed']),
                ('disabled', imgs['disabled']),
                border=12, sticky='nswe',
            )
            style.layout(f'{key}.TButton', [
                (elem, {'sticky': 'nswe', 'children': [
                    ('Button.padding', {'sticky': 'nswe', 'children': [
                        ('Button.label', {'sticky': 'nswe'}),
                    ]}),
                ]}),
            ])
    except tk.TclError:
        _button_keep.clear()

def _flat(widget_style: str, bg: str, fg: str, pad=(8, 4), border=(0, 0, 0, 0)):
    return {
        'background': bg, 'foreground': fg, 'padding': pad,
    }


def apply_theme(root: tk.Misc) -> ttk.Style:
    """把整套二次元样式刷上去。"""
    style = ttk.Style(root)
    for theme in ('clam', 'alt', 'default'):
        try:
            style.theme_use(theme)
            break
        except tk.TclError:
            continue

    P = PALETTE
    family = font_family()

    # ---- 基础 ----
    style.configure('.', background=P['bg'], foreground=P['text'],
                    font=(family, 9), borderwidth=0, focuscolor=P['pink'])
    style.configure('TFrame', background=P['bg'])
    style.configure('Card.TFrame', background=P['card'])
    style.configure('Soft.TFrame', background=P['bg'])

    style.configure('TLabel', background=P['bg'], foreground=P['text'],
                    font=(family, 9))
    style.configure('Card.TLabel', background=P['card'], foreground=P['text'])
    style.configure('Title.TLabel', background=P['card'], foreground=P['pink_dark'],
                    font=(family, 12, 'bold'))
    style.configure('Hint.TLabel', background=P['card'], foreground=P['text_muted'],
                    font=(family, 8))
    style.configure('HintBg.TLabel', background=P['bg'], foreground=P['text_muted'],
                    font=(family, 8))
    style.configure('Count.TLabel', background=P['bg'], foreground=P['pink_dark'],
                    font=(family, 9, 'bold'))

    # ---- 卡片（LabelFrame）----
    style.configure('TLabelframe', background=P['card'], bordercolor=P['border'],
                    lightcolor=P['card'], darkcolor=P['card'], borderwidth=1,
                    relief='solid')
    style.configure('TLabelframe.Label', background=P['card'],
                    foreground=P['pink_dark'], font=(family, 9, 'bold'))

    # ---- 按钮 ----
    style.configure('TButton', background=P['card'], foreground=P['text'],
                    bordercolor=P['pink_light'], lightcolor=P['card'],
                    darkcolor=P['pink_light'], borderwidth=1, relief='solid',
                    padding=(10, 5), font=(family, 9))
    style.map('TButton',
              background=[('active', P['pink_pale']), ('disabled', P['card'])],
              foreground=[('disabled', P['text_muted'])],
              bordercolor=[('active', P['pink'])],
              relief=[('pressed', 'solid'), ('active', 'solid')])

    # 主按钮：粉底白字
    style.configure('Accent.TButton', background=P['pink'], foreground='#FFFFFF',
                    bordercolor=P['pink'], lightcolor=P['pink'],
                    darkcolor=P['pink_dark'], borderwidth=1, relief='solid',
                    padding=(12, 8), font=(family, 10, 'bold'))
    style.map('Accent.TButton',
              background=[('active', P['pink_dark']), ('disabled', P['pink_light'])],
              foreground=[('disabled', '#FFF5F8')],
              bordercolor=[('active', P['pink_dark'])])

    # 次按钮：浅粉底
    style.configure('Soft.TButton', background=P['pink_pale'],
                    foreground=P['pink_dark'], bordercolor=P['pink_light'],
                    lightcolor=P['pink_pale'], darkcolor=P['pink_light'],
                    padding=(10, 5), font=(family, 9))
    style.map('Soft.TButton',
              background=[('active', P['pink_light']), ('disabled', P['card_alt'])],
              foreground=[('disabled', P['text_muted'])])

    # 危险/停止
    style.configure('Stop.TButton', background=P['card'], foreground=P['err'],
                    bordercolor=P['border'], lightcolor=P['card'],
                    darkcolor=P['border'], padding=(10, 6),
                    font=(family, 9))
    style.map('Stop.TButton',
              background=[('active', '#FFEDF0')],
              bordercolor=[('active', P['err'])])

    # 圆角化（失败就自动留在上面的纯色方案）
    _ensure_rounded_buttons(style)

    # ---- 输入框 ----
    for name in ('TEntry', 'TCombobox', 'TSpinbox'):
        style.configure(name, fieldbackground=P['card'], background=P['card'],
                        foreground=P['text'], bordercolor=P['border'],
                        lightcolor=P['border'], darkcolor=P['border'],
                        arrowcolor=P['pink_dark'], insertcolor=P['pink_dark'],
                        padding=(6, 4), borderwidth=1, relief='solid')
        style.map(name,
                  bordercolor=[('focus', P['pink'])],
                  lightcolor=[('focus', P['pink'])],
                  fieldbackground=[('readonly', P['card'])],
                  foreground=[('disabled', P['text_muted'])])

    style.map('TCombobox',
              selectbackground=[('readonly', P['card'])],
              selectforeground=[('readonly', P['text'])])

    # 下拉列表（Listbox 部分用 option 数据库）
    try:
        root.option_add('*TCombobox*Listbox.background', P['card'])
        root.option_add('*TCombobox*Listbox.foreground', P['text'])
        root.option_add('*TCombobox*Listbox.selectBackground', P['pink'])
        root.option_add('*TCombobox*Listbox.selectForeground', '#FFFFFF')
        root.option_add('*TCombobox*Listbox.font', (family, 9))
    except Exception:
        pass

    # ---- 复选框 ----
    _ensure_indicator(style, root)
    style.configure('TCheckbutton', background=P['card'], foreground=P['text'],
                    focuscolor=P['card'], padding=(2, 3), font=(family, 9))
    style.map('TCheckbutton',
              background=[('active', P['card'])],
              foreground=[('disabled', P['text_muted'])])

    if _indicator_keep:
        style.configure('Cute.TCheckbutton', background=P['card'],
                        foreground=P['text'], focuscolor=P['card'],
                        padding=(1, 3), font=(family, 9))
        style.map('Cute.TCheckbutton',
                  background=[('active', P['card'])],
                  foreground=[('disabled', P['text_muted'])])
        style.configure('Bg.Cute.TCheckbutton', background=P['bg'])
        style.map('Bg.Cute.TCheckbutton', background=[('active', P['bg'])])

    style.configure('Bg.TCheckbutton', background=P['bg'])
    style.map('Bg.TCheckbutton', background=[('active', P['bg'])])

    # ---- 树形列表 ----
    style.configure('Treeview', background=P['card'], fieldbackground=P['card'],
                    foreground=P['text'], bordercolor=P['border'],
                    lightcolor=P['border'], darkcolor=P['border'],
                    rowheight=28, borderwidth=1, relief='solid',
                    font=(family, 9))
    style.map('Treeview',
              background=[('selected', P['pink_light'])],
              foreground=[('selected', P['text'])])

    style.configure('Treeview.Heading', background=P['pink_pale'],
                    foreground=P['pink_dark'], relief='flat', borderwidth=1,
                    bordercolor=P['border'], padding=(6, 6),
                    font=(family, 9, 'bold'))
    style.map('Treeview.Heading',
              background=[('active', P['pink_light'])],
              relief=[('active', 'flat')])

    # ---- 标签页 ----
    style.configure('TNotebook', background=P['bg'], borderwidth=0,
                    tabmargins=(2, 6, 2, 0))
    style.configure('TNotebook.Tab', background=P['pink_pale'],
                    foreground=P['text_soft'], padding=(20, 8),
                    font=(family, 9, 'bold'), borderwidth=0)
    style.map('TNotebook.Tab',
              background=[('selected', P['pink']),
                          ('active', P['pink_light'])],
              foreground=[('selected', '#FFFFFF'),
                          ('active', P['pink_dark'])],
              expand=[('selected', (0, 0, 0, 0))])

    # ---- 进度条 ----
    style.configure('Cute.Horizontal.TProgressbar',
                    troughcolor=P['pink_pale'], background=P['pink'],
                    bordercolor=P['pink_pale'], lightcolor=P['pink'],
                    darkcolor=P['pink'], thickness=14, borderwidth=0)
    style.configure('Horizontal.TProgressbar',
                    troughcolor=P['pink_pale'], background=P['pink'],
                    bordercolor=P['pink_pale'], lightcolor=P['pink'],
                    darkcolor=P['pink'], thickness=12, borderwidth=0)

    # ---- 滚动条 ----
    for orient in ('Vertical', 'Horizontal'):
        style.configure(f'{orient}.TScrollbar', background=P['pink_light'],
                        troughcolor=P['bg_deep'], bordercolor=P['bg_deep'],
                        arrowcolor=P['pink_dark'], lightcolor=P['pink_light'],
                        darkcolor=P['pink_light'], borderwidth=0, width=12,
                        arrowsize=12)
        style.map(f'{orient}.TScrollbar',
                  background=[('active', P['pink'])],
                  arrowcolor=[('active', '#FFFFFF')])

    # ---- 分隔线 ----
    style.configure('TSeparator', background=P['border'])

    return style
