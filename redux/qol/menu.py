"""ReRedux intro settings menu (no C code): shown once at the start of a new game, it sets the
rules.c flags/vars, the difficulty, the city and the QoL switches (speed.c / turbo.c read flags
0x5DA/0x5DB, set = OFF). Also: gift scripts skip the "Give a nickname?" yes/no when "always nickname"
is on, and the Aspertia key bearer no longer hands out keys (the Key System is out of play: what
the keys chose is asked here; rules.py makes Unova Link refuse difficulty / City Key changes).

Script patches (data files, files(ctx)), append-only (original bytes stay in place, see below):
  zone 427 Aspertia City (a/0/5/6 script 854) scr_29, the opening cutscene that runs on the first
  field frame after the intro: its header entry -> appended `ActorPauseAll; VMCall @rules_menu;
  VMJump back`; the menu runs while var 0x4197 is 0 and sets it to 1 on Start. Texts: story bank 169
  (zone 427's), TEXTS below.
  zone 427 scr_34 (Redux's key bearer): his three CallUnovaLinkKeyUnlock (Easy, Challenge, City Key)
  are skipped and his first line says the rules were set at the start; his other gifts (flags,
  National Pokédex, the save) stay.
  gifts (13 scripts: 12 zones incl. the starter in 427, common 1253): every `YesNoWin V` whose YES
  branch (`StackPush V; StackPushConst 0; StackCmp 1; VMJumpIf` falls through on YES) reaches
  CallPokeNameInput within a few commands (one VMCall level) gets
  `if (flag 0x5D6) { V = 0 } else { YesNoWin V }`.

Menu (list menus with a hint per row in the system window; pages have <= 7 rows because B2's list
menu mis-restores a cursor below row 4 of a scrolling list):
  main: "Difficulty: Challenge" · "City: Black City" · "Nuzlocke: Off/Classic/Custom" ·
        "Catch rules: Off/N on" · "Items: Normal/..." · "Speed: Default/Custom" · Start the adventure!
  Every setting row ("Name: Value") opens a picker listing all its values, the current one marked ●
  (and under the cursor), with a hint per value; A picks, B keeps the value. The cursor comes back
  to the row it was on. Category pages (B or Back returns):
  Nuzlocke: Use Classic Nuzlocke preset… (lists what it turns on, asks yes/no) · Fainted:
            Kept/Released/Graveyard · Game over · Always nickname
  Catch rules: First catch only · Dupes clause · Species limit (Off / Same species / Same evolution
               line, var 0x4199) · Shiny clause · Statics count
  Items: No battle items · No trainer items
  Speed: Speed-ups · Turbo button · Auto-run (0x5DC, set = OFF) · Quick save (0x5DD) · Quick Surf
         (0x5DE) (the last three are read by qol2.c / qol2.py / fastsave.c)
  Start the adventure!: a recap (difficulty and city, then each category that isn't at its default),
  "Start ... with these rules? They can't be changed later." yes/no -> RulesCmd 0 (difficulty) and 5
  (city: 0 Black City + Black Tower, 1 White Forest + White Treehollow; var 0x419A).
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as R

ZONE_SCRIPT = 854          # a/0/5/6: zone 427 Aspertia City's event script
ZONE_TEXT = 169            # a/0/0/3: zone 427's text bank
KEYBEARER_LINE = 10        # zone 427 text: "Welcome, welcome! I am the key bearer! The keys, I shall grant..."
T_RES, T_CUR, T_SUB, T_PCUR = 0x8024, 0x8025, 0x8026, 0x8027   # script temporaries: result, cursors
T_A, T_B, T_C, T_D = 0x8028, 0x8029, 0x802A, 0x802B             # summary / recap codes
F = R.FLAGS
V_DONE, V_DIFF, V_LIMIT, V_CITY = R.VAR_MENU_DONE, R.VAR_DIFFICULTY, R.VAR_SPECIES_LIMIT, R.VAR_CITY
CUR = '●'                  # marks the current value in a picker (a glyph of both fonts)


def S(en, ja):
    return dict(en=en, ja=ja)


T = {
    'INTRO': S('Before your journey begins,\nchoose the rules for your adventure!',
               '冒険を　始める　前に\nこの　冒険の　ルールを　決めよう！'),
    'PROMPT': S('Choose a setting to change it.', '変えたい　項目を　選んでください'),
    'PICK': S('Choose a value.\nB: keep the current one.', '設定を　選んでください\nＢボタン：そのまま'),
    'CONFIRM': S("Press SELECT in the field to see\nthese settings again.{BE01}\n"
                 "Start the adventure with these\nrules? They can't be changed later.",
                 'セレクトボタンで　いつでも\nこの　設定を　見られます{BE01}\n'
                 'この　ルールで　冒険を　始めますか？\nあとから　変えられません'),
    'DONE': S('Start the adventure!', '冒険を　始める！'),
    'H_DONE': S("Check your rules and start.\nThey can't be changed later.",
                'ルールを　確認して　冒険を　始めます\nあとから　変えられません'),
    'BACK': S('Back', 'もどる'),
    'H_BACK': S('Back to the main menu.', '前の　メニューに　戻ります'),
    'PRESET': S('Use Classic Nuzlocke preset...', 'おまかせ　ナズロックを　使う…'),
    'H_PRESET': S('Shows the rules it turns on,\nthen asks before changing them.',
                  'オンに　なる　ルールを　見せてから\n使うか　どうか　ききます'),
    'PRESET_ASK': S('The Classic Nuzlocke preset sets:\nFainted: Released, Game over,{BE01}\n'
                    'Always nickname, First catch only,\nDupes clause and Shiny clause.{BE01}\n'
                    'Use the Classic Nuzlocke preset?',
                    'おまかせ　ナズロックで　オンに\nなる　ルール：{BE01}\nひんし：にがす　ゲームオーバー\n'
                    '必ず　ニックネーム{BE01}\n最初の　１匹だけ　ダブり　なし\n色違い　とくべつ{BE01}\n'
                    'おまかせ　ナズロックを\n使いますか？'),
    'KEYBEARER': S('Welcome, welcome!\nI am the key bearer!{BE01}\nBut your rules were chosen at the\n'
                   'start, so no keys are needed!{BE01}\nMy other gifts, I shall grant to you!\n'
                   'Then off, I shall go!{BE01}',
                   'ようこそ！　わたしは\nカギを　さずける　者！{BE01}\nだが　ルールは　もう　決まっている\n'
                   'カギは　いらないね！{BE01}\nかわりに　ほかの　おくりものを\nさずけよう！{BE01}'),
}

# --- settings: picker values (label, hint) ------------------------------------------------------------
# kind: 'var' (value = var), 'flag' (index 0 = On, 1 = Off; inv: flag set = OFF), 'faint' (Kept /
# Released / Graveyard over flags release + graveyard)
SETTINGS = {
    'DIFF': dict(kind='var', var=V_DIFF, name=S('Difficulty', 'むずかしさ'),
                 hint=S("Easy, Normal or Challenge Mode:\nhow strong trainers' Pokémon are.",
                        'トレーナーとの　勝負の\nむずかしさを　選びます'),
                 vals=[(S('Easy Mode', 'アシストモード'), S("Trainers' Pokémon are weaker.",
                                                              'トレーナーの　ポケモンが\n弱く　なります')),
                       (S('Normal Mode', 'ノーマルモード'), S("Black 2's normal difficulty.",
                                                              'ふつうの　むずかしさです')),
                       (S('Challenge Mode', 'チャレンジモード'),
                        S("Trainers' Pokémon are stronger.\nRedux's recommended mode.",
                          'トレーナーの　ポケモンが\n強く　なります'))],
                 rows=[S('Difficulty: Easy', 'むずかしさ：アシスト'), S('Difficulty: Normal', 'むずかしさ：ノーマル'),
                       S('Difficulty: Challenge', 'むずかしさ：チャレンジ')]),
    'CITY': dict(kind='var', var=V_CITY, name=S('City', 'まち'),
                 hint=S('Postgame: Black City and Black Tower,\nor White Forest and White Treehollow.',
                        'クリア後に　行ける　場所です\nブラックシティか　ホワイトフォレスト'),
                 vals=[(S('Black City', 'ブラックシティ'), S("Black City and Black Tower\n(Black 2's own).",
                                                             'ブラックシティと　ブラックタワー\n（ブラック２と　同じ）')),
                       (S('White Forest', 'ホワイトフォレスト'),
                        S('White Forest and White Treehollow\n(as in White 2).',
                          'ホワイトフォレストと\nホワイトツリーホロウ（ホワイト２）'))],
                 rows=[S('City: Black City', 'まち：ブラックシティ'), S('City: White Forest', 'まち：ホワイトフォレスト')]),
    'FAINT': dict(kind='faint', name=S('Fainted', 'ひんし'),
                  hint=S('After a battle, fainted Pokémon\nare released or put in the last Box.',
                         'ひんしの　ポケモンは　勝負の　あと\nにがすか　最後の　ボックスへ'),
                  vals=[(S('Kept', 'そのまま'), S('Fainted Pokémon stay with you.', 'ひんしの　ポケモンは　そのまま')),
                        (S('Released', 'にがす'), S('After a battle, fainted Pokémon\nare released.',
                                                    '勝負の　あと　ひんしの\nポケモンを　にがします')),
                        (S('Graveyard', 'おはかボックス'),
                         S('After a battle, fainted Pokémon\ngo to the last PC Box (graveyard).',
                           '勝負の　あと　ひんしの　ポケモンは\n最後の　ボックスへ'))],
                  rows=[S('Fainted: Kept', 'ひんし：そのまま'), S('Fainted: Released', 'ひんし：にがす'),
                        S('Fainted: Graveyard', 'ひんし：おはかボックス')]),
    'LIMIT': dict(kind='var', var=V_LIMIT, name=S('Species limit', 'しゅるい　せいげん'),
                  hint=S('One Pokémon per species (or per\nevolution line) in your party and PC.',
                         '手持ちと　ボックスに　同じ\nポケモンは　１匹だけ'),
                  vals=[(S('Off', 'オフ'), S('No species limit.', 'しゅるいの　せいげんは　ありません')),
                        (S('Same species', '同じ　しゅるい'),
                         S("You can't catch a species you\nalready have (party or PC).",
                           '手持ちや　ボックスに　いる\nしゅるいは　つかまえられません')),
                        (S('Same evolution line', '進化の　なかま'),
                         S("You can't catch a Pokémon whose\nevolution line you already have.",
                           '進化の　なかまが　いる　ポケモンは\nつかまえられません'))],
                  rows=[S('Species limit: Off', 'しゅるい　せいげん：オフ'),
                        S('Species limit: Same species', 'しゅるい　せいげん：同じ　しゅるい'),
                        S('Species limit: Evolution line', 'しゅるい　せいげん：進化の　なかま')]),
}
TOGGLES = [   # (key, flag, inverted (flag set = OFF), en label, ja label, en hint, ja hint)
    ('GAMEOVER', 'gameover', False, 'Game over', 'ゲームオーバー',
     'If all your Pokémon faint, the game\nis over: back to the title screen.',
     '手持ちが　全員　ひんしに　なると\nタイトル画面に　戻ります'),
    ('FIRST', 'first', False, 'First catch only', '最初の　１匹だけ',
     'Only the first wild Pokémon you\nmeet in each area can be caught.',
     'それぞれの　場所で　最初に　出会った\n野生の　ポケモンだけ　つかまえられる'),
    ('DUPES', 'dupes', False, 'Dupes clause', 'ダブり　なし',
     "Species you've caught don't count\nas the area's encounter.",
     'つかまえた　ことの　ある　ポケモンは\n数えず　つかまえられません'),
    ('SHINY', 'shiny', False, 'Shiny clause', '色違い　とくべつ',
     'Shiny Pokémon can always be\ncaught and never use the area.',
     '色違いの　ポケモンは\nいつでも　つかまえられます'),
    ('STATICS', 'statics', False, 'Statics count', '固定も　数える',
     'Legendary and Hidden Grotto\nbattles count as encounters.',
     '伝説の　ポケモンや　隠し穴の\nポケモンも　出会いに　数えます'),
    ('NICK', 'nickname', False, 'Always nickname', '必ず　ニックネーム',
     'Give a nickname to every Pokémon\nyou catch or receive.',
     'つかまえたり　もらった　ポケモンに\n必ず　ニックネームを　つけます'),
    ('NOITEMS', 'noitems', False, 'No battle items', '勝負中の　道具なし',
     "You can't use items in battle.\nPoké Balls still work.",
     '勝負中に　道具が　使えません\nモンスターボールは　使えます'),
    ('NOTRITEMS', 'notraineritems', False, 'No trainer items', 'トレーナーの　道具なし',
     "Trainers you battle don't\nuse any items.",
     'トレーナーが　勝負中に\n道具を　使わなくなります'),
    ('SPEED', 'speed_off', True, 'Speed-ups', '高速化',
     'Faster text, battles and animations.',
     '文字や　バトルの　演出が\n速く　なります'),
    ('TURBO', 'turbo_off', True, 'Turbo button', 'ターボボタン',
     'Press R in the field or in battle\nto switch 2x game speed on/off.',
     'Ｒボタンで　２ばいの　はやさに\nしたり　もとに　もどしたり　できます'),
    ('AUTORUN', 'autorun_off', True, 'Auto-run', 'いつも　はしる',      # qol2.c
     'Run without holding B.\nHold B to walk.',
     'Ｂボタンを　おさなくても　はしります\nＢボタンを　おすと　あるきます'),
    ('QSAVE', 'quicksave', False, 'Quick save', 'すぐに　レポート',
     'Save from the menu at once,\nwithout the yes/no question.',
     'メニューの　レポートで\nはい・いいえを　きかずに　かきます'),
    ('QSURF', 'quicksurf', False, 'Quick Surf', 'すぐに　なみのり',
     'Press A at water to Surf at once,\nwithout the yes/no question.',
     'みずに　むかって　Ａボタンで\nきかずに　すぐ　なみのり　します'),
]
for key, flag, inv, en, ja, hen, hja in TOGGLES:
    SETTINGS[key] = dict(kind='flag', flag=F[flag], inv=inv, name=S(en, ja), hint=S(hen, hja),
                         vals=[(S('On', 'オン'), S(hen, hja)),
                               (S('Off', 'オフ'), S(f'{en}: off.', f'{ja}：オフ'))],
                         rows=[S(en + ': ON', ja + '：オン'), S(en + ': OFF', ja + '：オフ')])

# main-row summaries (computed in the script, see Gen.summaries) and their texts
SUMMARY = {
    'NUZ': dict(hint=S('Hard rules: lose fainted Pokémon,\ngame over, always nickname.',
                       'ひんしの　ポケモンを　失う　など\nきびしい　ルールで　遊べます'),
                rows=[S('Nuzlocke: Off', 'ナズロック：オフ'), S('Nuzlocke: Classic', 'ナズロック：クラシック'),
                      S('Nuzlocke: Custom', 'ナズロック：カスタム')]),
    'ENC': dict(hint=S('One catch per area, dupes clause,\nspecies limit, shiny clause, statics.',
                       '場所ごとに　１匹だけ　など\nつかまえる　ときの　ルールです'),
                rows=[S('Catch rules: Off', 'つかまえる　ルール：オフ')] +
                     [S(f'Catch rules: {n} on', f'つかまえる　ルール：{"１２３４５"[n - 1]}つ') for n in range(1, 6)]),
    'ITEMS': dict(hint=S('Turn off items in battle for you\nor for the trainers you battle.',
                         '勝負中に　自分や　トレーナーが\n道具を　使えなく　なります'),
                  rows=[S('Items: Normal', '道具：ふつう'), S('Items: No battle items', '道具：勝負中は　なし'),
                        S('Items: No trainer items', '道具：トレーナーは　なし'),
                        S('Items: No items at all', '道具：どちらも　なし')]),
    'QOL': dict(hint=S('Speed-ups, turbo button, auto-run,\nquick save and quick Surf.',
                       'ゲームの　高速化や　ターボボタン\nいつも　はしる　などの　設定です'),
                rows=[S('Speed: Default', 'スピード：おすすめ'), S('Speed: Custom', 'スピード：カスタム')]),
}
MAIN = ['DIFF', 'CITY', 'NUZ', 'ENC', 'ITEMS', 'QOL', 'DONE']
# Pages have at most 7 rows: the list never scrolls (B2's list menu, given a start cursor below the
# 4th row of a scrolling list, draws it unscrolled and the cursor then can't move down).
PAGES = {
    'NUZ': ['PRESET', 'FAINT', 'GAMEOVER', 'NICK', 'BACK'],
    'ENC': ['FIRST', 'DUPES', 'LIMIT', 'SHINY', 'STATICS', 'BACK'],
    'ITEMS': ['NOITEMS', 'NOTRITEMS', 'BACK'],
    'QOL': ['SPEED', 'TURBO', 'AUTORUN', 'QSAVE', 'QSURF', 'BACK'],
}
PRESET_FLAGS = ['release', 'gameover', 'first', 'dupes', 'shiny', 'nickname']

# --- recap texts ---------------------------------------------------------------------------------------
RECAP_PARTS = {     # (en, ja) per non-default value, in display order
    'NUZ': [('FAINT', 1, 'fainted Pokémon released', 'ひんしは　にがす'),
            ('FAINT', 2, 'fainted Pokémon to the graveyard', 'ひんしは　おはかへ'),
            ('GAMEOVER', 0, 'game over', 'ゲームオーバー'), ('NICK', 0, 'always nickname', '必ず　ニックネーム')],
    'ENC': [('FIRST', 0, 'first catch only', '最初の　１匹だけ'), ('DUPES', 0, 'dupes clause', 'ダブり　なし'),
            ('LIMIT', 1, 'species limit (same species)', '同じ　しゅるいは　だめ'),
            ('LIMIT', 2, 'species limit (evolution line)', '進化の　なかまも　だめ'),
            ('SHINY', 0, 'shiny clause', '色違い　とくべつ'), ('STATICS', 0, 'statics count', '固定も　数える')],
    'ITEMS': [('NOITEMS', 0, 'no battle items', '勝負中の　道具なし'),
              ('NOTRITEMS', 0, 'no trainer items', 'トレーナーの　道具なし')],
    'QOL': [('SPEED', 1, 'speed-ups off', '高速化：オフ'), ('TURBO', 1, 'turbo button off', 'ターボ：オフ'),
            ('AUTORUN', 1, 'auto-run off', 'いつも　はしる：オフ'), ('QSAVE', 0, 'quick save on', 'すぐに　レポート：オン'),
            ('QSURF', 0, 'quick Surf on', 'すぐに　なみのり：オン')],
}
RECAP_HEAD = {'NUZ': ('Nuzlocke: ', 'ナズロック：'), 'ENC': ('Catch rules: ', 'つかまえる　ルール：'),
              'ITEMS': ('Items: ', '道具：'), 'QOL': ('Speed options: ', 'スピード：')}
EN_WIDTH, JA_WIDTH = 36, 18


def _pages(lines):
    """2 lines per message page"""
    return '{BE01}\n'.join('\n'.join(lines[i:i + 2]) for i in range(0, len(lines), 2))


def wrap_en(text):
    out, cur = [], ''
    for w in text.split(' '):
        if cur and len(cur) + 1 + len(w) > EN_WIDTH:
            out.append(cur)
            cur = w
        else:
            cur = f'{cur} {w}' if cur else w
    return _pages(out + [cur])


def wrap_ja(head, parts):
    toks = [head + parts[0]] + parts[1:]
    toks = [t + ('、' if i < len(toks) - 1 else '。') for i, t in enumerate(toks)]
    out, cur = [], ''
    for t in toks:
        for piece in re.split('(?<=　)', t):
            if cur and len(cur) + len(piece) > JA_WIDTH:
                out.append(cur.rstrip('　'))
                cur = piece
            else:
                cur += piece
    return _pages(out + [cur])


def recap_codes(cat):
    """[(code, [(key, value)])]: every combination of the category's settings; code = mixed radix"""
    keys = []
    for k, v, *_ in RECAP_PARTS[cat]:
        if k not in keys:
            keys.append(k)
    radix = [len(SETTINGS[k]['vals']) for k in keys]
    out = []
    total = 1
    for r in radix:
        total *= r
    for code in range(total):
        c, vals = code, []
        for k, r in zip(keys, radix):
            vals.append((k, c % r))
            c //= r
        out.append((code, vals))
    return keys, radix, out


