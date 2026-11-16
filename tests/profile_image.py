"""拆分单张图的耗时：网络 vs 解码 vs 落盘。"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption, JmImageTool

from jmfav.engine import JmEngine


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')
    album = client.get_album_detail(album_id)
    client.check_photo(album[0])
    images = list(album[0])[:5]

    tmp = tempfile.mkdtemp(prefix='jmprof-')
    engine = JmEngine(log=lambda s: None)

    print('== 完整（下载+解码+读入内存）==')
    for img in images:
        t0 = time.time()
        blob = engine._fetch_bytes(client, img, tmp)
        print(f'  {img.img_file_name}{img.img_file_suffix}  {len(blob):>7} B  {time.time() - t0:5.2f}s')

    print('\n== 只下载不落盘（原始响应）==')
    for img in images:
        t0 = time.time()
        resp = client.get_jm_image(img.download_url)
        raw = resp.content
        print(f'  {img.img_file_name}  {len(raw):>7} B  {time.time() - t0:5.2f}s')

    print('\n== 解码耗时 ==')
    for img in images:
        resp = client.get_jm_image(img.download_url)
        t0 = time.time()
        num = JmImageTool.get_num_by_detail(img)
        pic = JmImageTool.open_image(resp.content)
        t_open = time.time() - t0
        t1 = time.time()
        out = os.path.join(tmp, 'x.png')
        JmImageTool.decode_and_save(num, pic, out)
        print(f'  {img.img_file_name}  seg={num}  open={t_open * 1000:6.1f}ms  '
              f'decode_save={(time.time() - t1) * 1000:6.1f}ms  size={pic.size}')

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
