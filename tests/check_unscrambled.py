"""验证：不解扰的图（num == 0）可以直接存原始字节，零重编码成本。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption, JmImageTool

from jmfav.codec import decode_scramble, encode_image


def main():
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')

    # 找一个老本子（aid 小于 scramble_id 就不用解扰）
    album = client.get_album_detail(sys.argv[1] if len(sys.argv) > 1 else '1114751')
    print('scramble_id =', album.scramble_id, '| aid =', album.album_id)
    client.check_photo(album[0])

    zero, nonzero = 0, 0
    for img in list(album[0])[:30]:
        num = JmImageTool.get_num_by_detail(img)
        if num == 0:
            zero += 1
        else:
            nonzero += 1
    print(f'前 30 张：需解扰 {nonzero} 张，无需解扰 {zero} 张')

    # 取一张 num==0 的看看直接存原字节是否可行
    for img in list(album[0])[:30]:
        num = JmImageTool.get_num_by_detail(img)
        if num == 0:
            raw = client.get_jm_image(img.download_url).content
            pic = decode_scramble(raw, 0)
            print(f'\n样品 {img.img_file_name}: 原字节 {len(raw)}B, 尺寸 {pic.size}')
            print('  直接存原字节 → 100% 体积、零耗时')
            for fmt in ('webp', 'jpeg', 'png'):
                data, sfx = encode_image(pic, fmt)
                print(f'  重编码 {fmt:<5}: {len(data):>8}B ({len(data) / len(raw) * 100:5.0f}%)')
            break


if __name__ == '__main__':
    main()
