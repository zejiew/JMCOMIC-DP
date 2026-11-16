"""车号解析测试。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.ids import (looks_like_id, parse_album_id, parse_album_ids,
                       try_parse_album_id)


def main():
    ok = True

    def check(label, got, want):
        nonlocal ok
        passed = got == want
        print(('PASS ' if passed else 'FAIL ') + f'{label:<28} → {got!r}'
              + ('' if passed else f'（期望 {want!r}）'))
        if not passed:
            ok = False

    singles = [
        ('123456', '123456'),
        ('  123456  ', '123456'),
        ('JM123456', '123456'),
        ('jm123456', '123456'),
        ('JM 123456', '123456'),
        ('JM-123456', '123456'),
        ('[123456]', '123456'),
        ('【123456】', '123456'),
        ('(123456)', '123456'),
        ('https://18comic.vip/album/123456/', '123456'),
        ('https://18comic.vip/album/123456', '123456'),
        ('https://www.cdngwc.cc/album?id=123456', '123456'),
        ('https://18comic.org/comic/123456', '123456'),
        ('https://18comic.vip/photo/987654', '987654'),
        ('https://example.com/x?foo=1&id=555', '555'),
    ]
    for raw, want in singles:
        check(f'解析 {raw[:24]}', parse_album_id(raw), want)

    # 一批
    check('批量（逗号分隔）',
          parse_album_ids('123456,789012'), ['123456', '789012'])
    check('批量（空格/逗号/顿号混用）',
          parse_album_ids('111111  222222,333333、444444'),
          ['111111', '222222', '333333', '444444'])
    check('批量（含链接）',
          parse_album_ids('111111 https://18comic.vip/album/222222/'),
          ['111111', '222222'])
    check('批量去重', parse_album_ids('111111 111111 222222'), ['111111', '222222'])
    check('批量忽略空项', parse_album_ids(' 111111 , , 222222 '), ['111111', '222222'])

    # 容错
    check('解析失败给空', try_parse_album_id('这只是一段文字'), '')
    check('太短的数字不当 ID', try_parse_album_id('12'), '')

    # 判断像不像车号
    check('looks_like_id 纯数字', looks_like_id('123456'), True)
    check('looks_like_id JM 前缀', looks_like_id('JM123456'), True)
    check('looks_like_id 链接', looks_like_id('https://a/album/1/'), True)
    check('looks_like_id 中文词', looks_like_id('秘密教學'), False)
    check('looks_like_id 短英文', looks_like_id('naruto'), False)

    # 异常
    try:
        parse_album_id('')
        print('FAIL 空输入应抛异常')
        ok = False
    except ValueError:
        print('PASS 空输入抛 ValueError')

    try:
        parse_album_id('完全没有数字')
        print('FAIL 无数字应抛异常')
        ok = False
    except ValueError:
        print('PASS 无数字抛 ValueError')

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
