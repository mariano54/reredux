/* Follower talk engine (talk.c), shared with follow.c. */
#ifndef TALK_H
#define TALK_H

/* script command 0x89 ops (talk.s); 0 is follow.c's probe */
#define TALK_OP_FIRST   1
#define TALK_OP_BEGIN   1   /* face the player and pick a record -> 1 found */
#define TALK_OP_LEAD    2   /* -> party slot of the follower */
#define TALK_OP_ITEM    3   /* -> its held item */
#define TALK_OP_STEP    4   /* run the next step's motion + balloon (waits) -> 0 no steps left */
#define TALK_OP_MSG     5   /* -> the step's text id, 0 none */
#define TALK_OP_KEEP    6   /* -> 1: leave the last text open for the yes/no */
#define TALK_OP_FINISH  7   /* apply friendship / mood -> 1 end, 2 yes/no, 3 prop, 4 Shiny Leaf */
#define TALK_OP_ANSWER  8   /* ARG 0 yes / 1 no -> 1 chained to another record */
#define TALK_OP_REWARD  9   /* -> the record's prop / leaf number */
#define TALK_OP_END     10
#define TALK_OP_CUT     11  /* ARG party slot of the move's user: HGSS's reaction (waits) -> 1 if it reacted */
#define TALK_OP_STRENGTH 12
/* field moves in common script 1243 (build_followers.py add_field_moves); ARG party slot of the
 * move's user -> 1 if the follower used it itself (the script then skips the cut-in) */
#define TALK_OP_SURF    13  /* follow.c: hop, cry, then it jumps into the water (waits) */
#define TALK_OP_DIG     14  /* hop + cry (waits) */
#define TALK_OP_TELEPORT 15
#define TALK_OP_FLASH   16
#define TALK_OP_RECALL  17  /* follow.c: a visible follower goes back into its ball (waits) */
#define TALK_OP_LAST    17

/* Gen 5 type ids */
#define TYPE_NORMAL     0
#define TYPE_FLYING     2
#define TYPE_GROUND     4
#define TYPE_WATER      10
#define TYPE_GRASS      11
#define TYPE_PSYCHIC    13

#ifndef __ASSEMBLER__
int talk_op(void *field, void *fa, void *vm, u32 op, u32 arg, u16 *ret);
int talk_tick(void *field, void *fa);
void talk_offset(s32 *x, s32 *y, s32 *z);
void *talk_lead(void *gd, u32 *slot);
extern u32 talk_lead_sig;   /* hash of the party's bytes at the last talk_lead call (lead cache) */
/* HGSS's reaction to a field move the follower used (ov02_022507B4): +1 mood and two hops if the
 * move has one of its types, else one hop; then its cry if `cry`. -> 0 if it can't (not the lead,
 * hidden). talk_busy() is nonzero until it is over. */
int talk_react(void *field, void *fa, u32 slot, u32 type, u32 cry);
int talk_busy(void);

/* talk_select.c */
u32 talk_select(void *field, void *fa, void *pk, const u32 *hdr);
void talk_face_player(void *field, void *fa);

/* emote.c: HGSS balloon icon 0..13 not in B2 -> a task FLDEFF_GYOE_CheckEnd can poll, or 0 */
void *emote_hgss_start(void *field, void *fa, u32 icon);
#endif

#endif
