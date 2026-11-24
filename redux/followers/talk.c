/* Talking to the follower: a port of HGSS's Task_FollowMonInteract (ov02_02250110 and friends; see
 * build/hgss_talk/SPEC.md). talk.s drives it through script command 0x89 (follow.c), one op per
 * stage; the motions and emote balloons run here, once per field tick.
 *
 * Data (built by tools/follower_talk.py from the HGSS decomp, appended to arc TALK_ARC as member
 * TALK_DAT): a header of u32 offsets, then
 *   records   52-byte HGSS talk records (NARC 223), msg ids already turned into text ids
 *   motions   80-byte motion scripts (NARC 224)
 *   lists     20-byte condition entries: 70 generic ones (eval index 30..99), then 30 per list
 *   zones     u8 per zone each: condition list (0xFF none), place role, gym badge (0xFF none)
 *   species   u8 per species: HGSS species group (NARC 233, extended to Gen 5)
 * Read piece by piece with GFL_ArcSysReadRange, so nothing big is kept in RAM. */
#include "follow.h"
#include "talk.h"

enum { H_RECORDS, H_MOTIONS, H_GENERIC, H_LISTS, H_ZONE_LIST, H_ZONE_ROLE, H_ZONE_BADGE, H_SPECIES, H_NZONES,
       H_NSPECIES, H_COUNT };

#define REC_SIZE        52
#define MOTION_SIZE     80
#define ENTRY_SIZE      20
#define GENERIC_COUNT   70
#define LIST_COUNT      30
#define STEPS           5

#define SND_CRY         2379    /* HGSS SEQ_SE_END + 1: the lead's cry */
#define MOTION_HOP      3       /* HGSS's standard hop */
#define CRY_LOW_NUM     85      /* > SND_CRY: cry at HGSS pitch -96 (-1.5 semitones): speed * (1 - 85/1024) */
#define SE_EMOTE        0x54C   /* SEQ_SE_DECIDE1: B2 has no SEQ_SE_DP_DECIDE, which HGSS balloons play */
#define EMOTE_TIMEOUT   90      /* ticks */
#define CRY_TIMEOUT     150

static struct {
    u32 hdr[H_COUNT];
    u8 rec[REC_SIZE];
    u8 step;                /* next step of rec */
    u8 stage;               /* see talk_tick */
    u8 freeze;              /* text on screen: the follower's animation stops */
    u8 lead;                /* party slot of the follower */
    /* motion player */
    u8 mo[MOTION_SIZE];
    u8 mi, mleft;
    u16 sound;
    u8 face0;
    u8 emote;
    u8 wait;
    s8 ofs[3];              /* x, height, z offsets (world units) added to the follower's draw offset */
    u8 cry_pending;
    u8 cry_low;
    u8 hops;                /* field-move reaction: hops still to do after this motion */
    u8 cry_after;           /* field-move reaction: the cry follows the hops */
    u8 cry_wait;            /* ticks left waiting for it to end */
    u16 cry_h;              /* PokeVoice handle of the last cry */
    void *balloon;          /* B2 balloon effect task while it runs */
} tk;

enum { ST_IDLE, ST_MOTION, ST_EMOTE, ST_DONE, ST_CRY };

static void read_data(void *dst, u32 ofs, u32 len)
{
    GFL_ArcSysReadRange(dst, TALK_ARC, TALK_DAT, ofs, len);
}

static u16 rd16(const u8 *p)
{
    return p[0] | p[1] << 8;
}

/* ------------------------------------------------------------------------------------------ */
/* sounds */

static void play_cry_now(void *pk, u32 low)
{
    u16 h = PokeVoice_Play(PokeParty_GetParam(pk, PF_SPECIES, 0), PokeParty_GetParam(pk, PF_FORME, 0),
                           0x40, 0, 0, 0, 0, 0);
    if (low)
        PokeVoice_AdjustSpeed(h, -(s32)(PokeVoice_GetSpeed(h) * CRY_LOW_NUM >> 10));
    tk.cry_h = h;
}