def default_index(key):
    s = SETTINGS[key]
    if key == 'DIFF':
        return 2
    if s['kind'] == 'flag':
        return 0 if s['inv'] else 1      # QoL toggles default On, rules default Off
    return 0


RECAP_DEFAULT = {'NUZ': S('Nuzlocke: off.', 'ナズロック：オフ。'),
                 'ENC': S('Catch rules: off.', 'つかまえる　ルール：オフ。'),
                 'ITEMS': S('Items: no item rules.', '道具：ふつう。'),
                 'QOL': S('Speed options: all speed-ups on.', 'スピード：おすすめ（すべて　オン）。')}
TOWER = [S('Black Tower', 'ブラックタワー'), S('White Treehollow', 'ホワイトツリーホロウ')]


def recap_texts():
    """the settings view (common script 1230, story bank 208): every value of every category"""
    out = {'HEAD': S('These are the rules of your\nadventure (ReRedux settings).',
                     'この　冒険の　ルール\n（リリダックスの　設定）'),
           'DEATHS': S('Pokémon lost to the rules\nso far: {0202:0}', 'ルールで　失った　ポケモン：\n{0202:0}匹')}
    for d in range(3):
        for c in range(2):
            out[f'RC_DC_{d}_{c}'] = S(f"Difficulty: {SETTINGS['DIFF']['vals'][d][0]['en']}\n"
                                      f"City: {SETTINGS['CITY']['vals'][c][0]['en']}{{BE01}}\n"
                                      f"Tower: {TOWER[c]['en']}",
                                      f"むずかしさ：{SETTINGS['DIFF']['vals'][d][0]['ja']}\n"
                                      f"まち：{SETTINGS['CITY']['vals'][c][0]['ja']}{{BE01}}\n"
                                      f"タワー：{TOWER[c]['ja']}")
    for cat in RECAP_PARTS:
        keys, radix, combos = recap_codes(cat)
        for code, vals in combos:
            on = dict(vals)
            parts = [(en, ja) for k, v, en, ja in RECAP_PARTS[cat] if on[k] == v]
            if all(on[k] == default_index(k) for k in keys):
                out[f'RC_{cat}_{code}'] = RECAP_DEFAULT[cat]
                continue
            en = RECAP_HEAD[cat][0] + ', '.join(p[0] for p in parts) + '.'
            out[f'RC_{cat}_{code}'] = S(wrap_en(en), wrap_ja(RECAP_HEAD[cat][1], [p[1] for p in parts]))
    return out


