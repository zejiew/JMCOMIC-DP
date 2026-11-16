"""检查界面在高 DPI / 小屏下是否被裁切（模拟不同窗口尺寸）。"""

import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.engine import AlbumStub, FolderInfo
from jmfav.gui import JmApp


def fill(app):
    app._on_folders([FolderInfo('0', '全部收藏', 87), FolderInfo('123', '喜欢的', 12)])
    app._on_albums([AlbumStub(str(1000 + i), f'测试本子标题第 {i} 话' * 2)
                    for i in range(20)])
    app.var_status.set('已登录：demo')
    app.var_progress.set(55)
    app.var_progress_text.set('章节 3/8 · 128/357 张')
    app._log('测试日志行')


def main():
    app = JmApp()
    fill(app)
    ok = True

    for geom in ('1000x660', '1240x900', '1400x1000'):
        app.geometry(geom)
        app.update()
        app.update_idletasks()
        w, h = app.winfo_width(), app.winfo_height()

        # 关键控件必须完整落在窗口内
        widgets = {
            '开始下载': app.btn_start,
            '停止': app.btn_stop,
            '树': app.tree,
            '日志': app.log_text,
        }
        bad = []
        for name, wdg in widgets.items():
            try:
                x, y = wdg.winfo_rootx() - app.winfo_rootx(), \
                    wdg.winfo_rooty() - app.winfo_rooty()
                ww, wh = wdg.winfo_width(), wdg.winfo_height()
            except tk.TclError:
                bad.append(f'{name}(不存在)')
                continue
            if ww <= 1 or wh <= 1:
                bad.append(f'{name}(尺寸 {ww}x{wh})')
            elif x + ww > w + 2 or y + wh > h + 2 or x < 0 or y < 0:
                bad.append(f'{name}(越界 {x},{y} {ww}x{wh})')

        status = 'ok' if not bad else '裁切: ' + ', '.join(bad)
        print(f'{geom:<12} 窗口 {w}x{h}  {status}')
        if bad:
            ok = False

    req = app.winfo_reqwidth(), app.winfo_reqheight()
    print(f'\n内容需要的最小尺寸: {req[0]}x{req[1]}')
    app.destroy()
    print('RESULT:', 'OK' if ok else 'LAYOUT BROKEN')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
