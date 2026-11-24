; Talking to the follower: common script 1230, script id TALK_SCRIPT (text bank: story 208).
; HGSS's std_following_mon: talk blip, lock, then Task_FollowMonInteract, which talk.c runs one step
; at a time through command 0x89 (ops in talk.h):
;   .hword 0x0089, OP, DEST_VAR, ARG
; For each step of the chosen record: its motion (hop, shake...) with the cry or sound, its emote
; balloon, then its text. Then friendship / mood change, and a yes/no (whose answer picks the
; next record), or a Musical prop (HGSS: Fashion Case accessory).
; TALK_MSG_PROP_OWNED is replaced with the text id of that line.
scr_follow:
    SEPlay 0x96E                        ; SEQ_SE_DP_SELECT, as in HGSS
    ActorPauseAll
    .hword 0x0089, 1, 0x8020, 0         ; BEGIN: face the player, pick a record
    StackPush 0x8020
    StackPushConst 0
    StackCmp 5
    VMJumpIf 255, @scr_follow_end       ; none
    .hword 0x0089, 2, 0x8021, 0         ; LEAD: party slot
    .hword 0x0089, 3, 0x8022, 0         ; ITEM: held item
    WordSetPartyPokeName 0, 0x8021
    WordSetPlayerName 2
    WordSetItemName 4, 0x8022
scr_follow_step:
    .hword 0x0089, 4, 0x8023, 0         ; STEP: motion + balloon (waits)
    StackPush 0x8023
    StackPushConst 0
    StackCmp 5
    VMJumpIf 255, @scr_follow_finish    ; no steps left
    .hword 0x0089, 5, 0x8024, 0         ; MSG: text id
    StackPush 0x8024
    StackPushConst 0
    StackCmp 5
    VMJumpIf 255, @scr_follow_step
    MsgSystem 0x8024, 2
    MsgWaitAdvance
    .hword 0x0089, 6, 0x8025, 0         ; KEEP: the yes/no question stays up
    StackPush 0x8025
    StackPushConst 0
    StackCmp 1
    VMJumpIf 255, @scr_follow_step
    InputWaitAB
    MsgSystemClose
    VMJump @scr_follow_step
scr_follow_finish:
    .hword 0x0089, 7, 0x8025, 0         ; FINISH: friendship / mood -> 1 end, 2 yes/no, 3 prop
    StackPush 0x8025
    StackPushConst 2
    StackCmp 1
    VMJumpIf 255, @scr_follow_prop
    YesNoWin 0x8026
    MsgSystemClose
    .hword 0x0089, 8, 0x8020, 0x8026    ; ANSWER: chain to the yes / no record
    StackPush 0x8020
    StackPushConst 0
    StackCmp 5
    VMJumpIf 255, @scr_follow_end
    VMJump @scr_follow_step             ; (its conditions aren't checked, as in HGSS)
scr_follow_prop:
    StackPush 0x8025
    StackPushConst 3
    StackCmp 1
    VMJumpIf 255, @scr_follow_end
    .hword 0x0089, 9, 0x8027, 0         ; REWARD: prop id
    MusicalIsPropOwned 0x8027, 0x8028
    StackPush 0x8028
    StackPushConst 0
    StackCmp 1
    VMJumpIf 255, @scr_follow_owned
    WorkSet 0x8008, 0x8027
    WorkSetConst 0x8009, 1
    RTCallGlobal 10466                  ; B2's prop gift: fanfare, "put it in the Prop Case"
    VMJump @scr_follow_end
scr_follow_owned:                       ; (HGSS: "But the Fashion Case is already full!")
    WordSetMusicalInfo 1, 1, 0x8027
    MsgSystem TALK_MSG_PROP_OWNED, 2
    MsgWaitAdvance
    InputWaitAB
    MsgSystemClose
scr_follow_end:
    .hword 0x0089, 10, 0x8020, 0        ; END
    WorkSetConst 0x8020, 0
    WorkSetConst 0x8021, 0
    WorkSetConst 0x8022, 0
    WorkSetConst 0x8023, 0
    WorkSetConst 0x8024, 0
    WorkSetConst 0x8025, 0
    WorkSetConst 0x8026, 0
    WorkSetConst 0x8027, 0
    WorkSetConst 0x8028, 0
    RTFinishSubEvents
    ActorUnlockAll
    VMHalt