def all_texts():
    t = dict(T)
    for key, s in SETTINGS.items():
        t['H_' + key] = s['hint']
        for i, (label, hint) in enumerate(s['vals']):
            t[f'VAL_{key}_{i}'] = label
            t[f'VAL_{key}_{i}_C'] = S(CUR + label['en'], CUR + label['ja'])
            t[f'HV_{key}_{i}'] = hint
        for i, row in enumerate(s['rows']):
            t[f'ROW_{key}_{i}'] = row
    for key, s in SUMMARY.items():
        t['H_' + key] = s['hint']
        for i, row in enumerate(s['rows']):
            t[f'ROW_{key}_{i}'] = row
    return t


VIEW_FILE, VIEW_TEXT, VIEW_BASE = 1230, 208, 2000   # common script 1230 = global ids 2000.. (text: story 208)
TEXTS = [dict(bank=('story', ZONE_TEXT), key='MENU_' + k, en=v['en'], ja=v['ja']) for k, v in all_texts().items()] + \
        [dict(bank=('story', VIEW_TEXT), key='VIEW_' + k, en=v['en'], ja=v['ja']) for k, v in recap_texts().items()]


def view_ids(rom_view, fid):
    """(event id, recap id) of the two settings-view entries appended to common script 1230: the next
    two header entries (rules.py HEADERS computes the same for rules.c)"""
    import ndsfs, struct
    data = ndsfs.narc(rom_view.file(fid))[VIEW_FILE]
    n = 0
    while struct.unpack_from('<H', data, 4 * n)[0] != 0xFD13:
        n += 1
    return VIEW_BASE + n, VIEW_BASE + n + 1


