"""scen.py : the menu-speed sweep's scenarios (sweep.py). Start: Continue of the smoke battery save (Aspertia Pokémon
Center, zone 435, tile 9,16 facing the Mart clerk on the right; party: Tepig-line lead + Purrloin; Bag: 50 Poké Balls,
money 3550; empty PC boxes). Step formats: see sweep.py. v = vanilla Redux 1.4.1 (X menu without a cursor until a key;
the PC's "booted up" / "Storage System was accessed" lines).
X-menu slots by touch (identical in Redux 1.4.1 and ReRedux): 0 POKÉMON, 1 POKÉDEX, 2 BAG, 3 card, 4 SAVE, 5 OPTIONS."""

SLOT = [(0x40, 0x2C), (0xC0, 0x2C), (0x40, 0x5C), (0xC0, 0x5C), (0x40, 0x8C), (0xC0, 0x8C)]
TELEPORT = {}


def xmenu(v):
    show = [('xmenu.show_cursor', 'DOWN', 'DOWN')] if v else []
    return [('xmenu.open', 'X', 'DOWN')] + show + [('xmenu.cursor', 'DOWN', 'B'), ('xmenu.close', 'B', 'X'),
                                                    ('xmenu.open', 'X', 'DOWN')] + show + [
            ('xmenu.cursor', 'DOWN', 'UP'), ('xmenu.cursor', 'UP', 'B'), ('xmenu.close', 'B', 'X')]


def party(v):
    open_ = [('=', 'X', 60)] + ([('=', 'A', 30)] if v else [])
    sub = [('party.submenu', 'A', 'DOWN'), ('=', 'DOWN', 20)]
    return open_ + [
        ('party.open', 'A', 'RIGHT'), ('party.cursor', 'RIGHT', 'LEFT'), ('party.cursor', 'LEFT', 'A'),
        ('party.submenu', 'A', 'DOWN'), ('party.sub_cursor', 'DOWN', 'UP'), ('party.sub_cursor', 'UP', 'B'),
        ('party.sub_close', 'B', 'A'), ('party.submenu', 'A', 'A'),
        ('summary.open', 'A', 'RIGHT'), ('summary.page', 'RIGHT', 'LEFT'), ('summary.page_back', 'LEFT', 'RIGHT'),
        ('summary.page', 'RIGHT', 'LEFT'), ('summary.page_back', 'LEFT', 'DOWN'),
        ('summary.next_mon', 'DOWN', 'UP'), ('summary.prev_mon', 'UP', 'B'), ('summary.close', 'B', 'A')] + sub + [
        ('party.switch_pick', 'A', 'RIGHT'), ('party.switch_cursor', 'RIGHT', 'A'), ('party.switch_do', 'A', 'A')] + sub + [
        ('party.switch_pick', 'A', 'LEFT'), ('party.switch_cursor', 'LEFT', 'A'), ('party.switch_do', 'A', 'B'),
        ('party.close', 'B', 'B'), ('xmenu.close', 'B', 'X')]


def apps(v):
    out = [('=', 'X', 60)]
    for name, slot in (('dex', 1), ('bag', 2), ('card', 3), ('options', 5)):
        out += [(f'{name}.open', SLOT[slot], 'B'), (f'{name}.close', 'B', SLOT[slot + 1 if slot < 5 else 0])]
    out[-1] = ('options.close', 'B', 'B')
    out += [('xmenu.close', 'B', 'X')]
    return out


def bag(v):
    """Bag by touch (the first key only switches to key mode), pockets, the Poké Ball's menu, GIVE -> party -> B"""
    return [('=', 'X', 60), ('bag.open', SLOT[2], 'DOWN'), ('bag.keymode', 'DOWN', 'RIGHT'),
            ('bag.pocket', 'RIGHT', 'LEFT'), ('bag.pocket_back', 'LEFT', 'LEFT'), ('bag.pocket_back', 'LEFT', 'RIGHT'),
            ('bag.pocket', 'RIGHT', 'A'), ('bag.item_menu', 'A', 'B'), ('bag.item_menu_close', 'B', 'A'),
            ('bag.item_menu', 'A', 'A'), ('bag.give', 'A', 'B'), ('bag.give_back', 'B', 'B'),
            ('bag.close', 'B', 'B'), ('xmenu.close', 'B', 'X')]


def dex(v):
    """Pokédex: the cover waits for A; list scroll, an entry (Tepig) and its pages, back"""
    return [('=', 'X', 60), ('dex.open', SLOT[1], 'A'), ('dex.cover', 'A', 'DOWN'),
            ('dex.scroll', 'DOWN', 'UP'), ('dex.scroll', 'UP', 'DOWN'), ('dex.scroll', 'DOWN', 'A'),
            ('dex.entry', 'A', 'RIGHT'), ('dex.page', 'RIGHT', 'LEFT'), ('dex.page_back', 'LEFT', 'RIGHT'),
            ('dex.page', 'RIGHT', 'B'), ('dex.entry_close', 'B', 'B'), ('dex.close', 'B', 'B'),
            ('xmenu.close', 'B', 'X')]


