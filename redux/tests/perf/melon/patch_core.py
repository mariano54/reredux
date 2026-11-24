"""patch_core.py SRC: the perf benchmark's additions to a copy of the headless melonDS core (tmp/melonheadless/src,
which already has the cycle-weighted ARM9 PC profile g_prof_* in ARM.cpp and the card counters in NDSCart.cpp):
  - g_jit_halt: ARM9 halted / idle-loop cycles in every execution mode (busy % under the JIT too)
  - PC watchpoints (interpreter): log (index, ARM9 timestamp), and per-watch actions that switch the profile between
    table A and table B (e.g. B = inside the 3D draws)
  - GPU3D: polygons / vertices of every swapped list (last, peak) and the swap count
Idempotent (a patched file is left alone)."""
import os, sys

src = os.path.join(sys.argv[1], 'src', 'src')


def patch(rel, pairs, marker):
    p = os.path.join(src, rel)
    s = open(p).read()
    if marker in s:
        return
    for old, new in pairs:
        if s.count(old) != 1:
            sys.exit(f'patch_core: {rel}: anchor not found once: {old[:60]!r}')
        s = s.replace(old, new)
    open(p, 'w').write(s)
    print('patched', rel)


patch('ARM.cpp', [
    ("unsigned long long g_prof_other = 0, g_prof_halt = 0;",
     "unsigned long long g_prof_other = 0, g_prof_halt = 0;\n"
     "unsigned long long g_jit_halt = 0;   // ARM9 halted / idle-loop cycles (any mode)\n"
     "u32 g_watch[32]; u32 g_watch_n = 0; unsigned long long* g_wlog = nullptr; u32 g_wlog_n = 0, g_wlog_max = 0;"),
    ("""static inline void prof_add(u32 pc, u32 cyc)
{
    if ((pc & 0xFF000000) == 0x02000000) g_prof_tab[(pc & 0x3FFFFF) >> 1] += cyc;
    else if (pc >= 0x01FF8000 && pc < 0x02000000) g_prof_itcm[(pc - 0x01FF8000) >> 1] += cyc;""",
     """u32 g_watch_act[32]; u32 g_prof_sel = 0; unsigned long long* g_prof_tabB = nullptr; unsigned long long g_prof_itcmB[0x4000];
static inline void prof_add(u32 pc, u32 cyc)
{
    if (g_prof_sel && g_prof_tabB) {
        if ((pc & 0xFF000000) == 0x02000000) g_prof_tabB[(pc & 0x3FFFFF) >> 1] += cyc;
        else if (pc >= 0x01FF8000 && pc < 0x02000000) g_prof_itcmB[(pc - 0x01FF8000) >> 1] += cyc;
        else g_prof_other += cyc;
        return;
    }
    if ((pc & 0xFF000000) == 0x02000000) g_prof_tab[(pc & 0x3FFFFF) >> 1] += cyc;
    else if (pc >= 0x01FF8000 && pc < 0x02000000) g_prof_itcm[(pc - 0x01FF8000) >> 1] += cyc;"""),
    ("            if (g_prof_tab) g_prof_halt += NDS.ARM9Target - NDS.ARM9Timestamp;\n            NDS.ARM9Timestamp = NDS.ARM9Target;",
     "            if (g_prof_tab) g_prof_halt += NDS.ARM9Target - NDS.ARM9Timestamp;\n"
     "            g_jit_halt += NDS.ARM9Target - NDS.ARM9Timestamp;\n            NDS.ARM9Timestamp = NDS.ARM9Target;"),
    ("""                    if ((Halted == 1 || IdleLoop) && NDS.ARM9Timestamp < NDS.ARM9Target)
                    {
                        Cycles = 0;
                        NDS.ARM9Timestamp = NDS.ARM9Target;""",
     """                    if ((Halted == 1 || IdleLoop) && NDS.ARM9Timestamp < NDS.ARM9Target)
                    {
                        Cycles = 0;
                        g_jit_halt += NDS.ARM9Target - NDS.ARM9Timestamp;
                        NDS.ARM9Timestamp = NDS.ARM9Target;"""),
    ("                    if (g_prof_tab) g_prof_halt += NDS.ARM9Target - NDS.ARM9Timestamp - Cycles;",
     "                    if (g_prof_tab) g_prof_halt += NDS.ARM9Target - NDS.ARM9Timestamp - Cycles;\n"
     "                    g_jit_halt += NDS.ARM9Target - NDS.ARM9Timestamp - Cycles;"),
    ("            u32 prof_pc = R[15] - ((CPSR & 0x20) ? 2 : 4);\n",
     """            u32 prof_pc = R[15] - ((CPSR & 0x20) ? 2 : 4);
            if (g_watch_n) {
                for (u32 wi = 0; wi < g_watch_n; wi++)
                    if (g_watch[wi] == prof_pc) {
                        if (g_watch_act[wi]) g_prof_sel = g_watch_act[wi] - 1;
                        if (g_wlog_n < g_wlog_max)
                            g_wlog[g_wlog_n++] = ((unsigned long long)wi << 56) | (NDS.ARM9Timestamp & 0x00FFFFFFFFFFFFFFull);
                    }
            }
"""),
], 'g_jit_halt')

patch('GPU3D.cpp', [
    ("void GPU3D::VBlank() noexcept\n{",
     "u32 g_swap_polys = 0, g_swap_verts = 0, g_swaps = 0, g_swap_polys_max = 0, g_swap_verts_max = 0;\n"
     "void GPU3D::VBlank() noexcept\n{"),
    ("""        if (FlushRequest)
        {
            CurRAMBank = CurRAMBank?0:1;""",
     """        if (FlushRequest)
        {
            g_swap_polys = NumPolygons; g_swap_verts = NumVertices; g_swaps++;
            if (NumPolygons > g_swap_polys_max) g_swap_polys_max = NumPolygons;
            if (NumVertices > g_swap_verts_max) g_swap_verts_max = NumVertices;
            CurRAMBank = CurRAMBank?0:1;"""),
], 'g_swap_polys')
