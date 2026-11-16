"""联网冒烟测试：验证真实环境下「拉详情 → 下 1 张图 → 写 zip」能走通。

只下载 1 张图片用于校验解码与打包链路，不落整本。
用法：python tests/smoke_live.py [album_id]
不传 album_id 时从首页排行里挑一个。
"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption

from jmfav.engine import JmEngine, _cleanup_dir, _zip_write


def main():
    option = JmOption.construct({'client': {'impl': 'api'}})
    client = option.new_jm_client(impl='api')

    album_id = sys.argv[1] if len(sys.argv) > 1 else None
    if album_id is None:
        from jmcomic import JmMagicConstants as C
        page = client.categories_filter(page=1, time=C.TIME_ALL,
                                        category=C.CATEGORY_ALL, order_by=C.ORDER_BY_VIEW)
        ids = list(page.iter_id())
        if not ids:
            print('分类页也没有结果，请手动传入 album_id')
            return 1
        album_id = ids[0]
        print('挑选的 album_id =', album_id)

    album = client.get_album_detail(album_id)
    print('标题:', album.title)
    print('作者:', album.author, '| 章节数:', len(album), '| 总页数:', album.page_count)

    out = tempfile.mkdtemp(prefix='jmsmoke-')
    engine = JmEngine(log=print)
    engine.client = client

    # 只取第一章的第一张图，验证真实的解码 + zip 写入
    photo = album[0]
    client.check_photo(photo)
    images = list(photo)
    print('第一章:', photo.name, '| 图片数:', len(images))

    tmpdir = os.path.join(out, '.jmtmp')
    data = engine._fetch_bytes(client, images[0], tmpdir)
    print('下载字节数:', len(data), '| 头 8 字节:', data[:8].hex())

    # 并发路径：同一章节多张图并行拉取，验证线程池 + 客户端复用没问题
    from concurrent.futures import ThreadPoolExecutor
    sample = images[:8]
    with ThreadPoolExecutor(max_workers=4) as pool:
        blobs = list(pool.map(lambda im: engine._fetch_bytes(client, im, tmpdir), sample))
    print('并发拉取张数:', len(blobs), '| 大小:', [len(b) for b in blobs])
    sizes_ok = all(len(b) > 1000 for b in blobs) and len(set(map(len, blobs))) == len(blobs)

    zip_path = os.path.join(out, 'smoke.zip')
    with zipfile.ZipFile(zip_path, 'w') as zf:
        for im, blob in zip(sample, blobs):
            _zip_write(zf, f'{im.index:05d}{im.img_file_suffix}', blob, 0)
    with zipfile.ZipFile(zip_path) as zf:
        ok_zip = zf.testzip() is None and len(zf.namelist()) == len(sample)
        print('zip 校验:', ok_zip, zf.namelist()[:3], '...')

    _cleanup_dir(tmpdir)
    print('临时目录已清理:', not os.path.exists(tmpdir))

    ok = len(data) > 1000 and sizes_ok and ok_zip
    print('RESULT:', 'OK' if ok else 'SUSPICIOUS')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
