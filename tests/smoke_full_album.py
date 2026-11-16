"""联网完整链路测试：挑一个「页数最少」的真实本子，整本下载成 zip 并校验。

用法：python tests/smoke_full_album.py [album_id]
不传 album_id 时从单本分类里挑页数最少的一个。
"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmMagicConstants as C, JmOption

from jmfav.engine import AlbumStub, JmEngine


def pick_small_album(client):
    page = client.categories_filter(page=1, time=C.TIME_ALL,
                                    category=C.CATEGORY_SINGLE,
                                    order_by=C.ORDER_BY_LATEST)
    ids = list(page.iter_id())
    best = None
    for aid in ids[:15]:
        album = client.get_album_detail(aid)
        print(f'  候选 {aid}: 章节 {len(album):>3} · 页 {album.page_count:>4} · {album.title[:40]}')
        if best is None or album.page_count < best.page_count:
            best = album
        if best.page_count <= 30:
            break
    return best


def main():
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')

    if len(sys.argv) > 1:
        album = client.get_album_detail(sys.argv[1])
    else:
        print('正在从单本分类里找小本子…')
        album = pick_small_album(client)

    print(f'\n目标：{album.title}')
    print(f'  作者 {album.author} · 章节 {len(album)} · 页数 {album.page_count}')

    out = tempfile.mkdtemp(prefix='jmfull-')
    engine = JmEngine(log=print)
    engine.client = client

    results = engine.download_albums(
        [AlbumStub(album.album_id, album.title)], out,
        max_title_chars=60, image_threads=8, skip_existing=False,
    )
    r = results[0]
    print('\n结果：ok=%s images=%d seconds=%s' % (r.ok, r.images, r.seconds))
    print('文件：', os.path.basename(r.path))
    if not r.ok:
        print('错误：', r.error)
        return 1

    with zipfile.ZipFile(r.path) as zf:
        names = zf.namelist()
        bad = zf.testzip()
    print('zip 条目：', len(names), '| 校验：', 'OK' if bad is None else f'坏条目 {bad}')
    print('前 3 条：', names[:3])
    print('最后 1 条：', names[-1:])

    residue = [n for n in os.listdir(out) if n != os.path.basename(r.path)]
    print('目录残留：', residue or '无')

    ok = (r.ok and len(names) == r.images == album.page_count
          and bad is None and not residue)
    print('RESULT:', 'OK' if ok else 'CHECK')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