class Gen:
    """Script listing builder (gen5script listing syntax)."""

    def __init__(self, ctx):
        self.ctx, self.L, self.n = ctx, [], 0

    def m(self, key):
        return self.ctx.text_id('MENU_' + key)

    def a(self, s):
        self.L.append('    ' + s)

    def lab(self, s):
        self.L.append(s + ':')

    def new(self, p):
        self.n += 1
        return f'rm_{p}{self.n}'

    def if_not(self, push, value, label):
        """jump to label unless `push` == value (push: 'flag N' or 'var N')"""
        kind, n = push.split()
        self.a(('StackPushFlag ' if kind == 'flag' else 'StackPush ') + n)
        self.a(f'StackPushConst {value}')
        self.a('StackCmp 1')
        self.a(f'VMJumpIf 255, @{label}')

    def unless(self, conds, label):
        """jump to label unless every (push, value) holds"""
        for push, value in conds:
            self.if_not(push, value, label)

    # --- settings ---
    def conds(self, key, i):
        """conditions for setting `key` == value index i"""
        s = SETTINGS[key]
        if s['kind'] == 'var':
            return [(f'var {s["var"]:#x}', i)]
        if s['kind'] == 'flag':
            return [(f'flag {s["flag"]:#x}', (1 if i == 0 else 0) ^ (1 if s['inv'] else 0))]
        rel, grave = f'flag {F["release"]:#x}', f'flag {F["graveyard"]:#x}'
        return [[(rel, 0)], [(rel, 1), (grave, 0)], [(rel, 1), (grave, 1)]][i]

    def set_value(self, key, i):
        s = SETTINGS[key]
        if s['kind'] == 'var':
            self.a(f'WorkSetConst {s["var"]:#x}, {i}')
        elif s['kind'] == 'flag':
            on = (i == 0) != s['inv']
            self.a(f'{"FlagSet" if on else "FlagReset"} {s["flag"]:#x}')
        else:
            self.a(f'{"FlagSet" if i else "FlagReset"} {F["release"]:#x}')
            self.a(f'{"FlagSet" if i == 2 else "FlagReset"} {F["graveyard"]:#x}')

    def choice(self, options, uid, hint):
        """options: [(conds or None, text key)]: the first whose conditions hold is shown"""
        end = self.new('e')
        for cs, key in options:
            nxt = self.new('n') if cs else None
            if cs:
                self.unless(cs, nxt)
            self.a(f'ListMenuAdd {self.m(key)}, {self.m(hint)}, {uid}')
            self.a(f'VMJump @{end}')
            if nxt:
                self.lab(nxt)
        self.lab(end)

    def setting_row(self, key, uid):
        n = len(SETTINGS[key]['vals'])
        self.choice([(self.conds(key, i) if i < n - 1 else None, f'ROW_{key}_{i}') for i in range(n)], uid, 'H_' + key)

    def picker(self, key):
        """rm_pk_KEY (VMCall): every value of the setting, current one marked and under the cursor"""
        n = len(SETTINGS[key]['vals'])
        self.lab(f'rm_pk_{key}')
        self.a(f'WorkSetConst {T_PCUR:#x}, 0')
        for i in range(1, n):
            nx = self.new('p')
            self.unless(self.conds(key, i), nx)
            self.a(f'WorkSetConst {T_PCUR:#x}, {i}')
            self.lab(nx)
        self.a(f'MsgSystem {self.m("PICK")}, 0')      # window type 1: shows the hints
        self.a(f'ListMenuInitTR 31, 1, {T_PCUR:#x}, 1, {T_RES:#x}')
        for i in range(n):
            self.choice([([(f'var {T_PCUR:#x}', i)], f'VAL_{key}_{i}_C'), (None, f'VAL_{key}_{i}')], i, f'HV_{key}_{i}')
        self.a('ListMenuShow')
        self.a('MsgSystemClose')
        self.a('MsgWinCloseAll')
        for i in range(n):                  # B (0xFFFE) matches no case: nothing changes
            nx = self.new('v')
            self.if_not(f'var {T_RES:#x}', i, nx)
            self.set_value(key, i)
            self.a('VMReturn')
            self.lab(nx)
        self.a('VMReturn')

    def code(self, var, terms):
        """var = sum of the weights whose conditions hold; terms: [(conds, weight)]"""
        self.a(f'WorkSetConst {var:#x}, 0')
        for cs, w in terms:
            if not w:
                continue
            nx = self.new('k')
            self.unless(cs, nx)
            self.a(f'WorkAdd {var:#x}, {w}')
            self.lab(nx)

    def summaries(self):
        """T_A Nuzlocke 0 off / 1 classic / 2 custom, T_B catch rules on, T_C items, T_D speed"""
        cl = [(f'flag {F[f]:#x}', 1) for f in PRESET_FLAGS] + [(f'flag {F["graveyard"]:#x}', 0)]
        off = [(f'flag {F[f]:#x}', 0) for f in ('release', 'gameover', 'nickname')]
        a_cl, a_off, a_end = self.new('s'), self.new('s'), self.new('s')
        self.a(f'WorkSetConst {T_A:#x}, 2')
        self.unless(cl, a_cl)
        self.a(f'WorkSetConst {T_A:#x}, 1')
        self.a(f'VMJump @{a_end}')
        self.lab(a_cl)
        self.unless(off, a_end)
        self.a(f'WorkSetConst {T_A:#x}, 0')
        self.lab(a_end)
        self.code(T_B, [(self.conds(k, 0), 1) for k in ('FIRST', 'DUPES', 'SHINY', 'STATICS')] +
                  [(self.conds('LIMIT', 1), 1), (self.conds('LIMIT', 2), 1)])
        self.code(T_C, [(self.conds('NOITEMS', 0), 1), (self.conds('NOTRITEMS', 0), 2)])
        self.code(T_D, [(self.conds(k, 1 - default_index(k)), 1) for k in PAGES['QOL'][:-1]])

    def recap(self, t):
        """messages (texts VIEW_*): difficulty, city and tower, then every category's settings, the
        rules' death count when Fainted isn't Kept; uses temporary var t"""
        v = lambda key: self.ctx.text_id('VIEW_' + key)
        terms = [(self.conds('DIFF', d), 2 * d) for d in (1, 2)] + [(self.conds('CITY', 1), 1)]
        self.code(t, terms)
        for d in range(3):
            for c in range(2):
                nx = self.new('r')
                self.if_not(f'var {t:#x}', 2 * d + c, nx)
                self.a(f'MsgInfo {v(f"RC_DC_{d}_{c}")}, 2')
                self.a('InputWaitLast')
                self.lab(nx)
        for cat in RECAP_PARTS:
            keys, radix, combos = recap_codes(cat)
            w, terms = 1, []
            for k, r in zip(keys, radix):
                terms += [(self.conds(k, i), w * i) for i in range(1, r)]
                w *= r
            self.code(t, terms)
            for code, vals in combos:
                nx = self.new('r')
                self.if_not(f'var {t:#x}', code, nx)
                self.a(f'MsgInfo {v(f"RC_{cat}_{code}")}, 2')
                self.a('InputWaitLast')
                self.lab(nx)
        nx = self.new('r')
        self.if_not(f'flag {F["release"]:#x}', 1, nx)
        self.a(f'WordSetNumber 0, {R.RV_DEATHS:#x}, 3')
        self.a(f'MsgInfo {v("DEATHS")}, 2')
        self.a('InputWaitLast')
        self.lab(nx)
        self.a(f'WorkSetConst {t:#x}, 0')

    def view(self):
        """common script 1230 entries: rx_view (the SELECT event, rules.c) and rx_recap (RTCallGlobal
        from the intro menu's Start); both list every setting"""
        self.lab('rx_view')
        self.a('ActorPauseAll')
        self.a(f'MsgInfo {self.ctx.text_id("VIEW_HEAD")}, 2')
        self.a('InputWaitLast')
        self.a('VMCall @rx_recap')
        self.a('MsgWinCloseAll')
        self.a('ActorUnlockAll')
        self.a('VMHalt')
        self.lab('rx_recap')
        self.recap(0x8020)
        self.a('VMReturn')
        return self.L

    def page(self, name):
        rows = PAGES[name]
        top, loop, ret = f'rm_page_{name}', f'rm_page_{name}_loop', f'rm_page_{name}_ret'
        self.lab(top)
        self.a(f'WorkSetConst {T_SUB:#x}, 0')
        self.lab(loop)
        self.a(f'MsgSystem {self.m("PROMPT")}, 0')
        self.a(f'ListMenuInitTR 31, 1, {T_SUB:#x}, 1, {T_RES:#x}')
        for uid, key in enumerate(rows):
            if key in SETTINGS:
                self.setting_row(key, uid)
            else:
                self.a(f'ListMenuAdd {self.m(key)}, {self.m("H_" + key)}, {uid}')
        self.a('ListMenuShow')
        self.a('MsgSystemClose')
        self.a('MsgWinCloseAll')
        self.if_not(f'var {T_RES:#x}', 0xFFFE, f'{top}_c')        # B
        self.a(f'VMJump @{ret}')
        self.lab(f'{top}_c')
        self.a(f'WorkGet {T_SUB:#x}, {T_RES:#x}')               # the cursor stays on this row
        for uid, key in enumerate(rows):
            nxt = self.new('c')
            self.if_not(f'var {T_SUB:#x}', uid, nxt)
            if key == 'BACK':
                self.a(f'VMJump @{ret}')
            elif key == 'PRESET':
                self.a(f'MsgInfo {self.m("PRESET_ASK")}, 2')
                self.a(f'YesNoWin {T_RES:#x}')
                self.a('MsgWinCloseAll')
                self.if_not(f'var {T_RES:#x}', 0, loop)
                for f in PRESET_FLAGS:
                    self.a(f'FlagSet {F[f]:#x}')
                self.a(f'FlagReset {F["graveyard"]:#x}')
            else:
                self.a(f'VMCall @rm_pk_{key}')
            self.a(f'VMJump @{loop}')
            self.lab(nxt)
        self.a(f'VMJump @{loop}')
        self.lab(ret)
        self.a('VMReturn')

    def menu(self):
        self.lab('rules_menu')
        self.if_not(f'var {V_DONE:#x}', 0, 'rules_menu_end')
        self.a(f'WorkSetConst {V_DIFF:#x}, 2')
        self.a(f'WorkSetConst {V_LIMIT:#x}, 0')
        self.a(f'WorkSetConst {V_CITY:#x}, 0')
        self.a(f'WorkSetConst {T_CUR:#x}, 0')
        self.a(f'MsgInfo {self.m("INTRO")}, 2')
        self.a('InputWaitLast')
        self.a('MsgWinCloseAll')
        self.lab('rm_main')
        self.summaries()
        self.a(f'MsgSystem {self.m("PROMPT")}, 0')    # window type 1: shows the hints
        self.a(f'ListMenuInitTR 31, 1, {T_CUR:#x}, 0, {T_RES:#x}')
        for uid, key in enumerate(MAIN):
            if key in SETTINGS:
                self.setting_row(key, uid)
            elif key in SUMMARY:
                var = {'NUZ': T_A, 'ENC': T_B, 'ITEMS': T_C, 'QOL': T_D}[key]
                n = len(SUMMARY[key]['rows'])
                self.choice([([(f'var {var:#x}', i)] if i < n - 1 else None, f'ROW_{key}_{i}') for i in range(n)],
                            uid, 'H_' + key)
            else:
                self.a(f'ListMenuAdd {self.m(key)}, {self.m("H_" + key)}, {uid}')
        self.a('ListMenuShow')
        self.a('MsgSystemClose')
        self.a('MsgWinCloseAll')
        self.a(f'WorkGet {T_CUR:#x}, {T_RES:#x}')      # the cursor stays on this row
        for uid, key in enumerate(MAIN):
            if key == 'DONE':
                continue
            nx = self.new('c')
            self.if_not(f'var {T_CUR:#x}', uid, nx)
            self.a(f'VMCall @{"rm_pk_" + key if key in SETTINGS else "rm_page_" + key}')
            self.a('VMJump @rm_main')
            self.lab(nx)
        # Start the adventure!: recap (the settings view's list, common script 1230), confirm, apply
        self.a(f'RTCallGlobal {self.ctx.view_ids[1]}')
        self.a(f'MsgInfo {self.m("CONFIRM")}, 2')
        self.a(f'YesNoWin {T_RES:#x}')
        self.a('MsgWinCloseAll')
        self.if_not(f'var {T_RES:#x}', 0, 'rm_main')
        self.a(f'.hword {R.RULES_CMD:#06x}, 0, {T_RES:#x}, {V_DIFF:#x}')   # RulesCmd 0: apply the difficulty
        self.a(f'.hword {R.RULES_CMD:#06x}, 5, {T_RES:#x}, {V_CITY:#x}')   # RulesCmd 5: apply the city
        self.a(f'WorkSetConst {V_DONE:#x}, 1')
        for t in (T_RES, T_CUR, T_SUB, T_PCUR, T_A, T_B, T_C, T_D):
            self.a(f'WorkSetConst {t:#x}, 0')
        self.lab('rules_menu_end')
        self.a('VMReturn')
        for p in PAGES:
            self.page(p)
        for key in SETTINGS:
            self.picker(key)
        return '\n'.join(self.L) + '\n'

