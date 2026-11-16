"""所有测试一次跑完。

用法：
    python tests/run_all.py           # 只跑离线用例
    python tests/run_all.py --live    # 连联网用例一起跑
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable

OFFLINE = [
    ('命名规则', 'test_naming.py'),
    ('标题提取', 'test_title.py'),
    ('车号解析', 'test_ids.py'),
    ('作者水印', 'test_credit.py'),
    ('登录路径', 'test_login.py'),
    ('下载链路', 'test_pipeline.py'),
    ('边界用例', 'test_edge_cases.py'),
    ('界面渲染', 'test_gui_smoke.py'),
    ('界面交互', 'test_interactions.py'),
    ('界面布局', 'test_layout.py'),
    ('小屏适配', 'test_small_screen.py'),
]

LIVE = [
    ('解码正确性', 'test_decode_correct.py'),
    ('站内搜索', 'test_search_live.py'),
    ('整本下载', 'smoke_full_album.py'),
    ('界面下载', 'test_gui_download.py'),
    ('车号下载', 'test_id_download.py'),
    ('搜索下载', 'test_search_download.py'),
]

KEEP = ('PASS', 'FAIL', 'RESULT', '===', '共 ', '条目', '文件:', '产出', '结果',
        '目标', '子目录', '搜索结果', '分页', '命名预览', '车号')


def run_one(title, script, env):
    print(f'\n=== {title} ===', flush=True)
    started = time.time()
    try:
        proc = subprocess.run(
            [PY, os.path.join(HERE, script)], cwd=ROOT, env=env,
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=900,
        )
        out = (proc.stdout or '') + (proc.stderr or '')
        code = proc.returncode
    except subprocess.TimeoutExpired:
        print('  超时（900 秒）')
        return False, 900.0

    lines = [ln for ln in out.splitlines() if any(k in ln for k in KEEP)]
    print('\n'.join(lines[-25:]) if lines else out[-1000:])
    cost = time.time() - started
    print(f'  （用时 {cost:.1f}s）')
    return code == 0, cost


def main():
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    suites = list(OFFLINE)
    if '--live' in sys.argv:
        suites += LIVE

    results = []
    for title, script in suites:
        ok, cost = run_one(title, script, env)
        results.append((title, ok, cost))

    print('\n' + '=' * 46)
    for title, ok, cost in results:
        print(f'{"PASS" if ok else "FAIL"}  {title:<14} {cost:6.1f}s')
    bad = [t for t, ok, _ in results if not ok]
    total = sum(c for _, _, c in results)
    print(f'\n共 {len(results)} 组，失败 {len(bad)} 组，总用时 {total:.1f}s')
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main())
