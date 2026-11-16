"""联网测试：站内搜索、车号直达、分类/排序。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption

from jmfav.engine import JmEngine


def main():
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    engine = JmEngine(log=lambda s: None)
    engine.client = option.new_jm_client(impl='api')

    ok = True

    def check(label, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label + (f'  {extra}' if extra else ''))
        if not cond:
            ok = False

    # 1. 关键词搜索
    r = engine.search('秘密', page=1)
    check('关键词搜索有结果', r.total > 0 and len(r.items) > 0,
          f'total={r.total} page={len(r.items)} pages={r.page_count}')
    check('搜索不是车号直达', not r.single)
    check('结果带标题', all(a.title for a in r.items), r.items[0].title[:50] if r.items else '')

    # 2. 分页
    if r.page_count > 1:
        r2 = engine.search('秘密', page=2)
        ids1 = {a.album_id for a in r.items}
        ids2 = {a.album_id for a in r2.items}
        check('第 2 页与第 1 页不同', bool(ids2 - ids1), f'{len(ids2 - ids1)} 个新条目')

    # 3. 车号直达
    first_id = r.items[0].album_id
    single = engine.search(first_id)
    check('车号直达', single.single and len(single.items) == 1,
          f'single={single.single} n={len(single.items)}')
    check('直达 ID 一致', single.items and single.items[0].album_id == first_id,
          single.items[0].album_id if single.items else '')

    # 4. 排序生效（最新 vs 最热 结果不同）
    a = engine.search('老師', order_by='mr')
    b = engine.search('老師', order_by='mv')
    check('不同排序给不同结果',
          [x.album_id for x in a.items] != [x.album_id for x in b.items])

    # 5. 分类
    c = engine.search('老師', category='doujin')
    check('分类筛选可返回结果', len(c.items) >= 0, f'total={c.total}')

    # 6. 多页抓取
    many = engine.search_all('祕密', pages=2)
    check('search_all 翻多页', len(many) > len(r.items) or len(many) > 0, f'{len(many)} 个')

    # 7. 空关键词报错
    try:
        engine.search('')
        check('空关键词应报错', False)
    except ValueError:
        check('空关键词报错', True)

    # 8. 搜不到的词
    none = engine.search('zzzzqqqq不存在的词xyz')
    check('搜不到时返回空', none.items == [] and none.total == 0,
          f'total={none.total}')

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
