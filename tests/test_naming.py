import sys
sys.path.insert(0, '.')
from jmfav.naming import build_archive_name, truncate_title, sanitize_filename

t = ('[無邪氣漢化組] (C99) [紺色果實 (紺菓)] サレンの樂しい夢 '
     '(プリンセスコネクト!Re:Dive) [中國翻譯] [無修正] [DL版]')
out = r'C:\Users\zejiew\Desktop\jm下载\downloads'

print('1)', build_archive_name(t, max_chars=20, output_dir=out, album_id='123456'))
print('2)', build_archive_name(t, max_chars=60, output_dir=out, album_id='123456'))
print('3)', build_archive_name('a/b:c*?"<>|', max_chars=0, album_id='9'))
print('4)', build_archive_name('CON', max_chars=0, album_id='9'))
print('5)', build_archive_name('', max_chars=0, album_id='9'))
print('6)', build_archive_name(t, max_chars=30, template='{id} {title}', album_id='777'))
print('7) len =', len(build_archive_name('字' * 300, max_chars=0, output_dir=out)))
print('8)', truncate_title('abc...', 4))
print('9)', repr(truncate_title('短标题', 60)))
print('10)', sanitize_filename('  name.  '))
