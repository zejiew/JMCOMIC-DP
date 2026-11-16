"""小屏（1366×768）/ 高 DPI 场景下的自适应检查。"""

import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.gui import JmApp


def main():
    app = JmApp()
    app.update()

    req = app.winfo_reqwidth(), app.winfo_reqheight()
    screen = app.winfo_screenwidth(), app.winfo_screenheight()
    pos = app.winfo_x(), app.winfo_y()
    size = app.winfo_width(), app.winfo_height()
    mini = app.minsize()

    print(f'屏幕        {screen[0]}x{screen[1]}')
    print(f'内容需求    {req[0]}x{req[1]}')
    print(f'最小尺寸    {mini[0]}x{mini[1]}')
    print(f'实际窗口    {size[0]}x{size[1]} @ ({pos[0]},{pos[1]})')

    problems = []
    if size[0] > screen[0] or size[1] > screen[1]:
        problems.append('窗口超出屏幕')
    if pos[0] + size[0] > screen[0] or pos[1] + size[1] > screen[1]:
        problems.append('窗口右下越界')
    if mini[1] > screen[1] - 40:
        problems.append(f'最小高度 {mini[1]} 超过屏幕可用高度')
    if app.btn_start.winfo_width() <= 1:
        problems.append('主按钮没显示')

    app.destroy()
    print('\n结果:', 'OK' if not problems else '问题: ' + '；'.join(problems))
    return 0 if not problems else 1


if __name__ == '__main__':
    raise SystemExit(main())