def _scripts():
    import gen5script, redux_rom
    return gen5script, redux_rom.BUILD


# Redux's script files hold raw (undecoded) bytes, some of them relative offsets, so code must not
# move: every patch keeps the original bytes in place and only appends code at the end of the file.
#   intro: scr_29's header entry -> an appended stub (ActorPauseAll; VMCall @rules_menu; VMJump back)
#   gifts: `YesNoWin V` (+ following plain commands, >= 6 bytes) -> `VMJump @stub` + padding; the stub
#          (appended) does the flag test / YesNoWin, the moved commands and jumps back.
# check_in_place() verifies that only those bytes changed in the original part of the file.

INSTR = re.compile(r'^    (\S+)(?: (.*))?$')


class Script:
    def __init__(self, listing, gen5script, build_dir):
        self.g, self.bd = gen5script, build_dir
        first = listing.split('\n', 1)[0]
        self.ov = first if first.startswith('.overlay ') else None
        self.lines = listing.split('\n')
        self.tail = []          # appended lines
        self.sites = 0

    def size(self, line):
        """bytes of one instruction without label arguments"""
        txt = (self.ov + '\n' if self.ov else '') + line + '\n'
        return len(self.g.assemble_any(txt, self.bd))

    def text(self):
        return '\n'.join(self.lines).rstrip('\n') + '\n' + '\n'.join(self.tail) + '\n'

    def redirect(self, idx, stub_lines, tag):
        """replace instructions from line idx (>= 6 bytes, no labels/branches among them) by a jump to
        an appended stub: stub_lines(moved instruction lines) + jump back"""
        moved, n, j = [], 0, idx
        while n < 6:
            l = self.lines[j]
            m = INSTR.match(l)
            if not m or '@' in l or m.group(1).startswith('.'):
                raise ValueError(f'{tag}: cannot move {l!r}')
            moved.append(l)
            n += self.size(l)
            j += 1
        stub, back = f'rx_{tag}', f'rx_{tag}_back'
        self.lines[idx:j] = [f'    VMJump @{stub}'] + [f'    .byte 0x00'] * (n - 6) + [f'{back}:']
        self.tail += [f'{stub}:'] + stub_lines(moved) + [f'    VMJump @{back}']
        self.sites += 1