/* the step's sound: a plain SE, or the lead's cry (normal / low) */
static void play_sound(u32 snd)
{
    if (!snd)
        return;
    if (snd < SND_CRY) {
        GFL_SndSEPlay(snd);
        return;
    }
    tk.cry_pending = 1;     /* PokeVoice_Play busy-waits while sound data loads: start it when idle */
    tk.cry_low = snd > SND_CRY;
}

/* ------------------------------------------------------------------------------------------ */
/* motion player (HGSS ov02_02250004 / ov02_0224FF5C): per entry, on its first tick: position and
 * height, then the sound, then the facing; the entry lasts max(1, frames) ticks. */

static void motion_start(u32 id)
{
    read_data(tk.mo, tk.hdr[H_MOTIONS] + (id - 1) * MOTION_SIZE, MOTION_SIZE);
    tk.mi = 0;
    tk.mleft = 0;
    tk.ofs[0] = tk.ofs[1] = tk.ofs[2] = 0;
    tk.stage = ST_MOTION;
}

static int motion_tick(void *fa, u32 species)
{
    if (tk.mleft == 0) {
        if (tk.mi >= 10 || tk.mo[tk.mi * 8] == 0xFF)
            return 1;
        const u8 *e = tk.mo + tk.mi * 8;
        tk.ofs[0] += (s8)e[2];
        if (species != 50 && species != 51)     /* Diglett, Dugtrio stay in the ground */
            tk.ofs[1] += (s8)e[3];
        tk.ofs[2] += (s8)e[4];
        if (e[5])
            play_sound(tk.sound);
        if (e[0])
            SetActorFaceDir(fa, e[0] - 1);
        tk.mleft = e[1] ? e[1] : 1;
        tk.mi++;
    }
    tk.mleft--;
    return 0;
}

/* ------------------------------------------------------------------------------------------ */
/* emote balloons (HGSS ov01_02203AB4): record emote 1..14 = HGSS icon emote-1. B2 has four of them
 * (!, ?, music note, ...); emote.c adds HGSS's others. */

static void *emote_start(void *field, void *fa, u32 emote)
{
    static const s8 native[15] = {-1, -1, -1, -1, -1, -1, -1, 2, 1, 0, -1, -1, -1, 3, -1};
    if (emote > 14)
        return 0;   /* ignored, as in HGSS */
    void *tcb;
    if (native[emote] >= 0)
        tcb = FLDEFF_GYOE_SetMMdlAuto(Field_GetFieldEffects(field), fa, native[emote], 0);
    else
        tcb = emote_hgss_start(field, fa, emote - 1);
    if (tcb)
        GFL_SndSEPlay(SE_EMOTE);
    return tcb;
}

/* ------------------------------------------------------------------------------------------ */

/* The lead (first party Pokémon that is no egg and not fainted), cached. B2 keeps party Pokémon
 * encrypted: every PokeParty_GetParam decrypts the Pokémon, checks its sum and encrypts it again, and
 * the lead lookups of a field tick (follow.c, talk_tick) took ~27k ARM9 cycles per frame (2.4% of a
 * frame, every frame: emulator load). Any change to a party Pokémon changes its encrypted bytes, so
 * the lookup is redone only when a hash of the party's raw bytes changes (any single changed word
 * always changes it). talk_lead_sig: that hash at the last call (follow.c caches on it too). */
u32 talk_lead_sig;
static void *lc_party, *lc_pk;
static u32 lc_slot, lc_valid, lc_sig, lc_vbl;

static u32 party_hash(void *party, u32 n)
{
    const u32 *w = PokeParty_GetPkm(party, 0);
    u32 h = n + 1, i;
    for (i = 0; i < n * (0xDC / 4); i++)
        h = ((h << 5) + h) ^ w[i];
    return h;
}

