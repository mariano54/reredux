# Following Pokémon: credits

- **Follow movement and Gen 1–4 overworld sprites**: the game itself. Black 2/White 2 ship
  HeartGold/SoulSilver-style field sprites for every species up to #493 plus 53 Gen 5 species, and a
  "follow the player" movement code (0x30) used by story partners.
- **Design reference**: HeartGold/SoulSilver's follower system, read in the pret/pokeheartgold
  decompilation (and the LLM-assisted fork antonsynd/pokeheartgold-slop), plus Tempered Platinum's
  `follower_mon` (matt-newhall/plat-hack-decomp).
- **Black 2/White 2 symbols**: the `swan` headers (ds-pokemon-hacking), White 2 names ported to Black 2.
- **Gen 5 overworld sprites missing from the game** (103 species and their forms), converted from the
  Pokémon Essentials Generation 8 Pack v20.1 "Following Pokémon" graphics (compiled by Golisopod User
  and UberDunsparce). Gen 1–5 overworld artists: MissingLukey, help-14, Kymoyonian, cSc-A7X,
  2and2makes5, Pokegirl4ever, Fernandojl, Silver-Skies, TyranitarDark, Getsuei-H, Kid1513,
  Milomilotic11, Kyt666, kdiamo11, Chocosrawlooid, Syledude, Gallanty, Gizamimi-Pichu, Zyon17,
  LarryTurbo, spritesstealer.

- **Talk lines, their conditions, motions and the HGSS emote balloon and Poké Ball graphics**:
  HeartGold/SoulSilver's own data (NARCs a/2/2/0–a/2/2/2, a/2/3/1, a/1/0/3 and msg_0265), read from a
  pret/pokeheartgold checkout at build time; the talk engine follows the decomp's
  `overlay_02_02248728` and `overlay_01_02203A18`. Our part is the translation to Unova
  (`talk_mapping.json`: places, flags, Gen 5 species groups, Musical props).

The converted sprites and HGSS data are not stored in this repository; `tools/build_followers.py
--essentials DIR --hgss DIR` generates them from the pack's `Graphics/Characters/Followers/` sheets
and the pokeheartgold checkout.
