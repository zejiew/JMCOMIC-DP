"""GUI 冒烟测试：三个标签页、命名预览、勾选/筛选/翻页，不联网。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.engine import AlbumStub, FolderInfo, SearchResult
from jmfav.theme import CHECK_OFF, CHECK_ON
from jmfav.gui import JmApp


def main():
    app = JmApp()
    app.update()
    ok = True

    def check(label, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label + (f'  {extra}' if extra else ''))
        if not cond:
            ok = False

    # 三个标签页
    check('三个标签页', app.notebook.index('end') == 3,
          str(app.notebook.index('end')))
    check('默认在收藏夹页', app._active is app.tab_fav)

    # ---- 收藏夹页 ----
    app._on_folders([FolderInfo('0', '全部收藏', 87), FolderInfo('123', '喜欢的', 12)])
    app._on_albums([
        AlbumStub('1', '[無邪氣漢化組] (C99) [紺色果實] サレンの樂しい夢 (プリコネ) [中國翻譯]'),
        AlbumStub('2', '短标题'),
        AlbumStub('3', 'a/b:c*?"<>|'),
    ])
    app.update()

    rows = app.tab_fav.tree.get_children()
    check('收藏页 3 行', len(rows) == 3, str(rows))

    first = app.tab_fav.tree.item(rows[0])['values']
    check('命名预览已提取作品名', first[1].startswith('サレンの樂しい夢'), str(first[1]))
    check('原标题完整保留', '無邪氣' in str(first[2]), str(first[2])[:40])

    # 切换到「完整原标题」模式
    from jmfav.gui import NAME_MODE_CHOICES
    app.var_name_mode.set(NAME_MODE_CHOICES[1][0])
    app.update()
    first = app.tab_fav.tree.item(app.tab_fav.tree.get_children()[0])['values']
    check('完整模式含汉化组', '無邪氣' in str(first[1]), str(first[1])[:40])
    app.var_name_mode.set(NAME_MODE_CHOICES[0][0])
    app.update()

    # 勾选
    app.tab_fav.checked['1'] = False
    app.refresh_list()
    app.update()
    check('取消勾选', app.tab_fav.tree.item(app.tab_fav.tree.get_children()[0])['values'][0] == CHECK_OFF)

    # 筛选
    app.var_filter.set('短')
    app.update()
    check('筛选本页', len(app.tab_fav.tree.get_children()) == 1,
          str(len(app.tab_fav.tree.get_children())))
    app.var_filter.set('')
    app.update()

    # ---- 搜索页 ----
    app._on_search_result({
        'result': SearchResult(
            items=[AlbumStub('111', '[漢化] 測試作品 A [中國翻譯]'),
                   AlbumStub('222', '[漢化] 測試作品 B [中國翻譯]')],
            total=57, page=1, page_count=3, single=False),
        'keyword': '測試', 'mode': 'replace',
    })
    app.update()
    check('切到搜索页', app._active is app.tab_search)
    check('搜索结果显示', len(app.tab_search.albums) == 2, str(app.tab_search.albums))
    check('分页信息', '57' in app.var_search_info.get(), app.var_search_info.get())

    # 追加第 2 页
    app._on_search_result({
        'result': SearchResult(items=[AlbumStub('333', '第三個')],
                               total=57, page=2, page_count=3),
        'keyword': '測試', 'mode': 'append',
    })
    app.update()
    check('翻页追加', len(app.tab_search.albums) == 3, str(len(app.tab_search.albums)))

    # 车号直达
    app._on_search_result({
        'result': SearchResult(items=[AlbumStub('999', '直达作品')],
                               total=1, page=1, page_count=1, single=True),
        'keyword': '999', 'mode': 'replace',
    })
    app.update()
    check('车号直达标记', app.var_search_info.get() == '车号直达', app.var_search_info.get())

    # ---- 车号页 ----
    app.var_id_input.set('123456, JM789012, https://18comic.vip/album/555555/')
    app._add_ids()
    app.update()
    ids = [a.album_id for a in app.tab_id.albums]
    check('车号解析', ids == ['123456', '789012', '555555'], str(ids))
    check('输入框已清空', app.var_id_input.get() == '')

    app.var_id_input.set('123456')
    app._add_ids()
    app.update()
    check('重复车号不重复添加', len(app.tab_id.albums) == 3,
          str([a.album_id for a in app.tab_id.albums]))

    app._clear_ids()
    app.update()
    check('清空车号', len(app.tab_id.albums) == 0)

    # 三个页各自独立的勾选
    app.tab_id.checked['x'] = True
    check('各页勾选独立', 'x' not in app.tab_fav.checked)

    app.destroy()
    print('RESULT:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