void *talk_lead(void *gd, u32 *slot)
{
    void *party = GameData_GetParty(gd);
    u32 n = PokeParty_GetPkmCount(party);
    /* hashed once per frame (talk_lead runs ~3 times per field tick); within a frame only our own
     * mood / friendship writes change the party, and those change neither the lead nor its sprite */
    u32 vbl = *(volatile u32 *)0x027FFC3C, sig;
    if (lc_valid && vbl == lc_vbl && party == lc_party)
        sig = lc_sig;
    else
        sig = party_hash(party, n <= 6 ? n : 6);
    lc_vbl = vbl;
    talk_lead_sig = sig;
    if (!lc_valid || sig != lc_sig || party != lc_party) {
        /* (GetParam decrypts and re-encrypts with the same key: the bytes, and sig, stay the same) */
        lc_valid = 1;
        lc_sig = sig;
        lc_party = party;
        lc_pk = 0;
        for (u32 i = 0; i < n; i++) {
            void *pk = PokeParty_GetPkm(party, i);
            if (PokeParty_GetParam(pk, PF_IS_EGG, 0) || PokeParty_GetParam(pk, PF_NOW_HP, 0) == 0)
                continue;
            lc_slot = i;
            lc_pk = pk;
            break;
        }
    }
    if (lc_pk)
        *slot = lc_slot;
    return lc_pk;
}

/* Called once per field tick by follow.c. Returns nonzero while the follower's animation must stop. */
int talk_tick(void *field, void *fa)
{
    void *gd = GSYS_GetGameData(*(void **)((u8 *)field + 0x04));
    u32 slot;
    void *pk = talk_lead(gd, &slot);
    if (tk.cry_pending && pk && !Snd_IsLoading()) {
        play_cry_now(pk, tk.cry_low);
        tk.cry_pending = 0;
    }
    if (!fa)
        tk.stage = ST_IDLE;
    switch (tk.stage) {
    case ST_MOTION:
        if (!motion_tick(fa, pk ? PokeParty_GetParam(pk, PF_SPECIES, 0) : 0))
            break;
        if (tk.hops) {
            tk.hops--;
            motion_start(MOTION_HOP);
            break;
        }
        tk.ofs[0] = tk.ofs[1] = tk.ofs[2] = 0;
        SetActorFaceDir(fa, tk.face0);
        if (tk.cry_after) {
            tk.cry_after = 0;
            play_sound(SND_CRY);
            tk.cry_wait = CRY_TIMEOUT;
            tk.stage = ST_CRY;
            break;
        }
        tk.stage = ST_EMOTE;
        tk.wait = 0;
        /* fall through */
    case ST_EMOTE:
        if (tk.wait == 0) {
            tk.balloon = tk.emote ? emote_start(field, fa, tk.emote) : 0;
            if (!tk.balloon) {
                tk.stage = ST_DONE;
                break;
            }
            tk.wait = EMOTE_TIMEOUT;
        }
        /* B2 polls the balloon until it reports its end (it then removes itself); HGSS waits one
         * more frame after it */
        if (tk.balloon && (FLDEFF_GYOE_CheckEnd(tk.balloon) || --tk.wait == 1)) {
            tk.balloon = 0;
            tk.wait = 1;
        } else if (!tk.balloon) {
            tk.stage = ST_DONE;
        }
        break;
    case ST_CRY:    /* HGSS waits for IsCryFinished */
        if (!--tk.cry_wait || (!tk.cry_pending && !PokeVoice_IsPlaying(tk.cry_h)))
            tk.stage = ST_DONE;
        break;
    }
    return tk.freeze;
}

void talk_offset(s32 *x, s32 *y, s32 *z)
{
    *x = tk.ofs[0];
    *y = tk.ofs[1];
    *z = tk.ofs[2];
}

int talk_busy(void)
{
    return tk.stage != ST_DONE && tk.stage != ST_IDLE;
}