def check_in_place(old, new, sites):
    """the original bytes may only change in <= sites clusters of <= 8 bytes (jumps + padding)"""
    if len(new) < len(old):
        raise ValueError('script shrank')
    diff = [i for i in range(len(old)) if old[i] != new[i]]
    clusters = []
    for i in diff:
        if clusters and i - clusters[-1][1] <= 8:
            clusters[-1][1] = i
        else:
            clusters.append([i, i])
    if len(clusters) > sites or any(b - a >= 8 for a, b in clusters):
        raise ValueError(f'script patch moved code: changed {clusters}')


def patch_intro(sc, ctx):
    L = sc.lines
    i = L.index('scr_29:')
    if L[i + 1] != '    ActorPauseAll' or '.script scr_29' not in L or not any('MapChangeCore 428' in l for l in L):
        raise ValueError('zone 427 scr_29 is not the opening cutscene')
    L.insert(i + 2, 'rx_scr_29_cont:')
    L[L.index('.script scr_29')] = '.script rx_intro'
    sc.tail += ['rx_intro:', '    ActorPauseAll', '    VMCall @rules_menu', '    VMJump @rx_scr_29_cont']
    sc.tail += Gen(ctx).menu().rstrip('\n').split('\n')
    sc.sites += 1


def nickname_sites(lines):
    """-> [line index of YesNoWin V] for nickname questions (see the module docstring)"""
    labels = {l[:-1]: i for i, l in enumerate(lines) if l.endswith(':') and not l.startswith(' ')}

    def reaches_name_input(i, budget, depth):
        while 0 <= i < len(lines) and budget > 0:
            m = INSTR.match(lines[i])
            i += 1
            if not m:
                continue                      # label
            op, args = m.group(1), m.group(2) or ''
            budget -= 1
            if op == 'CallPokeNameInput':
                return True
            if op in ('YesNoWin', 'VMReturn', 'VMHalt', 'VMEnd', 'VMJump') or op.startswith('.'):
                return False
            if op == 'VMCall' and depth == 0 and args.lstrip('@') in labels:
                if reaches_name_input(labels[args.lstrip('@')] + 1, budget, 1):
                    return True
        return False

    out = []
    for i, l in enumerate(lines):
        m = re.match(r'^    YesNoWin (\S+)$', l)
        if not m:
            continue
        v = m.group(1)
        j = i + 1
        while j < len(lines) and lines[j].strip() in ('MsgSystemClose', 'MsgWinCloseAll', 'MsgActorClose'):
            j += 1
        want = [f'    StackPush {v}', '    StackPushConst 0', '    StackCmp 1']
        if lines[j:j + 3] != want or not lines[j + 3].startswith('    VMJumpIf 255, @'):
            continue
        if reaches_name_input(j + 4, 12, 0):
            out.append(i)
    return out