def pc(v):
    """PC: boot, Someone's PC, Move Pokémon -> Box: box switch, cursor, B -> Continue? NO -> list -> off;
    Deposit: pick Tepig -> menu -> DEPOSIT -> box 1, then Withdraw it back"""
    boot = [('pc.boot', 'A', 'A')] + ([('pc.boot_text', 'A', 'A')] if v else [])
    acc = ([('pc.someone', 'A', 'A'), ('pc.accessed_text', 'A', 'DOWN')] if v else [('pc.someone', 'A', 'DOWN')])
    return [('=goto', 4, 12), ('=face', 'UP')] + boot + acc + [
        ('pc.list_cursor', 'DOWN', 'DOWN'), ('pc.list_cursor', 'DOWN', 'A'),
        ('box.open', 'A', 'R'), ('box.switch', 'R', 'L'), ('box.switch_back', 'L', 'DOWN'),
        ('box.cursor', 'DOWN', 'UP'), ('box.cursor', 'UP', 'B'),
        ('box.exit_prompt', 'B', 'B'), ('box.exit', 'B', 'UP'),
        ('pc.list_cursor', 'UP', 'UP'), ('pc.list_cursor', 'UP', 'A'),
        ('box.open_deposit', 'A', 'A'), ('box.pick', 'A', 'B'), ('box.pick_cancel', 'B', 'A'), ('box.pick', 'A', 'A'),
        ('box.deposit_which', 'A', 'A'), ('box.deposit', 'A', 'B'),
        ('box.exit_prompt', 'B', 'B'), ('box.exit', 'B', 'DOWN'),
        ('pc.list_cursor', 'DOWN', 'A'), ('box.open_withdraw', 'A', 'A'), ('box.pick', 'A', 'A'),
        ('box.withdraw', 'A', 'B'), ('box.exit_prompt', 'B', 'B'), ('box.exit', 'B', 'B'),
        ('pc.list_close', 'B', 'B'), ('pc.off', 'B', 'X')]


def mart(v):
    """Mart clerk (right of the start tile): buy 2 Poké Balls"""
    return [('=face', 'RIGHT'), ('mart.talk', 'A', 'A'), ('mart.hello', 'A', 'A'), ('mart.buy', 'A', 'DOWN'),
            ('mart.list_cursor', 'DOWN', 'UP'), ('mart.list_cursor', 'UP', 'A'),
            ('mart.item', 'A', 'UP'), ('mart.qty', 'UP', 'A'), ('mart.qty_ok', 'A', 'A'), ('mart.yes', 'A', 'A'),
            ('mart.thanks', 'A', 'A'), ('mart.putaway', 'A', 'B'), ('mart.exit', 'B', 'DOWN'),
            ('=', 'DOWN', 20), ('=', 'DOWN', 20), ('mart.nothanks', 'A', 'A'), ('mart.bye', 'A', 'X')]


def nurse(v):
    """Nurse Joy: talk, yes/no (YES), the heal (jingle plays in full), the farewell lines"""
    return [('=goto', 7, 12), ('=face', 'UP'), ('nurse.talk', 'A', 'A'), ('nurse.text', 'A', 'DOWN'),
            ('yesno.cursor', 'DOWN', 'UP'), ('yesno.cursor', 'UP', 'A'), ('nurse.yes', 'A', 'A'),
            ('nurse.text', 'A', 'A'), ('nurse.text', 'A', 'A'), ('nurse.heal_yes', 'A', 'A', 600),
            ('nurse.text', 'A', 'A'), ('nurse.text', 'A', 'X')]


def battle(v):
    """Route 19 grass: walk until a wild battle; FIGHT, moves, B; POKÉMON (party in battle), B; BAG, B; RUN"""
    return [('=wild',), ('battle.fight', 'A', 'B'), ('battle.fight_back', 'B', 'A'), ('battle.fight', 'A', 'DOWN'),
            ('battle.move_cursor', 'DOWN', 'UP'), ('battle.move_cursor', 'UP', 'B'), ('battle.fight_back', 'B', 'DOWN'),
            ('battle.cmd_cursor', 'DOWN', 'A'), ('battle.party', 'A', 'B'), ('battle.party_back', 'B', 'LEFT'),
            ('battle.cmd_cursor', 'LEFT', 'A'), ('battle.bag', 'A', 'B'), ('battle.bag_back', 'B', 'RIGHT'),
            ('=', 'RIGHT', 20), ('battle.cmd_cursor', 'RIGHT', 'A'), ('battle.run', 'A', 'A', 600)]


def repeat(v):
    """held keys: the game's key repeat in the X menu, the party, the Pokédex list and the PC's list"""
    show = [('=', 'DOWN', 30)] if v else []
    return ([('=', 'X', 60)] + show + [('=hold', 'DOWN', 90, 'xmenu')] + [('=', 'B', 60)] +
            [('=', 'X', 60)] + show + [('=', 'UP', 30)] * 3 + [('=', 'A', 90), ('=hold', 'RIGHT', 60, 'party'),
                                                              ('=', 'B', 90), ('=', 'B', 60)] +
            [('=', 'X', 60), ('=', SLOT[1], 120), ('=', 'A', 150), ('=hold', 'DOWN', 120, 'dex_list'),
             ('=', 'B', 120), ('=', 'B', 90), ('=', 'B', 60)] +
            [('=goto', 4, 12), ('=face', 'UP'), ('=', 'A', 200)] + ([('=', 'A', 60)] if v else []) +
            [('=hold', 'DOWN', 60, 'pc_list'), ('=', 'B', 60)])


SCEN = dict(repeat=repeat,xmenu=xmenu, party=party, apps=apps, bag=bag, dex=dex, pc=pc, mart=mart, nurse=nurse, battle=battle)