static int wait_steps(void *vm, void *env)
{
    (void)vm;
    (void)env;
    return !talk_busy();
}

static u32 nsteps(void)
{
    u32 n = 0;
    while (n < STEPS && rd16(tk.rec + n * 8) != 0xFFFF)
        n++;
    return n;
}

static void load_record(u32 id)
{
    read_data(tk.rec, tk.hdr[H_RECORDS] + (id - 1) * REC_SIZE, REC_SIZE);
    tk.step = 0;
}

static s32 clamp(s32 v, s32 lo, s32 hi)
{
    return v < lo ? lo : v > hi ? hi : v;
}

static void add_mood(void *pk, s32 d)
{
    s32 m = (s8)PokeParty_GetParam(pk, PF_MOOD, 0) + d;
    PokeParty_SetParam(pk, PF_MOOD, (u8)clamp(m, -127, 127));
}

/* HGSS ov02_02250780 + ov02_022507B4: a move of one of its types makes it hop twice (and +1 mood),
 * else once. Diglett and Dugtrio don't hop. -> 0 if there is nothing to animate */
static int hop_start(void *fa, void *pk, u32 type)
{
    tk.hops = 0;
    if (PokeParty_GetParam(pk, PF_TYPE1, 0) == type || PokeParty_GetParam(pk, PF_TYPE2, 0) == type) {
        tk.hops = 1;
        add_mood(pk, 1);
    }
    u32 species = PokeParty_GetParam(pk, PF_SPECIES, 0);
    if (species == 50 || species == 51)
        return 0;
    read_data(tk.hdr, 0, sizeof(tk.hdr));
    tk.sound = 0;
    tk.emote = 0;
    tk.face0 = GetActorFaceDir(fa);
    motion_start(MOTION_HOP);
    return 1;
}

int talk_react(void *field, void *fa, u32 slot, u32 type, u32 cry)
{
    u32 lead;
    void *pk = talk_lead(GSYS_GetGameData(*(void **)((u8 *)field + 0x04)), &lead);
    if (!pk || !fa || slot != lead || CheckActorFlag(fa, 0x4))
        return 0;
    tk.lead = lead;
    tk.cry_after = cry;
    if (!hop_start(fa, pk, type)) {
        tk.cry_after = 0;
        tk.stage = ST_DONE;
        if (cry) {
            play_sound(SND_CRY);
            tk.cry_wait = CRY_TIMEOUT;
            tk.stage = ST_CRY;
        }
    }
    return 1;
}

/* Script command 0x89 ops >= TALK_OP_FIRST (talk.s); ret = value for the destination variable.
 * Returns 1 when the script must wait (a native callback was set). */
