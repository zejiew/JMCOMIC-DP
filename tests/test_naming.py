"""命名规则测试：作者前缀、截断、非法字符、路径限长。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.naming import (author_tagged, build_archive_name, clean_author,
                          sanitize_filename, truncate_title)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'downloads')
LONG = ('[無邪氣漢化組] (C99) [紺色果實 (紺菓)] サレンの樂しい夢 '
        '(プリンセスコネクト!Re:Dive) [中國翻譯] [無修正] [DL版]')


def main():
    ok = True

    def check(label, got, want):
        nonlocal ok
        passed = got == want
        print(('PASS ' if passed else 'FAIL ') + label + f'  → {got!r}'
              + (f'（期望 {want!r}）' if not passed else ''))
        if not passed:
            ok = False

    # --- 作者清洗 ---
    check('作者正常', clean_author('紺菓'), '紺菓')
    check('作者为空', clean_author(''), '')
    check('占位作者丢弃', clean_author('default_author'), '')
    check('未知作者丢弃', clean_author('[未知]'), '')
    check('多作者只留第一个', clean_author('甲, 乙'), '甲')

    # --- 作者前缀 ---
    check('加作者前缀', author_tagged('作品名', '紺菓'), '[紺菓] 作品名')
    check('作者已在标题里不重复', author_tagged('紺菓的作品', '紺菓'), '紺菓的作品')
    check('没作者就不加', author_tagged('作品名', ''), '作品名')
    check('占位作者不加', author_tagged('作品名', 'default_author'), '作品名')

    # --- 完整命名 ---
    check('默认带作者',
          build_archive_name('作品名', max_chars=60, album_id='1', author='紺菓'),
          '[紺菓] 作品名')
    check('没作者只有作品名',
          build_archive_name('作品名', max_chars=60, album_id='1'),
          '作品名')
    check('模板里写 {author} 不重复',
          build_archive_name('作品名', template='{title} - {author}',
                             album_id='1', author='紺菓'),
          '作品名 - 紺菓')
    check('完整原标题模式不加作者前缀',
          build_archive_name('原作标题', name_mode='full', raw_title='[漢化] 原作标题',
                             album_id='1', author='紺菓'),
          '[漢化] 原作标题')
    check('截断只算作品名（作者不占字数）',
          build_archive_name('标题' * 40, max_chars=10, album_id='1', author='紺菓'),
          '[紺菓] ' + '标题' * 5)
    check('空标题兜底不挂作者',
          build_archive_name('', max_chars=60, album_id='9', author='紺菓'),
          'JM9')

    # --- 非法字符 / 截断 / 路径 ---
    check('非法字符换全角',
          build_archive_name('a/b:c*?"<>|', max_chars=0, album_id='9'),
          'a／b：c＊？＂＜＞｜')
    check('保留设备名加前缀',
          build_archive_name('CON', max_chars=0, album_id='9', author_in_name=False),
          '_CON')
    check('截断不留结尾标点', truncate_title('abc...', 4), ('abc', True))
    check('不必截断', truncate_title('短标题', 60), ('短标题', False))
    check('清理首尾空白与点', sanitize_filename('  name.  '), 'name')
    check('超长路径兜底',
          len(build_archive_name('字' * 300, max_chars=0, output_dir=OUT)) <= 240,
          True)

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
