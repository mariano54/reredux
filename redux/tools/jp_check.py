"""jp_check.py TODO.json TR.json : check a translation file for jp_port.py.

TR.json is {id: japanese}. Checks: every id translated; the same control codes ({0102:0}, {BE01},
{003F}...) as the English, each as many times; line breaks written as the two characters \\n (as
in the input); each displayed line at most 18 full-width characters (half-width counts 0.5, a name
placeholder counts 6); no raw newlines. Exit status 1 if anything is wrong."""
import json, re, sys

TAG = re.compile(r'\{[0-9A-F]{4}(?::[0-9,]*)?\}|\{U\+[0-9A-F]{4}\}')
NAME = re.compile(r'\{01[0-9A-F]{2}:[0-9,]*\}')
BREAK = re.compile(r'\\n|\{BE0[01]\}|\{003F\}')
MAXW = 18


def width(seg):
    w = 6 * len(NAME.findall(seg))
    for ch in TAG.sub('', seg):
        w += 0.5 if ord(ch) < 0x2000 or 0xFF61 <= ord(ch) <= 0xFF9F else 1
    return w


def tags(t):
    return sorted(x for x in TAG.findall(t) if x != '{U+FFFF}')


def main(todo_p, tr_p):
    todo = json.load(open(todo_p))
    tr = json.load(open(tr_p))
    bad = 0
    for it in todo:
        i, en = it['id'], it['en']
        ja = tr.get(i)
        if ja is None:
            print(f'{i}: missing')
            bad += 1
            continue
        if '\n' in ja or '\r' in ja:
            print(f'{i}: raw newline (write \\\\n in JSON, i.e. backslash + n)')
            bad += 1
        if tags(ja) != tags(en):
            print(f'{i}: tags differ: en {tags(en)} ja {tags(ja)}')
            bad += 1
        if '\\n' in en or len(en) > 30:     # dialogue / descriptions: line widths matter
            for seg in BREAK.split(ja):
                if width(seg) > MAXW:
                    print(f'{i}: line too wide ({width(seg)}): {seg}')
                    bad += 1
    extra = set(tr) - {it['id'] for it in todo}
    if extra:
        print('ids not in the todo file:', sorted(extra)[:10])
        bad += 1
    print(f'{len(todo)} items, {bad} problems')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(*sys.argv[1:3])