int talk_op(void *field, void *fa, void *vm, u32 op, u32 arg, u16 *ret)
{
    void *gd = GSYS_GetGameData(*(void **)((u8 *)field + 0x04));
    u32 slot = 0;
    void *pk = talk_lead(gd, &slot);
    *ret = 0;
    switch (op) {
    case TALK_OP_BEGIN: {       /* face the player, pick a record: ret = 1 if there is one */
        read_data(tk.hdr, 0, sizeof(tk.hdr));
        tk.stage = ST_IDLE;
        tk.freeze = 0;
        if (!pk || !fa)
            break;
        tk.lead = slot;
        talk_face_player(field, fa);
        u32 id = talk_select(field, fa, pk, tk.hdr);
#ifdef TALK_DEBUG_RECORD
        id = TALK_DEBUG_RECORD;     /* test builds: always this record */
#endif
        if (id) {
            load_record(id);
            *ret = 1;
        }
        break;
    }
    case TALK_OP_LEAD:
        *ret = tk.lead;
        break;
    case TALK_OP_ITEM:
        *ret = pk ? PokeParty_GetParam(pk, PF_ITEM, 0) : 0;
        break;
    case TALK_OP_STEP: {        /* run the next step's motion and balloon: ret = 0 when none is left */
        tk.freeze = 0;
        if (tk.step >= nsteps() || !fa)
            break;
        const u8 *s = tk.rec + tk.step * 8;
        u32 motion = rd16(s);
        tk.sound = rd16(s + 4);
        tk.emote = s[6];
        tk.face0 = GetActorFaceDir(fa);
        *ret = 1;
        if (motion) {
            motion_start(motion);   /* its sound plays on the entry marked for it */
        } else {
            tk.stage = ST_EMOTE;
            tk.wait = 0;
        }
        VM_SetNativeCallback(vm, wait_steps);
        return 1;
    }
    case TALK_OP_MSG: {         /* the step's text id (0 none); freezes the follower while shown */
        const u8 *s = tk.rec + tk.step * 8;
        *ret = rd16(s + 2);
        tk.freeze = *ret != 0;
        tk.step++;
        break;
    }
    case TALK_OP_KEEP:          /* 1: last step of a yes/no record, leave the text box open */
        *ret = tk.step >= nsteps() && tk.rec[0x28];
        break;
    case TALK_OP_FINISH: {      /* friendship / mood deltas; ret = 1 end, 2 yes/no, 3 prop, 4 leaf */
        tk.freeze = 0;
        if (pk) {
            s32 f = PokeParty_GetParam(pk, PF_FRIENDSHIP, 0) + (s8)tk.rec[0x30];
            PokeParty_SetParam(pk, PF_FRIENDSHIP, clamp(f, 0, 255));
            s32 m = (s8)PokeParty_GetParam(pk, PF_MOOD, 0) + (s8)tk.rec[0x31];
            PokeParty_SetParam(pk, PF_MOOD, (u8)clamp(m, -127, 127));
        }
        *ret = tk.rec[0x28] ? 2 : tk.rec[0x32] ? 3 : tk.rec[0x33] ? 4 : 1;
        break;
    }
    case TALK_OP_ANSWER: {      /* arg 0 yes / 1 no: chain to that record (ret = 1) or end */
        u32 id = rd16(tk.rec + (arg == 0 ? 0x2C : 0x2E));
        if (id) {
            load_record(id);
            *ret = 1;
        }
        break;
    }
    case TALK_OP_REWARD:        /* the record's Musical prop (stored + 1 by follower_talk.py) */
        *ret = tk.rec[0x32] ? tk.rec[0x32] - 1 : 0;
        break;
    case TALK_OP_END:
        tk.stage = ST_IDLE;
        tk.freeze = 0;
        break;
    case TALK_OP_CUT:
    case TALK_OP_STRENGTH:
        /* HGSS after Cut / Strength used by the follower (the script still shows the cut-in):
         * Cut raises its mood by 20, then the hops */
        if (!pk || !fa || arg != slot || CheckActorFlag(fa, 0x4))
            break;
        if (op == TALK_OP_CUT)
            add_mood(pk, 20);
        tk.cry_after = 0;
        if (!hop_start(fa, pk, op == TALK_OP_CUT ? TYPE_GRASS : TYPE_NORMAL))
            break;
        *ret = 1;
        VM_SetNativeCallback(vm, wait_steps);
        return 1;
    case TALK_OP_DIG:
    case TALK_OP_TELEPORT:
    case TALK_OP_FLASH:
        /* HGSS Task_FieldDig / Task_FieldTeleport / the Flash script: if the follower is the user
         * (and the player walks), no cut-in: it hops (two for a Ground / Psychic follower), then
         * its cry plays to the end */
        if (FieldPlayer_GetExState(*(void **)((u8 *)field + 0x94)) != 0
            || !talk_react(field, fa, arg, op == TALK_OP_DIG ? TYPE_GROUND : TYPE_PSYCHIC, 1))
            break;
        *ret = 1;
        VM_SetNativeCallback(vm, wait_steps);
        return 1;
    }
    return 0;
}
