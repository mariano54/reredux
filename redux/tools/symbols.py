"""Symbolic names for script arguments.

Constants live in SRC/constants/<category>.txt ("NAME = id" per line), written once at export
from the ROM's names (catalog.py) and read back at build, so renaming a Pokémon in the text never
breaks scripts. A literal argument is shown as a constant when its parameter name says what it is
(species, itemId, moveId, trId, zoneId); values >= 0x4000 (script variables) are shown in hex;
message arguments get the line's text as a `;` comment.
"""
import os

PARAM_CATEGORY = {
    'species': 'species', 'poke': 'species', 'monsno': 'species', 'pokeid': 'species',
    'itemid': 'item', 'item': 'item',
    'moveid': 'move', 'movecode': 'move', 'move': 'move',
    'trid': 'trainer', 'trid1': 'trainer', 'trid2': 'trainer', 'trainerid': 'trainer',
    'zoneid': 'zone',
}
CATEGORIES = ('species', 'item', 'move', 'trainer', 'zone', 'ability', 'type', 'trclass')


def write_constants(src, consts):
    d = os.path.join(src, 'constants')
    os.makedirs(d, exist_ok=True)
    for cat, table in consts.items():
        with open(os.path.join(d, f'{cat}.txt'), 'w') as f:
            f.writelines(f'{name} = {i}\n' for i, name in sorted(table.items()))


def read_constants(src):
    out = {}
    d = os.path.join(src, 'constants')
    for cat in CATEGORIES:
        p = os.path.join(d, f'{cat}.txt')
        if os.path.exists(p):
            t = {}
            for line in open(p):
                if '=' in line:
                    name, v = line.split('=')
                    t[int(v)] = name.strip()
            out[cat] = t
    return out


class Symbols:
    def __init__(self, consts, messages=None):
        self.consts = consts
        self.rev = {name: i for t in consts.values() for i, name in t.items()}
        self.messages = messages     # list of text lines of the script's zone, or None

    def with_messages(self, messages):
        s = Symbols.__new__(Symbols)
        s.consts, s.rev, s.messages = self.consts, self.rev, messages
        return s

    def fmt(self, pname, ptype, v):
        if ptype in ('ushort', 'ref ushort') and v >= 0x4000:
            return f'0x{v:04X}'
        cat = PARAM_CATEGORY.get(pname.lower())
        if cat and cat in self.consts and v in self.consts[cat]:
            return self.consts[cat][v]
        return str(v)

    def parse(self, tok):
        return self.rev.get(tok)

    def comment(self, pnames, vals):
        if not self.messages:
            return None
        for name, v in zip(pnames, vals):
            if name == 'msgId' and isinstance(v, int) and v < len(self.messages):
                t = self.messages[v].replace('\\n', ' ')
                return '"' + (t[:70] + '…' if len(t) > 70 else t) + '"'
        return None
