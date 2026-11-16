"""用真实标题样本评估 title.clean_title 的效果。"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from jmfav.title import clean_title

titles = json.load(open(os.path.join(HERE, 'title_samples.json'), encoding='utf-8'))

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0
rows = []
for t in (titles[:limit] if limit else titles):
    r = clean_title(t)
    rows.append((len(r), r, t))

bad = [x for x in rows if x[0] > 45]
print(f'共 {len(rows)} 条，超 45 字的 {len(bad)} 条\n')
print('=== 超长的 ===')
for ln, r, t in bad[:20]:
    print(f'  [{ln}] {r[:90]}')
    print(f'       ← {t[:100]}')

print('\n=== 抽样（前 40）===')
for ln, r, t in rows[:40]:
    print(f'  {ln:>3} {r:<44} | {t[:70]}')

avg = sum(x[0] for x in rows) / len(rows)
print(f'\n平均长度 {avg:.1f} 字；最长 {max(x[0] for x in rows)} 字；'
      f'空结果 {sum(1 for x in rows if not x[1])} 条')
