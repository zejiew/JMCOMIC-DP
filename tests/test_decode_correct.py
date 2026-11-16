"""解码正确性测试：把内存解码结果与 jmcomic 官方 decode_and_save 逐像素比对。"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption, JmImageTool
from PIL import Image, ImageChops

from jmfav.codec import decode_scramble


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')
    album = client.get_album_detail(album_id)
    client.check_photo(album[0])
    images = list(album[0])[:6]

    tmp = tempfile.mkdtemp(prefix='jmcmp-')
    ok = True
    for img in images:
        raw = client.get_jm_image(img.download_url).content
        num = JmImageTool.get_num_by_detail(img)

        # 官方路径
        ref_path = os.path.join(tmp, 'ref.png')
        JmImageTool.decode_and_save(num, JmImageTool.open_image(raw), ref_path)

        # 我们的内存路径
        mine = decode_scramble(raw, num)

        ref = Image.open(ref_path).convert('RGB')
        diff = ImageChops.difference(ref, mine)
        bbox = diff.getbbox()
        same = bbox is None
        print(f'  {img.img_file_name} seg={num:>2} size={mine.size} '
              f'{"一致" if same else f"不一致 bbox={bbox}"}')
        ok = ok and same

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print('RESULT:', 'OK' if ok else 'MISMATCH')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
