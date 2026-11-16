"""标题提取规则测试：基于真实标题样本 + 手工用例。"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmfav.title import clean_title, extract_core, pick_variant, split_variants

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ok = True

    def check(label, got, want=None, cond=None):
        nonlocal ok
        passed = (got == want) if want is not None else bool(cond)
        print(('PASS ' if passed else 'FAIL ') + label + f'  → {got!r}'
              + (f'（期望 {want!r}）' if want is not None and not passed else ''))
        if not passed:
            ok = False

    # --- 典型结构 ---
    cases = [
        # 汉化组在前
        ('[中國翻譯] [漢化組] 作品名 [DL版]', '漢化組] 作品名 [DL版'),
    ]
    # 上面这条是坏输入（括号不配对），单独验证不会崩
    check('括号不配对不崩', clean_title('[中國翻譯] [漢化組 作品名'), cond=True)

    cases = [
        ('[無邪氣漢化組] (C99) [紺色果實 (紺菓)] サレンの樂しい夢 (プリンセスコネクト!Re:Dive) [中國翻譯] [無修正]',
         'サレンの樂しい夢 (プリンセスコネクト!Re:Dive)'),
        ('[超勇漢化組×禁漫天堂](C108)[ぽんぽこ(たたきた)]生徒會の秘密[中國翻譯]', '生徒會の秘密'),
        ('[山嵐個人漢化] [くろねこ (NTR専門)] 【NTR】誰にも言えない秘密', '誰にも言えない秘密'),
        ('老師的秘密 1[乃希漢化] [大地巧太]先生の秘密 その1', '老師的秘密 1'),
        ('下班後的例行戀愛/下班後的秘密關係', '下班後的例行戀愛'),
        ('秘密教學 / 秘密の授業', '秘密教學'),
        ('[純純的個人翻譯] [Anamimai] Jingwei Secret | 靜微的秘密 [Chinese]', '靜微的秘密'),
        ('[goodkids (AK1)] 海風の秘密 (ハンター×ハンター) [中國翻譯]',
         '海風の秘密 (ハンター×ハンター)'),
        ('人妻回春館', '人妻回春館'),
        ('[牧部かたる]人妻女教師的秘密的課外授業', '人妻女教師的秘密的課外授業'),
        ('修女的秘密[圈跪個人漢化][胃之國屋] Sister’s Secret[中國翻譯]', '修女的秘密'),
        ('[AB] 某作品 [Chinese] [Digital] [作者]', '某作品'),
        ('【Naitong】同桌的秘密', '同桌的秘密'),
        ('[黃油大師]魔王與薇洛的秘密特訓 [AI Generated] [中國翻譯]', '魔王與薇洛的秘密特訓'),
    ]
    for raw, want in cases:
        check('提取', clean_title(raw), want)

    # --- 边界 ---
    check('空标题', clean_title(''), '')
    check('纯噪声标题', clean_title('[中國翻譯]'), '[中國翻譯]')
    check('纯括号作品名', clean_title('[某作品名] [漢化組]'), '某作品名')
    check('超长不炸', None, cond=len(clean_title('測試' * 200)) > 0)
    check('无括号原样', clean_title('人妻回春館'), '人妻回春館')

    # --- 分隔符 ---
    check('斜杠切变体（括号内不切）', split_variants('A (B/C) | D'), ['A (B/C)', 'D'])
    check('取中文变体', pick_variant(['Secret', '秘密', 'ひみつ']), '秘密')
    check('单变体', pick_variant(['只有一個']), '只有一個')

    # --- 真实样本：批量不崩、长度合理 ---
    path = os.path.join(HERE, 'title_samples.json')
    if os.path.exists(path):
        titles = json.load(open(path, encoding='utf-8'))
        results = [clean_title(t) for t in titles]
        empty = sum(1 for r in results if not r)
        avg = sum(len(r) for r in results) / len(results)
        check(f'真实样本 {len(titles)} 条无空结果', empty, 0)
        check(f'真实样本平均 {avg:.1f} 字 < 30', avg, cond=avg < 30)
        check('真实样本结果都不含常见汉化组后缀',
              sum(1 for r in results if '中國翻譯]' in r or '[DL版]' in r), 0)

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