def patch_nicknames(sc, tag):
    sites = nickname_sites(sc.lines)
    flag = R.FLAGS['nickname']
    for k, i in enumerate(reversed(sites)):      # from the end: earlier indices stay valid
        v = sc.lines[i].split()[1]
        ask, done = f'rn_{tag}_{k}_ask', f'rn_{tag}_{k}_done'

        def stub(moved, v=v, ask=ask, done=done):
            return [f'    StackPushFlag {flag:#x}', '    StackPushConst 1', '    StackCmp 1', f'    VMJumpIf 255, @{ask}',
                    f'    WorkSetConst {v}, 0', f'    VMJump @{done}', f'{ask}:', moved[0], f'{done}:'] + moved[1:]
        sc.redirect(i, stub, f'{tag}_{k}')
    return len(sites)




def patch_keybearer(sc, ctx):
    """zone 427 scr_34: skip CallUnovaLinkKeyUnlock 0, 1, 7 (Easy, Challenge, City Key) and say why"""
    L = sc.lines
    i = L.index('    CallUnovaLinkKeyUnlock 0')
    if L[i + 1:i + 4] != ['    CallUnovaLinkKeyUnlock 1', '    CallUnovaLinkKeyUnlock 7', '    FlagSet 2965']:
        raise ValueError(f'zone 427: the key bearer script changed: {L[i:i + 4]}')
    # `VMJump` over the three (6 bytes over unlock 0 and half of unlock 1; the rest stays, unreached)
    L[i:i + 4] = ['    VMJump @rx_keys_skip', '    .byte 0x01', '    .byte 0x00', L[i + 2], 'rx_keys_skip:', L[i + 3]]
    sc.sites += 1
    old = f'    MsgActor 1024, {KEYBEARER_LINE}, 0, 0'
    if L.count(old) != 1:
        raise ValueError(f'zone 427: {old.strip()!r} found {L.count(old)} times')
    L[L.index(old)] = f'    MsgActor 1024, {ctx.text_id("MENU_KEYBEARER")}, 0, 0'   # msg id in place
    sc.sites += 1


