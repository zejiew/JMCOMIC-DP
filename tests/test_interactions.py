"""右键菜单 / 复制 / 仅选一本 / 勾选交互的测试。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.engine import AlbumStub
from jmfav.theme import CHECK_OFF, CHECK_ON
from jmfav.gui import JmApp


def main():
    app = JmApp()
    app.update()
    app.tab_fav.set_albums([
        AlbumStub('111', '第一本'),
        AlbumStub('222', '第二本'),
        AlbumStub('333', '第三本'),
    ])
    app.update()
    ok = True

    def check(label, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label + (f'  {extra}' if extra else ''))
        if not cond:
            ok = False

    tab = app.tab_fav
    rows = tab.tree.get_children()

    # 仅选一本
    app._check_only('222', tab)
    picked = [k for k, v in tab.checked.items() if v]
    check('仅选一本', picked == ['222'], str(picked))

    # 复制标题
    app._copy_text(tab.title_of('222'))
    app.update()
    check('复制到剪贴板', app.clipboard_get() == '第二本', app.clipboard_get())

    # 复制 ID
    app._copy_text('333')
    app.update()
    check('复制 ID', app.clipboard_get() == '333')

    # 取消勾选后显示空框
    app._check_all(True, tab)
    app.update()
    app.tab_fav.checked['111'] = False
    app.refresh_list()
    app.update()
    first = tab.tree.item(tab.tree.get_children()[0])['values']
    check('取消后显示空框', first[0] == CHECK_OFF, str(first[0]))

    # 空格键切换
    tab.tree.selection_set(tab.tree.get_children()[1])
    app._toggle_selected(tab)
    check('空格切换勾选', tab.checked['222'] is False, str(tab.checked['222']))

    # 全选/反选
    app._check_all(True, tab)
    app._invert_check(tab)
    check('反选', all(v is False for v in tab.checked.values()))
    app._check_all(True, tab)
    check('全选', all(v is True for v in tab.checked.values()))

    # 行 iid 里带的是 tab 的 id，取值时要能拿到真 album_id
    row = tab.tree.get_children()[0]
    check('从行取回 album_id', app._row_album_id(tab, row) == '111',
          app._row_album_id(tab, row))

    # 命名预览随模式变化
    from jmfav.gui import NAME_MODE_CHOICES
    app.var_name_mode.set(NAME_MODE_CHOICES[1][0])
    app.refresh_list()
    app.update()
    vals = tab.tree.item(tab.tree.get_children()[0])['values']
    check('完整模式预览=原标题', vals[1] == '第一本', str(vals[1]))

    app.destroy()
    print('RESULT:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
