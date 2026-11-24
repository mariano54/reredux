"""ReRedux qol2: test-only module (disabled; build/scripts/qol2/build.py --test, build/scripts/qa2/build_qa2.py):
q2tst mailbox to read and write party Pokémon parameters, set a Pokémon's language (+ Pokédex
registration) and toggle the bike from the emulator tests (qol2_test.c). Needs rules (rules_gd)."""
ENABLED = False
FRAME = ['qol2_test_frame']
SYMS = {'PokeParty_SetParam': 0x0201CD1D, 'addPkmToDex': 0x0200D569, 'PokeDex_SetNationalObtained': 0x0200D19D}