def files(ctx):
    import ndsfs
    gen5script, build_dir = _scripts()
    fid = ctx.fid('a/0/5/6')
    raw = ctx.rom.file(fid)
    scripts = ndsfs.narc(raw)
    report = []
    ctx.view_ids = view_ids(ctx.rom, fid)
    # the settings view: two entries appended to common script 1230's header (the code moves by 8
    # bytes as a whole, as the followers' talk script entry did; relative offsets stay valid)
    data = scripts[VIEW_FILE]
    listing, _ = gen5script.decompile_best(data, build_dir)
    if gen5script.assemble_any(listing, build_dir) != data:
        raise ValueError(f'script {VIEW_FILE} does not round-trip')
    L = listing.split('\n')
    last = max(i for i, l in enumerate(L) if l.startswith('.script'))
    if sum(1 for l in L if l.startswith('.script')) != ctx.view_ids[0] - VIEW_BASE:
        raise ValueError('common script 1230: header entry count mismatch')
    L[last + 1:last + 1] = ['.script rx_view', '.script rx_recap']
    scripts[VIEW_FILE] = gen5script.assemble_any('\n'.join(L).rstrip('\n') + '\n' + '\n'.join(Gen(ctx).view()) + '\n',
                                                 build_dir)
    report.append(f'{VIEW_FILE} (settings view ids {ctx.view_ids[0]}, {ctx.view_ids[1]})')
    for i, data in enumerate(scripts):
        if i == VIEW_FILE:
            continue
        intro = i == ZONE_SCRIPT
        if not intro and not (b'\x05\x01' in data and b'\x47\x00' in data):   # CallPokeNameInput, YesNoWin
            continue
        listing, _ = gen5script.decompile_best(data, build_dir)
        if gen5script.assemble_any(listing, build_dir) != data:
            if intro:
                raise ValueError(f'script {i} does not round-trip')
            continue
        sc = Script(listing, gen5script, build_dir)
        n = patch_nicknames(sc, i)
        if intro:
            patch_keybearer(sc, ctx)
            patch_intro(sc, ctx)
        if sc.sites:
            new = gen5script.assemble_any(sc.text(), build_dir)
            check_in_place(data, new, sc.sites)
            scripts[i] = new
            report.append(f'{i}' + (f' ({n} nickname)' if n else '') + (f' (menu, key bearer; {len(new)} bytes)' if intro else ''))
    print('menu: scripts patched (append-only): ' + ', '.join(report))
    return {fid: ndsfs.pack_narc(scripts, ndsfs.narc_layout(raw))}
