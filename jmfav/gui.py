"""JM 下载器 —— 图形界面。

三个数据来源各占一个标签页：
    收藏夹  按收藏夹翻页载入
    搜索    站内搜索，可按相关度/最新/最热排序，支持翻页
    车号    粘贴车号或链接（支持一次贴一批）

三个页共用同一套「勾选 → 开始下载」逻辑，下载的永远是**当前标签页**里勾中的条目。
列表里除了原始标题，还会显示一列「命名预览」——那就是它落盘时会用的文件名，
不满意可以直接换命名模式。

结构：
- 后台线程负责网络与下载，UI 只通过 queue 收消息，绝不阻塞界面。
- 左列是标签页与日志，右列是下载设置与操作。
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Dict, List, Optional, Tuple

from . import __version__
from .engine import AlbumStub, Cancelled, FolderInfo, JmEngine, friendly_error
from .ids import looks_like_id, parse_album_ids, try_parse_album_id
from .naming import author_tagged, build_archive_name, truncate_title
from .paths import CONFIG_PATH, DEFAULT_OUTPUT, app_dir
from .theme import (AUTHOR, AUTHOR_ID, CHECK_OFF, CHECK_ON, CREDIT, PALETTE,
                    apply_theme, avatar_photo, f as theme_font, font_family,
                    make_header_image)
from .title import clean_title

APP_TITLE = 'JM 下载器'
THEME_BG = PALETTE['bg']

# 搜索排序
ORDER_CHOICES = [
    ('最新', 'mr'),
    ('最热', 'mv'),
    ('最多图', 'mp'),
    ('最多喜欢', 'tf'),
]
# 分类
CATEGORY_CHOICES = [
    ('全部', '0'),
    ('同人', 'doujin'),
    ('单本', 'single'),
    ('短篇', 'short'),
    ('韩漫', 'hanman'),
    ('美漫', 'meiman'),
    ('其他', 'another'),
]
# 命名模式
NAME_MODE_CHOICES = [
    ('智能提取作品名', 'smart'),
    ('完整原标题', 'full'),
]


def enable_dpi_awareness() -> None:
    """让 Windows 别把界面拉伸成模糊的一片。"""
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class AlbumTab:
    """一个标签页里的「条目列表 + 勾选状态」。"""

    def __init__(self, frame: ttk.Frame, columns, widths, headings,
                 refresh_hook=None):
        self.frame = frame
        self.albums: List[AlbumStub] = []
        self.checked: Dict[str, bool] = {}
        self._refresh_hook = refresh_hook

        # height 只是"请求"的行数；外面 expand 后会自动撑满，设小一点让窗口能更矮
        self.tree = ttk.Treeview(frame, columns=columns, show='headings', height=9)
        for col, (text, width) in zip(columns, zip(headings, widths)):
            self.tree.heading(col, text=text)
            if col in ('check', 'id'):
                self.tree.column(col, width=width, anchor='center', stretch=False)
            else:
                self.tree.column(col, width=width, anchor='w')

        vsb = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

    def refresh(self) -> None:
        if self._refresh_hook is not None:
            self._refresh_hook()

    def set_albums(self, items: List[AlbumStub], check_all: bool = True) -> None:
        self.albums = list(items)
        self.checked = {a.album_id: check_all for a in self.albums}
        self.refresh()

    def add_albums(self, items: List[AlbumStub], check_all: bool = True) -> None:
        """追加（去重），已有条目保持原勾选状态。"""
        have = {a.album_id for a in self.albums}
        for item in items:
            if item.album_id in have:
                continue
            self.albums.append(item)
            self.checked[item.album_id] = check_all
        self.refresh()

    def picked(self) -> List[AlbumStub]:
        return [a for a in self.albums if self.checked.get(a.album_id)]

    def count_text(self, shown: Optional[int] = None, keyword: str = '') -> str:
        picked = sum(1 for v in self.checked.values() if v)
        text = f'共 {len(self.albums)} 个 · 已选 {picked}'
        if keyword:
            text += f' · 匹配 {shown or 0}'
        return text

    def title_of(self, album_id: str) -> str:
        for album in self.albums:
            if album.album_id == album_id:
                return album.title
        return album_id


class JmApp(tk.Tk):

    def __init__(self):
        enable_dpi_awareness()
        super().__init__()
        self.title(APP_TITLE)
        self._apply_geometry()
        self.configure(bg=THEME_BG)
        self._set_window_icon()

        self.engine = JmEngine(log=self._log_from_thread)
        self.msg_queue: 'queue.Queue[tuple]' = queue.Queue()

        self.folders: List[FolderInfo] = []
        self.worker: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()
        self._busy = False
        self._last_output_dir = ''
        self._search_page = 1
        self._search_pages = 1
        self._searching = False       # 一次搜索还在路上时，挡住重复点击

        self.cfg = self._load_config()
        self._build_vars()
        self._build_ui()
        self._apply_config()
        self._apply_minsize()

        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.after(120, self._drain_queue)

        self._log('欢迎使用。先登录，再在「收藏夹 / 搜索 / 车号」任一页选好要下的条目。')
        self._log(f'{CREDIT}（@{AUTHOR_ID}）· v{__version__}')

    # ------------------------------------------------------------------ 兼容层
    # 老测试与外部脚本用的是 app.albums / app.checked / app.tree，这里代理到当前页

    @property
    def _active(self) -> AlbumTab:
        idx = getattr(self, 'notebook', None).index('current') if hasattr(self, 'notebook') else 0
        tabs = [self.tab_fav, self.tab_search, self.tab_id]
        return tabs[max(0, min(idx, len(tabs) - 1))]

    @property
    def tab_fav(self) -> AlbumTab:
        return self.tabs[0]

    @property
    def tab_search(self) -> AlbumTab:
        return self.tabs[1]

    @property
    def tab_id(self) -> AlbumTab:
        return self.tabs[2]

    @property
    def tree(self):
        return self._active.tree

    @property
    def albums(self) -> List[AlbumStub]:
        return self._active.albums

    @albums.setter
    def albums(self, value: List[AlbumStub]) -> None:
        self._active.albums = list(value)

    @property
    def checked(self) -> Dict[str, bool]:
        return self._active.checked

    @checked.setter
    def checked(self, value: Dict[str, bool]) -> None:
        self._active.checked = dict(value)

    # ------------------------------------------------------------------ 配置

    def _set_window_icon(self) -> None:
        """标题栏 / 任务栏图标（Q 版头像）。打包后图标在 _MEIPASS/assets。"""
        import sys
        for name in ('icon.ico',):
            for base in (getattr(sys, '_MEIPASS', None), app_dir()):
                if not base:
                    continue
                path = os.path.join(base, name)
                if os.path.exists(path):
                    try:
                        self.iconbitmap(default=path)
                        return
                    except tk.TclError:
                        pass

    def _apply_geometry(self) -> None:
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
        except tk.TclError:
            sw, sh = 1366, 768
        width = min(1300, max(1020, int(sw * 0.76)))
        height = min(1010, max(680, int(sh * 0.92)))
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2 - 20)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def _apply_minsize(self) -> None:
        """按实际布局需求设最小尺寸，并且绝不大于屏幕可用区域。"""
        self.update_idletasks()
        req_w = max(self.winfo_reqwidth(), 960)
        req_h = max(self.winfo_reqheight(), 620)

        avail_w = max(960, self.winfo_screenwidth() - 80)
        avail_h = max(620, self.winfo_screenheight() - 120)
        w, h = min(req_w, avail_w), min(req_h, avail_h)
        self.minsize(w, h)

        # 只把不够的那一边补上：以前两边一起写死，窗口反而会被压窄
        cur_w, cur_h = self.winfo_width(), self.winfo_height()
        new_w, new_h = max(cur_w, w), max(cur_h, h)
        if (new_w, new_h) != (cur_w, cur_h):
            x = max(0, (self.winfo_screenwidth() - new_w) // 2)
            y = max(0, (self.winfo_screenheight() - new_h) // 2 - 20)
            self.geometry(f'{new_w}x{new_h}+{x}+{y}')

    def _load_config(self) -> dict:
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {}

    def _save_config(self) -> None:
        data = {
            'username': self.var_user.get().strip(),
            'output': self.var_output.get().strip(),
            'max_chars': self._int(self.var_max_chars.get(), 60),
            'template': self.var_template.get().strip() or '{title}',
            'threads': self._int(self.var_threads.get(), 8),
            'compress': self._int(self.var_compress.get(), 0),
            'skip': bool(self.var_skip.get()),
            'order_by_name': bool(self.var_order.get()),
            'image_format': self.var_format.get() or 'auto',
            'image_quality': self._int(self.var_quality.get(), 90),
            'name_mode': self._var_name_mode_value(),
            'proxy': self.var_proxy.get().strip(),
            'cookies': self.cfg.get('cookies') or {},
        }
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _apply_config(self) -> None:
        self.var_output.set(self.cfg.get('output') or DEFAULT_OUTPUT)
        self.var_user.set(self.cfg.get('username') or '')
        self.var_max_chars.set(str(self.cfg.get('max_chars', 60)))
        self.var_template.set(self.cfg.get('template') or '{title}')
        self.var_threads.set(str(self.cfg.get('threads', 8)))
        self.var_compress.set(str(self.cfg.get('compress', 0)))
        self.var_skip.set(bool(self.cfg.get('skip', True)))
        self.var_order.set(bool(self.cfg.get('order_by_name', False)))
        self.var_format.set(self.cfg.get('image_format') or 'auto')
        self.var_quality.set(str(self.cfg.get('image_quality', 90)))
        self.var_proxy.set(self.cfg.get('proxy') or '')

        mode = self.cfg.get('name_mode') or 'smart'
        label = next((lb for lb, v in NAME_MODE_CHOICES if v == mode),
                     NAME_MODE_CHOICES[0][0])
        self.var_name_mode.set(label)

        self.engine.image_format = self.var_format.get() or 'auto'
        self.engine.image_quality = self._int(self.var_quality.get(), 90)
        self.engine.proxy = self.var_proxy.get().strip()

        cookies = self.cfg.get('cookies') or {}
        if cookies:
            self._try_cookie_login(cookies)

    def _var_name_mode_value(self) -> str:
        label = self.var_name_mode.get()
        return next((v for lb, v in NAME_MODE_CHOICES if lb == label), 'smart')

    # ------------------------------------------------------------------ 变量

    def _build_vars(self) -> None:
        self.var_user = tk.StringVar()
        self.var_pass = tk.StringVar()
        self.var_output = tk.StringVar(value=DEFAULT_OUTPUT)
        self.var_max_chars = tk.StringVar(value='60')
        self.var_template = tk.StringVar(value='{title}')
        self.var_threads = tk.StringVar(value='8')
        self.var_compress = tk.StringVar(value='0')
        self.var_skip = tk.BooleanVar(value=True)
        self.var_order = tk.BooleanVar(value=False)
        self.var_format = tk.StringVar(value='auto')
        self.var_quality = tk.StringVar(value='90')
        self.var_name_mode = tk.StringVar(value=NAME_MODE_CHOICES[0][0])
        self.var_proxy = tk.StringVar(value='')
        self.var_filter = tk.StringVar()
        self.var_status = tk.StringVar(value='未登录')
        self.var_progress = tk.DoubleVar(value=0.0)
        self.var_progress_text = tk.StringVar(value='未开始')
        self.var_count = tk.StringVar(value='共 0 个 · 已选 0')

        self.var_search = tk.StringVar()
        self.var_search_order = tk.StringVar(value=ORDER_CHOICES[0][0])
        self.var_search_cat = tk.StringVar(value=CATEGORY_CHOICES[0][0])
        self.var_search_info = tk.StringVar(value='')
        self.var_id_input = tk.StringVar()

        self.var_filter.trace_add('write', lambda *_: self.refresh_list())
        self.var_name_mode.trace_add('write', lambda *_: self.refresh_list())

    # ------------------------------------------------------------------ 界面

    def _build_ui(self) -> None:
        apply_theme(self)

        outer = ttk.Frame(self, padding=0)
        outer.pack(fill='both', expand=True)

        self._build_header(outer)

        content = ttk.Frame(outer, padding=(12, 12, 12, 10))
        content.pack(fill='both', expand=True)

        self._build_account(content)

        # 操作条先占住底部：窗口再矮也不会把它挤掉
        self._build_actions(content)

        body = ttk.Frame(content)
        body.pack(fill='both', expand=True, pady=(8, 0))

        left = ttk.Frame(body)
        left.pack(side='left', fill='both', expand=True)
        right = ttk.Frame(body, width=304)
        right.pack(side='right', fill='both', padx=(10, 0))
        right.pack_propagate(False)

        self._build_tabs(left)
        self._build_log(left)

        # 右栏放进可滚动容器：窗口矮的时候（笔记本 768 高）也能翻到每项设置
        scroll_host = self._make_scroll_area(right)
        self._build_settings(scroll_host)

    def _make_scroll_area(self, parent) -> ttk.Frame:
        """竖排可滚动区域，返回真正放内容的 Frame。"""
        holder = ttk.Frame(parent)
        holder.pack(fill='both', expand=True)

        canvas = tk.Canvas(holder, bg=PALETTE['bg'], highlightthickness=0,
                           bd=0, takefocus=0, height=10, width=10)
        vsb = ttk.Scrollbar(holder, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        inner = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=inner, anchor='nw')

        def _sync_scrollbar():
            """内容装得下就把滚动条收起来，免得右边一直挂一条。"""
            try:
                need = inner.winfo_reqheight() > canvas.winfo_height() + 2
            except tk.TclError:
                return
            mapped = bool(vsb.winfo_ismapped())
            if need and not mapped:
                vsb.pack(side='right', fill='y')
            elif not need and mapped:
                vsb.pack_forget()

        def _on_inner(_e=None):
            canvas.configure(scrollregion=canvas.bbox('all'))
            _sync_scrollbar()

        def _on_canvas(event):
            canvas.itemconfigure(window, width=event.width)
            _sync_scrollbar()

        inner.bind('<Configure>', _on_inner)
        canvas.bind('<Configure>', _on_canvas)

        def _wheel(event):
            if inner.winfo_height() <= canvas.winfo_height():
                return
            delta = -1 if event.delta > 0 else 1
            canvas.yview_scroll(delta * 2, 'units')

        def _enter(_e):
            canvas.bind_all('<MouseWheel>', _wheel)

        def _leave(_e):
            canvas.unbind_all('<MouseWheel>')

        canvas.bind('<Enter>', _enter)
        canvas.bind('<Leave>', _leave)

        self._scroll_canvas = canvas
        return inner

    def _build_header(self, parent) -> None:
        """顶部渐变横幅：头像 + 标题 + 副标题（随窗口宽度重绘）。"""
        holder = ttk.Frame(parent, style='Soft.TFrame')
        holder.pack(fill='x')

        self.header = tk.Canvas(holder, height=76, highlightthickness=0,
                                bd=0, bg=PALETTE['bg_deep'])
        self.header.pack(fill='x')
        self._header_photo = None
        self._header_width = 0
        self._header_job = None
        self.header.bind('<Configure>', self._on_header_resize)

        # 首次先用一个默认宽度画上，避免闪一下空白
        self._paint_header(1100)

    def _on_header_resize(self, event) -> None:
        width = max(520, int(event.width))
        if abs(width - self._header_width) < 24:
            return
        if self._header_job is not None:
            try:
                self.after_cancel(self._header_job)
            except Exception:
                pass
        self._header_job = self.after(90, lambda: self._paint_header(width))

    def _paint_header(self, width: int) -> None:
        self._header_job = None
        width = max(520, int(width))
        try:
            photo = make_header_image(width, 76,
                                      title='JM 下载器',
                                      subtitle='禁漫收藏 · 一键打包下载')
        except Exception:
            return
        if photo is None:
            return
        self._header_photo = photo
        self._header_width = width
        try:
            self.header.delete('all')
            self.header.create_image(0, 0, anchor='nw', image=photo)
        except tk.TclError:
            pass

    def _build_account(self, parent) -> None:
        box = ttk.LabelFrame(parent, text=' 账号 ', padding=(10, 8))
        box.pack(fill='x')

        ttk.Label(box, text='用户名', style='Card.TLabel').grid(
            row=0, column=0, sticky='w')
        ttk.Entry(box, textvariable=self.var_user, width=20).grid(
            row=0, column=1, padx=(4, 14))
        ttk.Label(box, text='密码', style='Card.TLabel').grid(
            row=0, column=2, sticky='w')
        entry = ttk.Entry(box, textvariable=self.var_pass, width=20, show='●')
        entry.grid(row=0, column=3, padx=(4, 12))
        entry.bind('<Return>', lambda _e: self._do_login())

        self.btn_login = ttk.Button(box, text='登录', width=8,
                                    style='Accent.TButton', command=self._do_login)
        self.btn_login.grid(row=0, column=4, padx=(0, 4), pady=2)
        self.lbl_status = tk.Label(box, textvariable=self.var_status,
                                   bg=PALETTE['card'], fg=PALETTE['ok'],
                                   font=theme_font(9, True), anchor='w')
        self.lbl_status.grid(row=0, column=5, padx=(12, 0), sticky='w')

    # ---------------- 标签页 ----------------

    def _build_tabs(self, parent) -> None:
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill='both', expand=True, pady=(4, 0))

        self.tabs: List[AlbumTab] = []
        hook = self.refresh_list

        # 1) 收藏夹
        page_fav = ttk.Frame(self.notebook, padding=(10, 8, 10, 6))
        self.notebook.add(page_fav, text='收藏夹')
        self._build_fav_bar(page_fav)
        list_fav = ttk.Frame(page_fav)
        list_fav.pack(fill='both', expand=True, pady=(6, 4))
        self.tabs.append(self._make_tab(list_fav, hook))
        self._build_bulk_bar(page_fav)

        # 2) 搜索
        page_search = ttk.Frame(self.notebook, padding=(10, 8, 10, 6))
        self.notebook.add(page_search, text='搜索')
        self._build_search_bar(page_search)
        list_search = ttk.Frame(page_search)
        list_search.pack(fill='both', expand=True, pady=(6, 4))
        self.tabs.append(self._make_tab(list_search, hook))
        self._build_bulk_bar(page_search, show_pager=True)

        # 3) 车号
        page_id = ttk.Frame(self.notebook, padding=(10, 8, 10, 6))
        self.notebook.add(page_id, text='车号')
        self._build_id_bar(page_id)
        list_id = ttk.Frame(page_id)
        list_id.pack(fill='both', expand=True, pady=(6, 4))
        self.tabs.append(self._make_tab(list_id, hook))
        self._build_bulk_bar(page_id)

        self.notebook.bind('<<NotebookTabChanged>>', lambda _e: self._on_tab_changed())

    def _make_tab(self, frame: ttk.Frame, hook) -> AlbumTab:
        tab = AlbumTab(
            frame,
            columns=('check', 'save', 'title', 'id'),
            headings=('选', '命名预览', '原标题', '本子ID'),
            widths=(42, 240, 300, 82),
            refresh_hook=hook,
        )
        tab.tree.bind('<Button-1>', lambda e, t=tab: self._on_tree_click(t, e))
        tab.tree.bind('<space>', lambda _e, t=tab: self._toggle_selected(t))
        tab.tree.bind('<Double-1>', lambda e, t=tab: self._on_tree_double(t, e))
        tab.tree.bind('<Button-3>', lambda e, t=tab: self._on_tree_menu(t, e))
        tab.tree.bind('<Control-a>', lambda _e, t=tab: self._check_all(True, t))
        # 隔行浅粉底，长列表更好读
        tab.tree.tag_configure('stripe', background=PALETTE['card_alt'])
        return tab

    def _build_bulk_bar(self, parent, show_pager: bool = False) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill='x')

        ttk.Label(bar, textvariable=self.var_count, style='Count.TLabel').pack(
            side='left')

        ttk.Button(bar, text='全选', width=6, style='Soft.TButton',
                   command=lambda: self._check_all(True)).pack(side='right')
        ttk.Button(bar, text='全不选', width=7, style='Soft.TButton',
                   command=lambda: self._check_all(False)).pack(side='right', padx=4)
        ttk.Button(bar, text='反选', width=6, style='Soft.TButton',
                   command=self._invert_check).pack(side='right')

        if show_pager:
            ttk.Button(bar, text='下一页 ▸', width=10, style='Soft.TButton',
                       command=lambda: self._page_search(+1)).pack(side='right',
                                                                  padx=(8, 4))
            ttk.Label(bar, textvariable=self.var_search_info,
                      style='HintBg.TLabel').pack(side='right', padx=(0, 4))
            ttk.Button(bar, text='◂ 上一页', width=10, style='Soft.TButton',
                       command=lambda: self._page_search(-1)).pack(side='right')

    # ---------------- 收藏夹栏 ----------------

    def _build_fav_bar(self, parent) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill='x')

        ttk.Label(bar, text='收藏夹', style='HintBg.TLabel').pack(side='left')
        self.var_folder_label = tk.StringVar()
        self.cmb_folder = ttk.Combobox(bar, textvariable=self.var_folder_label,
                                       state='readonly', width=18)
        self.cmb_folder.pack(side='left', padx=(4, 8))
        self.cmb_folder.bind('<<ComboboxSelected>>', lambda _e: self._load_favorites())

        self.btn_load = ttk.Button(bar, text='载入收藏', style='Accent.TButton',
                                   command=self._load_favorites)
        self.btn_load.pack(side='left')
        ttk.Button(bar, text='刷新', width=6, style='Soft.TButton',
                   command=self._do_list_folders).pack(side='left', padx=4)

        ttk.Label(bar, text='筛选本页', style='HintBg.TLabel').pack(
            side='left', padx=(14, 2))
        ttk.Entry(bar, textvariable=self.var_filter, width=16).pack(side='left')

    # ---------------- 搜索栏 ----------------

    def _build_search_bar(self, parent) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill='x', pady=(8, 0))

        row1 = ttk.Frame(bar)
        row1.pack(fill='x')
        entry = ttk.Entry(row1, textvariable=self.var_search, width=32)
        entry.pack(side='left')
        entry.bind('<Return>', lambda _e: self._do_search(reset=True))

        ttk.Button(row1, text='搜索', width=8,
                   command=lambda: self._do_search(reset=True)).pack(side='left', padx=(6, 12))
        ttk.Label(row1, text='关键词填车号也能直达',
                  style='HintBg.TLabel').pack(side='left')

        row2 = ttk.Frame(bar)
        row2.pack(fill='x', pady=(5, 0))
        ttk.Label(row2, text='排序', style='HintBg.TLabel').pack(side='left')
        cmb_order = ttk.Combobox(row2, textvariable=self.var_search_order, width=9,
                                 state='readonly',
                                 values=[lb for lb, _ in ORDER_CHOICES])
        cmb_order.pack(side='left', padx=(4, 14))
        cmb_order.bind('<<ComboboxSelected>>',
                       lambda _e: self._do_search(reset=True))

        ttk.Label(row2, text='分类', style='HintBg.TLabel').pack(side='left')
        cmb_cat = ttk.Combobox(row2, textvariable=self.var_search_cat, width=8,
                               state='readonly',
                               values=[lb for lb, _ in CATEGORY_CHOICES])
        cmb_cat.pack(side='left', padx=(4, 0))
        cmb_cat.bind('<<ComboboxSelected>>', lambda _e: self._do_search(reset=True))

    # ---------------- 车号栏 ----------------

    def _build_id_bar(self, parent) -> None:
        bar = ttk.Frame(parent)
        bar.pack(fill='x')

        row1 = ttk.Frame(bar)
        row1.pack(fill='x')
        ttk.Label(row1, text='车号 / 链接', style='HintBg.TLabel').pack(side='left')

        entry = ttk.Entry(row1, textvariable=self.var_id_input, width=26)
        entry.pack(side='left', padx=(6, 6))
        entry.bind('<Return>', lambda _e: self._add_ids())

        ttk.Button(row1, text='添加', width=7, style='Accent.TButton',
                   command=self._add_ids).pack(side='left')
        ttk.Button(row1, text='清空', width=7, style='Soft.TButton',
                   command=self._clear_ids).pack(side='left', padx=4)

        row2 = ttk.Frame(bar)
        row2.pack(fill='x', pady=(5, 0))
        ttk.Button(row2, text='直接下载这个 ID', style='Soft.TButton',
                   command=self._download_typed_id).pack(side='left')
        ttk.Label(row2, text='支持 123456 / JM123456 / 网址；多个用逗号或空格隔开',
                  style='HintBg.TLabel').pack(side='left', padx=(10, 0))

    # ---------------- 日志 / 设置 / 进度 ----------------

    def _build_log(self, parent) -> None:
        box = ttk.LabelFrame(parent, text=' 日志 ', padding=1)
        box.pack(fill='x', pady=(8, 0))

        # 深紫底 + 淡紫时间戳，和浅色主体形成对比
        self.log_text = ScrolledText(
            box, height=4, wrap='word', state='disabled',
            font=(font_family(), 9),
            bg=PALETTE['log_bg'], fg=PALETTE['log_fg'],
            insertbackground=PALETTE['log_fg'],
            selectbackground=PALETTE['pink'], selectforeground='#FFFFFF',
            relief='flat', borderwidth=0, padx=10, pady=6,
        )
        self.log_text.pack(fill='both', expand=True)
        self.log_text.tag_configure('time', foreground=PALETTE['log_time'])
        self.log_text.tag_configure('ok', foreground='#8FE3B8')
        self.log_text.tag_configure('err', foreground='#FF9DB0')
        self.log_text.tag_configure('name', foreground='#FFD59E')

    def _build_settings(self, parent) -> None:
        box = ttk.LabelFrame(parent, text=' 下载设置 ', padding=(10, 8))
        box.pack(fill='x')

        def lab(master, text, hint=False):
            return ttk.Label(master, text=text,
                             style='Hint.TLabel' if hint else 'Card.TLabel')

        lab(box, '输出目录').pack(anchor='w')
        ttk.Entry(box, textvariable=self.var_output).pack(fill='x', pady=(2, 3))
        ttk.Button(box, text='选择输出目录…', style='Soft.TButton',
                   command=self._pick_output).pack(fill='x', pady=(0, 7))

        lab(box, '命名方式').pack(anchor='w')
        self.cmb_name_mode = ttk.Combobox(
            box, textvariable=self.var_name_mode, state='readonly',
            values=[lb for lb, _ in NAME_MODE_CHOICES])
        self.cmb_name_mode.pack(fill='x', pady=(2, 1))

        row = ttk.Frame(box)
        row.pack(fill='x', pady=(0, 7))
        lab(row, '字数上限').pack(side='left')
        ttk.Spinbox(row, textvariable=self.var_max_chars, from_=0, to=200,
                    width=5).pack(side='left', padx=(6, 4))
        lab(row, '0 = 不限', hint=True).pack(side='left')

        lab(box, '命名模板').pack(anchor='w')
        ttk.Entry(box, textvariable=self.var_template).pack(fill='x', pady=(2, 1))
        lab(box, '{title} {id} {author} {date}（默认 {title} 已自动带作者）',
            hint=True).pack(anchor='w', pady=(0, 7))

        row = ttk.Frame(box)
        row.pack(fill='x', pady=(0, 7))
        lab(row, '线程').pack(side='left')
        ttk.Spinbox(row, textvariable=self.var_threads, from_=1, to=32,
                    width=4).pack(side='left', padx=(6, 14))
        lab(row, '压缩').pack(side='left')
        ttk.Spinbox(row, textvariable=self.var_compress, from_=0, to=9,
                    width=4).pack(side='left', padx=(6, 0))

        row = ttk.Frame(box)
        row.pack(fill='x', pady=(0, 7))
        lab(row, '格式').pack(side='left')
        self.cmb_format = ttk.Combobox(row, textvariable=self.var_format, width=6,
                                       state='readonly',
                                       values=['auto', 'webp', 'jpeg', 'png'])
        self.cmb_format.pack(side='left', padx=(6, 12))
        lab(row, '质量').pack(side='left')
        ttk.Spinbox(row, textvariable=self.var_quality, from_=50, to=100,
                    width=4).pack(side='left', padx=(6, 0))

        ttk.Checkbutton(box, text='已存在的压缩包跳过', style='Cute.TCheckbutton',
                        variable=self.var_skip).pack(anchor='w')
        ttk.Checkbutton(box, text='章节按名称自然排序', style='Cute.TCheckbutton',
                        variable=self.var_order).pack(anchor='w', pady=(1, 6))

        lab(box, '代理（留空走系统代理）').pack(anchor='w')
        ttk.Entry(box, textvariable=self.var_proxy).pack(fill='x', pady=(2, 4))

        self._build_tips(parent)

    def _build_tips(self, parent) -> None:
        """右下角的小提示卡片（纯展示）。"""
        box = ttk.LabelFrame(parent, text=' 小提示 ', padding=(10, 8))
        box.pack(fill='x', pady=(8, 0))

        lines = [
            '点最左的爱心列切换勾选',
            '搜索翻页会累积，可跨页勾选',
            '车号页支持一次贴一批',
        ]
        for text in lines:
            row = ttk.Frame(box)
            row.pack(fill='x', pady=1)
            ttk.Label(row, text='·', style='Card.TLabel',
                      foreground=PALETTE['pink'], width=1).pack(side='left')
            ttk.Label(row, text=text, style='Hint.TLabel',
                      wraplength=236, justify='left').pack(side='left', fill='x')

    def _build_actions(self, parent) -> None:
        """底部操作条：进度 + 状态 + 开始/停止/打开目录（一条排完，省纵向空间）。"""
        bar = ttk.Frame(parent)
        bar.pack(side='bottom', fill='x', pady=(8, 0))

        self.btn_start = ttk.Button(bar, text='开始下载勾选项',
                                    style='Accent.TButton',
                                    command=self._start_download)
        self.btn_start.pack(side='left', ipadx=8)
        self.btn_stop = ttk.Button(bar, text='停止', style='Stop.TButton',
                                   width=7, command=self._stop_download,
                                   state='disabled')
        self.btn_stop.pack(side='left', padx=(8, 0))
        ttk.Button(bar, text='打开输出目录', style='Soft.TButton',
                   command=self._open_output).pack(side='left', padx=(8, 0))

        ttk.Label(bar, textvariable=self.var_progress_text, width=30,
                  anchor='e', style='HintBg.TLabel').pack(side='right', padx=(10, 0))
        ttk.Progressbar(bar, variable=self.var_progress, maximum=100.0,
                        style='Cute.Horizontal.TProgressbar').pack(
            side='left', fill='x', expand=True, padx=(12, 0), pady=6)

    # ------------------------------------------------------------------ 列表逻辑

    def refresh_list(self) -> None:
        for tab in getattr(self, 'tabs', []):
            self._refresh_tab(tab)
        tab = self._active
        keyword = self.var_filter.get().strip() if tab is self.tab_fav else ''
        shown = len(self._visible_ids(tab)) if keyword else None
        self.var_count.set(tab.count_text(shown, keyword))
    def _visible_ids(self, tab: AlbumTab) -> List[str]:
        keyword = self.var_filter.get().strip().lower() if tab is self.tab_fav else ''
        out = []
        for album in tab.albums:
            if keyword and keyword not in album.title.lower() \
                    and keyword not in album.album_id:
                continue
            out.append(album.album_id)
        return out

    def _refresh_tab(self, tab: AlbumTab) -> None:
        keyword = self.var_filter.get().strip().lower() if tab is self.tab_fav else ''
        mode = self._var_name_mode_value()
        limit = self._int(self.var_max_chars.get(), 60)

        tab.tree.delete(*tab.tree.get_children())
        row_no = 0
        for album in tab.albums:
            if keyword and keyword not in album.title.lower() \
                    and keyword not in album.album_id:
                continue
            mark = CHECK_ON if tab.checked.get(album.album_id) else CHECK_OFF
            preview = self._preview_name(album, mode, limit)
            # 隔行浅粉，和白色行交替，长列表时更好跟住视线
            tags = ('stripe',) if row_no % 2 else ()
            tab.tree.insert('', 'end', iid=f'{id(tab)}_{album.album_id}',
                            values=(mark, preview, album.title, album.album_id),
                            tags=tags)
            row_no += 1

    def _preview_name(self, album: AlbumStub, mode: str, limit: int) -> str:
        """列表里那一列「命名预览」——尽量和落盘时的名字一致（含作者）。

        顺序与 ``build_archive_name`` 保持一致：先截断作品名，再加 ``[作者]``
        前缀（作者不占字数上限）；完整原标题模式原样显示。
        """
        name = album.title if mode == 'full' else clean_title(album.title)
        name, _ = truncate_title(name, limit)
        if not name:
            return album.title
        if mode != 'full':
            name = author_tagged(name, getattr(album, 'author', ''))
        return name

    # 下面这些是给测试与右键菜单用的「当前页」快捷入口

    def _refresh_tree(self) -> None:
        self.refresh_list()

    def _on_albums(self, items: List[AlbumStub]) -> None:
        self.tab_fav.set_albums(items)
        self.refresh_list()
        self._log(f'共 {len(items)} 个本子')

    def _row_album_id(self, tab: AlbumTab, iid: str) -> str:
        if 'iid' in tab.tree.item(iid)['values'][3:] or True:
            vals = tab.tree.item(iid)['values']
            if len(vals) >= 4:
                return str(vals[3])
        return str(iid).split('_', 1)[-1]

    def _on_tree_click(self, tab: AlbumTab, event) -> None:
        row = tab.tree.identify_row(event.y)
        col = tab.tree.identify_column(event.x)
        if not row:
            return
        album_id = self._row_album_id(tab, row)
        if col == '#1':
            tab.checked[album_id] = not tab.checked.get(album_id, False)
            self.refresh_list()
        elif col in ('#2', '#3', '#4'):
            tab.tree.selection_set(row)

    def _on_tree_double(self, tab: AlbumTab, event) -> None:
        row = tab.tree.identify_row(event.y)
        if row:
            self._open_album_page(self._row_album_id(tab, row))

    def _on_tree_menu(self, tab: AlbumTab, event) -> None:
        row = tab.tree.identify_row(event.y)
        if not row:
            return
        tab.tree.selection_set(row)
        album_id = self._row_album_id(tab, row)

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label='勾选 / 取消',
                         command=lambda: (tab.checked.__setitem__(
                             album_id, not tab.checked.get(album_id, False)),
                             self.refresh_list()))
        menu.add_command(label='打开网页',
                         command=lambda: self._open_album_page(album_id))
        menu.add_command(label='仅选这一本',
                         command=lambda: self._check_only(album_id, tab))
        menu.add_separator()
        menu.add_command(label='复制标题',
                         command=lambda: self._copy_text(tab.title_of(album_id)))
        menu.add_command(label='复制作品名',
                         command=lambda: self._copy_text(
                             self._preview_name(
                                 AlbumStub(album_id, tab.title_of(album_id)),
                                 self._var_name_mode_value(),
                                 self._int(self.var_max_chars.get(), 60))))
        menu.add_command(label='复制 ID', command=lambda: self._copy_text(album_id))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def checked_title(self, album_id: str) -> str:
        return self._active.title_of(album_id)

    def _copy_text(self, text: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(text)
        self._log(f'已复制：{text[:60]}')

    def _check_only(self, album_id: str, tab: Optional[AlbumTab] = None) -> None:
        tab = tab or self._active
        for album in tab.albums:
            tab.checked[album.album_id] = (album.album_id == album_id)
        self.refresh_list()

    def _toggle_selected(self, tab: Optional[AlbumTab] = None) -> None:
        tab = tab or self._active
        for row in tab.tree.selection():
            album_id = self._row_album_id(tab, row)
            tab.checked[album_id] = not tab.checked.get(album_id, False)
        self.refresh_list()

    def _check_all(self, value: bool, tab: Optional[AlbumTab] = None) -> None:
        tab = tab or self._active
        for album in tab.albums:
            tab.checked[album.album_id] = value
        self.refresh_list()

    def _invert_check(self, tab: Optional[AlbumTab] = None) -> None:
        tab = tab or self._active
        for album in tab.albums:
            tab.checked[album.album_id] = not tab.checked.get(album.album_id, False)
        self.refresh_list()

    def _on_tab_changed(self) -> None:
        tab = self._active
        keyword = self.var_filter.get().strip() if tab is self.tab_fav else ''
        shown = len(self._visible_ids(tab)) if keyword else None
        self.var_count.set(tab.count_text(shown, keyword))
        # 搜索页保留搜索状态；其它页清掉分页提示
        if tab is not self.tab_search:
            self.var_search_info.set('')

    def _open_album_page(self, album_id: str) -> None:
        import webbrowser
        client = self.engine.client
        domain = None
        try:
            domains = getattr(client, 'domain_list', None) or []
            domain = domains[0] if domains else None
        except Exception:
            domain = None
        url = (f'https://{domain}/album/{album_id}/' if domain
               else f'https://18comic.vip/album/{album_id}/')
        webbrowser.open(url)

    # ------------------------------------------------------------------ 日志/队列

    def _log_from_thread(self, text: str) -> None:
        self.msg_queue.put(('log', text))

    def _log(self, text: str) -> None:
        stamp = time.strftime('%H:%M:%S')
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f'[{stamp}] ', ('time',))
        # 按内容挑个颜色，扫一眼就能分出成功 / 失败 / 命名
        if text.startswith('[完成]'):
            tag = ('ok',)
        elif text.startswith('[失败]') or '失败' in text[:6]:
            tag = ('err',)
        elif text.startswith('命名：'):
            tag = ('name',)
        else:
            tag = ()
        self.log_text.insert('end', f'{text}\n', tag)
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _post(self, kind: str, payload) -> None:
        self.msg_queue.put((kind, payload))

    def _drain_queue(self) -> None:
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == 'log':
                    self._log(str(payload))
                elif kind == 'progress':
                    self._on_progress(payload)
                elif kind == 'status':
                    self.var_status.set(str(payload))
                elif kind == 'folders':
                    self._on_folders(payload)
                elif kind == 'albums':
                    self._on_albums(payload)
                elif kind == 'search':
                    self._on_search_result(payload)
                elif kind == 'search_idle':
                    self._searching = False
                elif kind == 'download_done':
                    self._on_download_done(payload)
                elif kind == 'error':
                    messagebox.showerror(APP_TITLE, str(payload))
                elif kind == 'busy':
                    self._set_busy(bool(payload))
        except queue.Empty:
            pass
        self.after(120, self._drain_queue)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = 'disabled' if busy else 'normal'
        for btn in (self.btn_login, self.btn_load):
            btn.configure(state=state)
        self.btn_start.configure(state=state)
        self.btn_stop.configure(state='normal' if busy else 'disabled')

    # ------------------------------------------------------------------ 登录

    def _try_cookie_login(self, cookies: dict) -> None:
        def work():
            try:
                info = self.engine.login_with_cookies(cookies, self.var_user.get().strip())
                self._post('status', f'已用本机登录态：{info.get("username") or "已有 cookies"}')
                self._post('log', '已用保存的登录态恢复会话（如失效请重新输入密码登录）')
                self._refresh_folders_async()
            except Exception as exc:
                self._post('status', '登录态已失效，请重新登录')
                self._post('log', f'保存的登录态不可用：{friendly_error(exc)}')
        threading.Thread(target=work, daemon=True).start()

    def _do_login(self) -> None:
        user = self.var_user.get().strip()
        pwd = self.var_pass.get()
        if not user or not pwd:
            messagebox.showwarning(APP_TITLE, '请填写用户名和密码')
            return

        self._set_busy(True)
        self.var_status.set('登录中…')

        def work():
            try:
                info = self.engine.login(user, pwd)
                self.cfg['cookies'] = info.get('cookies') or {}
                self._post('status', f'已登录：{user}')
                self._post('log', f'登录成功，uid={info.get("user_id")}')
                self._save_config()
                self._refresh_folders_async()
            except Exception as exc:
                msg = friendly_error(exc)
                self._post('status', '登录失败')
                self._post('log', f'登录失败：{msg}')
                self._post('error', f'登录失败：\n{msg}')
            finally:
                self._post('busy', False)

        threading.Thread(target=work, daemon=True).start()

    def _require_login(self) -> bool:
        if not self.engine.logged_in:
            messagebox.showwarning(APP_TITLE, '请先登录')
            return False
        return True

    # ------------------------------------------------------------------ 收藏夹

    def _refresh_folders_async(self) -> None:
        def work():
            try:
                folders = self.engine.list_folders()
                self._post('folders', folders)
            except Exception as exc:
                self._post('log', f'读取收藏夹目录失败：{friendly_error(exc)}')
        threading.Thread(target=work, daemon=True).start()

    def _do_list_folders(self) -> None:
        if not self._require_login():
            return
        self._refresh_folders_async()

    def _on_folders(self, folders: List[FolderInfo]) -> None:
        self.folders = folders
        labels = [f'{f.name}（{f.count}）' if f.folder_id == '0' else f.name
                  for f in folders]
        self.cmb_folder['values'] = labels
        if labels:
            self.cmb_folder.current(0)
        self._log(f'收藏夹：{len(folders)} 个')

    def _current_folder(self) -> FolderInfo:
        idx = self.cmb_folder.current()
        if 0 <= idx < len(self.folders):
            return self.folders[idx]
        return FolderInfo('0', '全部收藏')

    def _load_favorites(self) -> None:
        if not self._require_login():
            return
        folder = self._current_folder()

        self._set_busy(True)
        self.var_status.set(f'正在拉取「{folder.name}」…')
        self.stop_flag.clear()

        def work():
            try:
                items = self.engine.fetch_all_favorites(
                    folder_id=folder.folder_id,
                    progress=lambda p: self._post(
                        'status', f'已读取 {p["count"]} 个本子…'),
                    should_stop=self.stop_flag.is_set,
                )
                self._post('albums', items)
            except Cancelled:
                self._post('log', '已取消拉取')
            except Exception as exc:
                msg = friendly_error(exc)
                self._post('log', f'拉取收藏失败：{msg}')
                self._post('error', f'拉取收藏失败：\n{msg}')
            finally:
                self._post('busy', False)
                self._post('status', '就绪')

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------ 搜索

    def _do_search(self, reset: bool = True, page: Optional[int] = None,
                   append: bool = False) -> None:
        """发起一次搜索。

        :param reset: 新的一轮搜索（换关键词/排序/分类）——页码归 1，列表替换
        :param page: 指定页码（翻页时用）；省略则按 ``reset`` 取 1 或当前页
        :param append: 结果追加到已有列表（翻页）而不是替换
        """
        if not self._require_login():
            return
        if self._searching:
            return

        keyword = self.var_search.get().strip()
        if not keyword:
            messagebox.showinfo(APP_TITLE, '请输入搜索关键词或车号')
            return

        if page is None:
            page = 1 if reset else self._search_page
        page = max(1, int(page))
        if reset:
            append = False
        self._search_page = page

        order = next((v for lb, v in ORDER_CHOICES
                      if lb == self.var_search_order.get()), 'mr')
        category = next((v for lb, v in CATEGORY_CHOICES
                         if lb == self.var_search_cat.get()), '0')

        self._searching = True
        self._set_busy(True)
        self.var_status.set(f'搜索「{keyword}」第 {page} 页…')

        def work():
            try:
                result = self.engine.search(keyword, page=page,
                                            order_by=order, category=category)
                self._post('search', {'result': result, 'keyword': keyword,
                                      'mode': 'append' if append else 'replace'})
            except Exception as exc:
                msg = friendly_error(exc)
                self._post('log', f'搜索失败：{msg}')
                self._post('error', f'搜索失败：\n{msg}')
            finally:
                self._post('search_idle', True)
                self._post('busy', False)
                self._post('status', '就绪')

        threading.Thread(target=work, daemon=True).start()

    def _page_search(self, delta: int) -> None:
        """上一页 / 下一页：翻到相邻页并把结果**追加**进列表。"""
        if self._searching:
            return
        if not self.var_search.get().strip():
            messagebox.showinfo(APP_TITLE, '请先输入关键词搜索一次')
            return
        target = self._search_page + delta
        if target < 1:
            return
        if self._search_pages and target > self._search_pages:
            return
        self._do_search(reset=False, page=target, append=True)

    def _on_search_result(self, payload: dict) -> None:
        result = payload['result']
        keyword = payload['keyword']
        mode = payload.get('mode', 'replace')

        self._search_page = result.page
        self._search_pages = result.page_count or 1

        if mode == 'append':
            self.tab_search.add_albums(result.items)
        else:
            self.tab_search.set_albums(result.items)

        self.notebook.select(1)
        self.refresh_list()

        span = f'第 {result.page}/{result.page_count or 1} 页'
        total = f'共 {result.total} 条'
        if result.single:
            self.var_search_info.set('车号直达')
            self._log(f'车号直达：{keyword} → {result.items[0].title if result.items else ""}')
        else:
            self.var_search_info.set(f'{total} · {span}')
            self._log(f'搜索「{keyword}」：{total}，本页 {len(result.items)} 条')

    # ------------------------------------------------------------------ 车号

    def _add_ids(self, reset: bool = False) -> None:
        raw = self.var_id_input.get().strip()
        if not raw:
            messagebox.showinfo(APP_TITLE, '请粘贴车号或链接')
            return

        ids = parse_album_ids(raw)
        if not ids:
            messagebox.showwarning(
                APP_TITLE, '没识别出车号。支持 123456 / JM123456 / 网址')
            return

        if reset:
            self.tab_id.albums = []
            self.tab_id.checked = {}

        known = {a.album_id for a in self.tab_id.albums}
        added = 0
        for aid in ids:
            if aid in known:
                continue
            self.tab_id.albums.append(AlbumStub(aid, f'JM{aid}'))
            self.tab_id.checked[aid] = True
            known.add(aid)
            added += 1

        self.var_id_input.set('')
        self.notebook.select(2)
        self.refresh_list()
        self._log(f'添加 {added} 个车号（共 {len(self.tab_id.albums)} 个）')

        # 后台补全标题，方便看清名字与命名预览
        to_fetch = [AlbumStub(aid, f'JM{aid}') for aid in known]
        del to_fetch  # 只补全还没有真名的
        needs = [a for a in self.tab_id.albums if a.title.startswith('JM')]
        if needs and self.engine.logged_in:
            threading.Thread(target=self._fill_titles, args=(needs,), daemon=True).start()

    def _clear_ids(self) -> None:
        self.tab_id.albums = []
        self.tab_id.checked = {}
        self.refresh_list()
        self._log('已清空车号列表')

    def _fill_titles(self, items: List[AlbumStub]) -> None:
        client = self.engine.client
        changed = 0
        for stub in items:
            try:
                album = client.get_album_detail(stub.album_id)
                stub.title = album.title or stub.title
                changed += 1
                self._post('log', f'JM{stub.album_id} → {clean_title(stub.title)}')
            except Exception:
                pass
        if changed:
            self._post('log', f'已补全 {changed} 个标题')

    def _download_typed_id(self) -> None:
        if not self._require_login():
            return
        raw = self.var_id_input.get().strip()
        album_id = try_parse_album_id(raw)
        if not album_id:
            messagebox.showwarning(APP_TITLE, '没识别出车号')
            return
        output = self.var_output.get().strip() or DEFAULT_OUTPUT
        os.makedirs(output, exist_ok=True)
        self.var_id_input.set('')
        self._launch_download([AlbumStub(album_id, f'JM{album_id}')], output)

    # ------------------------------------------------------------------ 下载

    def _pick_output(self) -> None:
        path = filedialog.askdirectory(initialdir=self.var_output.get() or app_dir())
        if path:
            self.var_output.set(path)

    def _open_output(self) -> None:
        path = self.var_output.get().strip() or DEFAULT_OUTPUT
        try:
            os.makedirs(path, exist_ok=True)
            os.startfile(path)  # noqa: S606  (Windows 专用)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f'打不开目录：{exc}')

    def _start_download(self) -> None:
        if self._busy:
            return
        if not self._require_login():
            return

        tab = self._active
        targets = tab.picked()
        if not targets:
            messagebox.showinfo(APP_TITLE, '当前页没有勾选任何本子')
            return

        output = self.var_output.get().strip() or DEFAULT_OUTPUT
        try:
            os.makedirs(output, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(APP_TITLE, f'输出目录不可用：{exc}')
            return

        self._launch_download(targets, output)

    def _launch_download(self, targets: List[AlbumStub], output: str) -> None:
        self.stop_flag.clear()
        self._last_output_dir = output
        self.var_progress.set(0.0)
        self.var_progress_text.set(f'0 / {len(targets)}')
        self._set_busy(True)
        self._log(f'开始下载 {len(targets)} 个本子 → {output}')

        max_chars = self._int(self.var_max_chars.get(), 60)
        template = self.var_template.get().strip() or '{title}'
        threads = max(1, self._int(self.var_threads.get(), 8))
        compress = max(0, min(9, self._int(self.var_compress.get(), 0)))
        skip = bool(self.var_skip.get())
        order = bool(self.var_order.get())
        image_format = self.var_format.get() or 'auto'
        image_quality = max(50, min(100, self._int(self.var_quality.get(), 90)))
        name_mode = self._var_name_mode_value()

        self.engine.image_format = image_format
        self.engine.image_quality = image_quality
        self.engine.proxy = self.var_proxy.get().strip()
        self._save_config()

        def work():
            results = []
            try:
                results = self.engine.download_albums(
                    targets, output,
                    max_title_chars=max_chars,
                    template=template,
                    compress_level=compress,
                    image_threads=threads,
                    skip_existing=skip,
                    order_by_name=order,
                    image_format=image_format,
                    image_quality=image_quality,
                    name_mode=name_mode,
                    progress=lambda p: self._post('progress', p),
                    should_stop=self.stop_flag.is_set,
                )
            except Exception as exc:
                msg = friendly_error(exc)
                self._post('log', f'下载流程异常：{msg}')
                self._post('error', f'下载异常：\n{msg}')
            finally:
                self._post('download_done', results)
                self._post('busy', False)

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _stop_download(self) -> None:
        self.stop_flag.set()
        self._log('已请求停止，正在结束当前图片…')

    def _on_progress(self, payload: dict) -> None:
        kind = payload.get('type')
        if kind == 'album_start':
            i, total = payload['index'], payload['total']
            self.var_progress_text.set(f'第 {i} / {total} 本 · 准备中')
            self._log(f'—— [{i}/{total}] {payload["title"]}')
        elif kind == 'album_meta':
            self.var_progress.set(0.0)
        elif kind == 'photo_start':
            self.var_progress.set(0.0)
            self.var_progress_text.set(
                f'章节 {payload["photo_index"]}/{payload["photo_total"]}'
                f' · {payload.get("images_done", 0)} 张')
        elif kind == 'image_done':
            done = payload.get('images_done', 0)
            total = max(1, payload.get('images_total') or 1)
            self.var_progress.set(min(100.0, done * 100.0 / total))
            self.var_progress_text.set(
                f'章节 {payload.get("photo_index", 0)}/{payload.get("photo_total", 0)}'
                f' · {done}/{total} 张')

    def _on_download_done(self, results: List) -> None:
        ok = [r for r in results if getattr(r, 'ok', False) and not r.skipped]
        skipped = [r for r in results if getattr(r, 'skipped', False)]
        failed = [r for r in results if not getattr(r, 'ok', False)]

        self.var_progress.set(100.0 if ok else 0.0)
        self.var_progress_text.set(
            f'完成 {len(ok)} · 跳过 {len(skipped)} · 失败 {len(failed)}')
        self._log(f'全部结束：完成 {len(ok)}，跳过 {len(skipped)}，失败 {len(failed)}')
        for r in failed:
            self._log(f'  失败：{r.title} → {r.error}')

        if results:
            messagebox.showinfo(
                APP_TITLE,
                f'完成：{len(ok)}\n跳过（已存在）：{len(skipped)}\n失败：{len(failed)}\n\n'
                f'保存位置：{self._last_output_dir}'
            )

    # ------------------------------------------------------------------ 杂项

    @staticmethod
    def _int(text: str, default: int) -> int:
        try:
            return int(str(text).strip())
        except (TypeError, ValueError):
            return default

    def _on_close(self) -> None:
        if self._busy:
            if not messagebox.askyesno(APP_TITLE, '还在下载，确定要退出吗？'):
                return
            self.stop_flag.set()
        try:
            self._save_config()
        finally:
            self.destroy()


def main() -> None:
    app = JmApp()
    app.mainloop()


if __name__ == '__main__':
    main()
