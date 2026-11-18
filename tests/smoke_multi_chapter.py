"""模拟一个多章节的大本子，评估「整本下载」的耗时与进度上报是否正常。"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption

from jmfav.engine import AlbumStub, JmEngine


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1136963'
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')
    album = client.get_album_detail(album_id)
    print(f'{album.title}')
    print(f'  章节 {len(album)} · 总页 {album.page_count}')

    out = tempfile.mkdtemp(prefix='jmmulti-')
    engine = JmEngine(log=lambda s: print(' ', s, flush=True))
    engine.client = client

    events = {'album_start': 0, 'photo_start': 0, 'image_done': 0, 'album_done': 0}

    def on_progress(p):
        events[p['type']] = events.get(p['type'], 0) + 1
        if p['type'] == 'photo_start' and p['photo_index'] % 5 == 1:
            print(f"   章节 {p['photo_index']}/{p['photo_total']} "
                  f"{p['photo_name'][:28]} ({p['images']} 张)", flush=True)

    t0 = time.time()
    r = engine.download_albums([AlbumStub(album_id, album.title)], out,
                               max_title_chars=40, image_threads=12,
                               skip_existing=False, progress=on_progress,
                               split_chapters=False)[0]
    cost = time.time() - t0

    print(f'\n耗时 {cost:.1f}s · {r.images} 张 · {r.images / cost:.1f} 张/秒')
    print('事件计数:', events)
    print('文件名:', os.path.basename(r.path))
    print('体积:', round(os.path.getsize(r.path) / 1024 / 1024, 1), 'MB')

    import zipfile
    with zipfile.ZipFile(r.path) as zf:
        names = zf.namelist()
        print('条目:', len(names), '| 首条:', names[0], '| 校验:', zf.testzip() is None)
        dirs = {n.split('/')[0] for n in names if '/' in n}
        print('章节子目录数:', len(dirs))

    import shutil
    shutil.rmtree(out, ignore_errors=True)


if __name__ == '__main__':
    main()
