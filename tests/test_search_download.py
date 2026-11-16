"""联网测试：搜索 → 勾选 → 下载，并验证命名。"""

import os
import sys
import tempfile
import threading
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jmfav.gui as gui_mod
from jmfav.paths import CONFIG_PATH


class _SilentBox:
    def __getattr__(self, _name):
        return lambda *a, **k: None

    def askyesno(self, *a, **k):
        return True


gui_mod.messagebox = _SilentBox()
from jmfav.gui import JmApp  # noqa: E402


def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else '秘密'
    out_dir = tempfile.mkdtemp(prefix='jmsearch-')

    backup = None
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'rb') as fp:
            backup = fp.read()

    app = JmApp()
    app.var_output.set(out_dir)
    app.var_threads.set('12')
    app.var_search.set(keyword)

    from jmcomic import JmOption
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    app.engine.client = option.new_jm_client(impl='api')

    ok = True
    app._do_search(reset=True)

    deadline = time.time() + 90
    while time.time() < deadline and not app.tab_search.albums:
        app.update()
        time.sleep(0.1)
    app.update()

    print('搜索结果:', len(app.tab_search.albums), '条')
    print('分页信息:', app.var_search_info.get())
    if not app.tab_search.albums:
        print('FAIL 搜索没有结果')
        app.destroy()
        return 1

    rows = app.tab_search.tree.get_children()
    print('列表行数:', len(rows))
    sample = [app.tab_search.tree.item(r)['values'] for r in rows[:3]]
    for v in sample:
        print('  ', v[1], '←', str(v[2])[:46])

    if not any(v[1] and not str(v[1]).startswith('JM') for v in sample):
        print('FAIL 命名预览没提取作品名')
        ok = False

    # 只下第一个，省时间
    first = app.tab_search.albums[0]
    app._check_only(first.album_id, app.tab_search)
    picked = app.tab_search.picked()
    print('勾选:', [a.album_id for a in picked])

    ev = threading.Event()
    real = app._on_download_done

    def hook(results):
        real(results)
        ev.set()

    app._on_download_done = hook
    app._launch_download(picked, out_dir)

    deadline = time.time() + 240
    while not ev.is_set() and time.time() < deadline:
        app.update()
        time.sleep(0.1)

    files = [f for f in os.listdir(out_dir) if f.endswith('.zip')]
    if files:
        with zipfile.ZipFile(os.path.join(out_dir, files[0])) as zf:
            print('产出:', files[0], '| 条目', len(zf.namelist()))
    else:
        print('FAIL 没有产出')
        ok = False

    app._busy = False
    app.destroy()
    try:
        if backup is None:
            if os.path.exists(CONFIG_PATH):
                os.remove(CONFIG_PATH)
        else:
            with open(CONFIG_PATH, 'wb') as fp:
                fp.write(backup)
    except OSError:
        pass

    print('RESULT:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
