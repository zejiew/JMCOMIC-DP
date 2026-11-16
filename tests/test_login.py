"""账号密码登录路径的测试。

这个用例专门盯着一个曾经踩过的坑：``option.auth`` 是 jmcomic 的 AdvancedDict，
它的 ``__getattr__`` 会把 ``.update()`` 这类方法名当成 key 去查，从而抛 KeyError。
所以登录必须逐键赋值。

联网部分只在 --live 时跑（需要一个真实账号）。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.engine import JmEngine, friendly_error


def main():
    ok = True

    def check(label, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label + (f'  {extra}' if extra else ''))
        if not cond:
            ok = False

    # 1. 空账号要在本地就被拦下（不发网络请求）
    engine = JmEngine(log=lambda s: None)
    for bad in [('', ''), ('user', ''), ('', 'pass')]:
        try:
            engine.login(*bad)
            check(f'空参数应报错 {bad}', False)
        except ValueError:
            check(f'空参数本地拦截 {bad}', True)

    # 2. 构造 option 时不因 auth 赋值方式报错（离线可测）
    from jmcomic import JmOption
    try:
        option = JmOption.construct({
            'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
            'download': {'threading': {'image': 1, 'photo': 1}},
        }, cover_default=True)
        # 就是这两行以前会炸
        option.auth.username = 'someone'
        option.auth.password = 'secret'
        check('auth 逐键赋值不报错', option.auth.get('username') == 'someone',
              str(option.auth.get('username')))
    except Exception as exc:
        check('auth 逐键赋值不报错', False, f'{type(exc).__name__}: {exc}')

    # 2b. 反过来确认 .update() 确实是坑（防止有人"顺手优化"回去）
    bad_threw = False
    try:
        option.auth.update({'username': 'x'})
    except KeyError:
        bad_threw = True
    except Exception:
        bad_threw = True
    check('记录：.update() 会炸（提醒不要改回去）', bad_threw)

    # 3. friendly_error 能把 401 翻成人话
    msg = friendly_error(RuntimeError('{"code":401,"errorMsg":"無效的用戶名和/或密碼！"}'))
    check('401 翻译', '登录' in msg, msg)

    # 4. 真账号登录（可选）
    user = os.environ.get('JM_USER')
    pwd = os.environ.get('JM_PASS')
    if '--live' in sys.argv and user and pwd:
        engine = JmEngine(log=lambda s: None)
        try:
            info = engine.login(user, pwd)
            check('真实账号登录', bool(info.get('user_id')), str(info.get('user_id')))
            folders = engine.list_folders()
            check('登录后可读收藏夹', len(folders) > 0, f'{len(folders)} 个')
        except Exception as exc:
            check('真实账号登录', False, friendly_error(exc))
    else:
        print('（跳过真实账号登录：设 JM_USER / JM_PASS 并加 --live 才跑）')

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
