// libmelon: headless melonDS (interpreter, software renderer) as a C API for Python ctypes (warp timing harness).
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdarg>
#include <string>
#include <vector>
#include <fstream>
#include <sstream>
#include <memory>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include "NDS.h"
#include "NDSCart.h"
#include "Savestate.h"
#include "Platform.h"
#include "GPU.h"
#include "SPU.h"

using namespace melonDS;

#include "platform_part.inc"

namespace melonDS { extern u32 g_watch_act[32]; extern u32 g_prof_sel; extern unsigned long long* g_prof_tabB; extern unsigned long long g_prof_itcmB[0x4000]; }
namespace melonDS { extern u32 g_watch[32]; extern u32 g_watch_n; extern unsigned long long* g_wlog; extern u32 g_wlog_n, g_wlog_max; }
namespace melonDS { extern unsigned long long g_jit_halt;extern u32 g_swap_polys, g_swap_verts, g_swaps, g_swap_polys_max, g_swap_verts_max; }
namespace melonDS { extern unsigned long long* g_prof_tab; extern unsigned long long g_prof_itcm[0x4000]; extern unsigned long long g_prof_other, g_prof_halt; }
namespace melonDS { namespace NDSCart { extern unsigned long long g_cart_cmds, g_cart_bytes, g_cart_cycles; extern u32* g_cart_log; extern u32 g_cart_log_n, g_cart_log_max; } }

static NDS* nds;
static FILE* g_wav = nullptr;
static u32 g_wav_samples = 0;
static std::vector<std::vector<u8>> g_states(8);
static s16 g_abuf[8192 * 2];
static int g_last_samples = 0;
static double g_last_peak = 0;

static std::vector<u8> readfile(const char* p) {
    std::ifstream f(p, std::ios::binary);
    return std::vector<u8>((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
}

static void wav_header(FILE* f, u32 samples) {
    u32 rate = 32768, bytes = samples * 4;
    fseek(f, 0, SEEK_SET);
    fwrite("RIFF", 1, 4, f); u32 v = 36 + bytes; fwrite(&v, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
    v = 16; fwrite(&v, 4, 1, f); u16 h = 1; fwrite(&h, 2, 1, f); h = 2; fwrite(&h, 2, 1, f);
    fwrite(&rate, 4, 1, f); v = rate * 4; fwrite(&v, 4, 1, f); h = 4; fwrite(&h, 2, 1, f); h = 16; fwrite(&h, 2, 1, f);
    fwrite("data", 1, 4, f); fwrite(&bytes, 4, 1, f);
}

extern "C" {

int ml_init(const char* rom_path, const char* sav_path) {
    auto rom = readfile(rom_path);
    if (rom.empty()) return -1;
    std::vector<u8> sav;
    if (sav_path && *sav_path) sav = readfile(sav_path);
    NDSArgs args;
    args.JIT = std::nullopt;
#ifdef JIT_ENABLED
    {
        const char* j = getenv("ML_JIT");      // ML_JIT=1: JIT on (Watermelon / melonDS Android default)
        if (j && *j == '1') {
            JITArgs ja;
            const char* bs = getenv("ML_JIT_BLOCK");
            if (bs) ja.MaxBlockSize = atoi(bs);
            const char* fm = getenv("ML_JIT_FASTMEM");
            if (fm) ja.FastMemory = *fm == '1';
            args.JIT = ja;
        }
    }
#endif
    nds = new NDS(std::move(args));
    nds->Reset();
    NDSCart::NDSCartArgs cargs;
    if (!sav.empty()) {
        cargs.SRAM = std::make_unique<u8[]>(sav.size());
        memcpy(cargs.SRAM.get(), sav.data(), sav.size());
        cargs.SRAMLength = sav.size();
    }
    auto romp = std::make_unique<u8[]>(rom.size());
    memcpy(romp.get(), rom.data(), rom.size());
    auto cart = NDSCart::ParseROM(std::move(romp), rom.size(), nullptr, std::move(cargs));
    if (!cart) return -2;
    nds->SetNDSCart(std::move(cart));
    nds->Reset();
    nds->SetupDirectBoot("rom.nds");
    nds->SPU.SetOutputSampleRate(32768.0);
    nds->Start();
    return 0;
}

// one frame with keys held (bit = A,B,SELECT,START,RIGHT,LEFT,UP,DOWN,R,L,X,Y) and optional touch
int ml_frame(u32 keys, int touch, int tx, int ty) {
    nds->SetKeyMask(0xFFF & ~keys);
    if (touch) nds->TouchScreen(tx, ty); else nds->ReleaseScreen();
    nds->RunFrame();
    int total = 0;
    double peak = 0;
    for (;;) {
        int n = nds->SPU.ReadOutput(g_abuf, 8192);
        if (n <= 0) break;
        for (int i = 0; i < 2 * n; i++) { double a = std::abs((int)g_abuf[i]); if (a > peak) peak = a; }
        if (g_wav) { fwrite(g_abuf, 4, n, g_wav); g_wav_samples += n; }
        total += n;
        if (n < 8192) break;
    }
    g_last_samples = total;
    g_last_peak = peak;
    return total;
}

double ml_last_peak() { return g_last_peak; }

// mean luma (0..255) of a screen, every 4th pixel each way; and a 32-bit hash of the whole screen
double ml_luma(int screen) {
    u32* p = nds->GPU.Framebuffer[nds->GPU.FrontBuffer][screen].get();
    double sum = 0; int n = 0;
    for (int y = 0; y < 192; y += 4)
        for (int x = 0; x < 256; x += 4) {
            u32 c = p[y * 256 + x];
            sum += 0.299 * ((c >> 16) & 0xFF) + 0.587 * ((c >> 8) & 0xFF) + 0.114 * (c & 0xFF);
            n++;
        }
    return sum / n;
}

u32 ml_hash(int screen) {
    u32* p = nds->GPU.Framebuffer[nds->GPU.FrontBuffer][screen].get();
    u32 h = 2166136261u;
    for (int i = 0; i < 256 * 192; i++) { h ^= p[i] & 0xFFFFFF; h *= 16777619u; }
    return h;
}
u8* ml_ram() { return nds->MainRAM; }
u32 ml_ram_mask() { return nds->MainRAMMask; }
u32* ml_fb(int screen) { return nds->GPU.Framebuffer[nds->GPU.FrontBuffer][screen].get(); }
u32 ml_bright(int engine) { return engine ? nds->GPU.GPU2D_B.MasterBrightness : nds->GPU.GPU2D_A.MasterBrightness; }
u16 ml_read16(u32 addr) { return nds->ARM9Read16(addr); }
u32 ml_read32(u32 addr) { return nds->ARM9Read32(addr); }

void ml_cart(unsigned long long* out) {
    out[0] = NDSCart::g_cart_cmds; out[1] = NDSCart::g_cart_bytes; out[2] = NDSCart::g_cart_cycles;
}

int ml_state_mem_save(int slot) {
    Savestate s; nds->DoSavestate(&s); s.Finish();
    g_states[slot].assign((u8*)s.Buffer(), (u8*)s.Buffer() + s.Length());
    return (int)s.Length();
}

int ml_state_mem_load(int slot) {
    auto& v = g_states[slot];
    if (v.empty()) return -1;
    std::vector<u8> copy = v;
    Savestate s(copy.data(), copy.size(), false);
    bool ok = nds->DoSavestate(&s);
    return ok && !s.Error ? 0 : -2;
}

int ml_state_save(const char* path) {
    Savestate s; nds->DoSavestate(&s); s.Finish();
    FILE* f = fopen(path, "wb"); if (!f) return -1;
    fwrite(s.Buffer(), 1, s.Length(), f); fclose(f);
    return (int)s.Length();
}

int ml_state_load(const char* path) {
    auto st = readfile(path);
    if (st.empty()) return -1;
    Savestate s(st.data(), st.size(), false);
    bool ok = nds->DoSavestate(&s);
    return ok && !s.Error ? 0 : -2;
}

int ml_sram_dump(const char* path) {
    const u8* d = nds->GetNDSSave(); u32 l = nds->GetNDSSaveLength();
    FILE* f = fopen(path, "wb"); if (!f) return -1;
    fwrite(d, 1, l, f); fclose(f);
    return (int)l;
}

int ml_wav_start(const char* path) {
    if (g_wav) return -1;
    g_wav = fopen(path, "wb");
    if (!g_wav) return -2;
    g_wav_samples = 0;
    wav_header(g_wav, 0);
    return 0;
}

int ml_wav_stop() {
    if (!g_wav) return -1;
    wav_header(g_wav, g_wav_samples);
    fclose(g_wav);
    g_wav = nullptr;
    return (int)g_wav_samples;
}


// cycle-weighted ARM9 PC profile: start clears; dump writes "pc cycles" lines (nonzero) + other/halt totals
void ml_prof_start() {
    if (!g_prof_tab) g_prof_tab = (unsigned long long*)calloc(1 << 21, 8);
    else memset(g_prof_tab, 0, (1 << 21) * 8);
    memset(g_prof_itcm, 0, sizeof(g_prof_itcm));
    g_prof_other = g_prof_halt = 0;
}

int ml_prof_dump(const char* path, int stop) {
    if (!g_prof_tab) return -1;
    FILE* f = fopen(path, "w"); if (!f) return -2;
    fprintf(f, "other %llu\nhalt %llu\n", g_prof_other, g_prof_halt);
    for (u32 i = 0; i < (1u << 21); i++) if (g_prof_tab[i]) fprintf(f, "%08x %llu\n", 0x02000000 + i * 2, g_prof_tab[i]);
    for (u32 i = 0; i < 0x4000; i++) if (g_prof_itcm[i]) fprintf(f, "%08x %llu\n", 0x01FF8000 + i * 2, g_prof_itcm[i]);
    fclose(f);
    if (stop) { free(g_prof_tab); g_prof_tab = nullptr; }
    return 0;
}


// card read log: ROM addresses of the 0xB7 (read) commands
void ml_cartlog_start() {
    if (!NDSCart::g_cart_log) { NDSCart::g_cart_log_max = 1 << 22; NDSCart::g_cart_log = (u32*)malloc(4u << 22); }
    NDSCart::g_cart_log_n = 0;
}
u32 ml_cartlog_n() { return NDSCart::g_cart_log_n; }
u32* ml_cartlog() { return NDSCart::g_cart_log; }

// field-feel additions: 3D engine state per frame (bank flips on every geometry swap) and OAM
void ml_g3d(u32* out) {
    auto& g = nds->GPU.GPU3D;
    out[0] = g.CurRAMBank; out[1] = g.RenderNumPolygons; out[2] = g.NumPolygons; out[3] = g.NumVertices;
    out[4] = g.DispCnt; out[5] = g.FlushRequest;
}
u8* ml_oam() { return nds->GPU.OAM; }

// perf60: ARM9 halted/idle cycles (every mode, JIT too) and the ARM9 timestamp; JIT on?
unsigned long long ml_a9_halt() { return g_jit_halt; }
// RTC (season / time of day)
void ml_set_rtc(int y, int mo, int d, int h, int mi, int s) { nds->RTC.SetDateTime(y, mo, d, h, mi, s); }
void ml_get_rtc(int* out) { nds->RTC.GetDateTime(out[0], out[1], out[2], out[3], out[4], out[5]); }
// PC watchpoints (interpreter): set n addresses (exact instruction addresses, thumb without the 1 bit); the log holds
// (index << 56 | ARM9 timestamp) entries
void ml_watch_set(const u32* addrs, u32 n) {
    if (!g_wlog) { g_wlog_max = 1 << 22; g_wlog = (unsigned long long*)malloc(8ull << 22); }
    for (u32 i = 0; i < n && i < 32; i++) g_watch[i] = addrs[i];
    g_watch_n = n > 32 ? 32 : n;
    g_wlog_n = 0;
}
// actions per watch (0 log only, 1 -> profile table A, 2 -> table B) and table B start / dump
void ml_watch_act(const u32* acts, u32 n) { for (u32 i = 0; i < n && i < 32; i++) g_watch_act[i] = acts[i]; }
void ml_profB_start() {
    if (!g_prof_tabB) g_prof_tabB = (unsigned long long*)calloc(1 << 21, 8);
    else memset(g_prof_tabB, 0, (1 << 21) * 8);
    memset(g_prof_itcmB, 0, sizeof(g_prof_itcmB));
    g_prof_sel = 0;
}
int ml_profB_dump(const char* path) {
    if (!g_prof_tabB) return -1;
    FILE* f = fopen(path, "w"); if (!f) return -2;
    fprintf(f, "other 0\nhalt 0\n");
    for (u32 i = 0; i < (1u << 21); i++) if (g_prof_tabB[i]) fprintf(f, "%08x %llu\n", 0x02000000 + i * 2, g_prof_tabB[i]);
    for (u32 i = 0; i < 0x4000; i++) if (g_prof_itcmB[i]) fprintf(f, "%08x %llu\n", 0x01FF8000 + i * 2, g_prof_itcmB[i]);
    fclose(f);
    return 0;
}
u32 ml_wlog_n() { return g_wlog_n; }
unsigned long long* ml_wlog() { return g_wlog; }
void ml_wlog_clear() { g_wlog_n = 0; }
// polygons / vertices of the last swapped list, swaps so far, peaks; DISP3DCNT (bit 13 = RAM overflow)
void ml_swapinfo(u32* out) {
    out[0] = g_swap_polys; out[1] = g_swap_verts; out[2] = g_swaps; out[3] = g_swap_polys_max; out[4] = g_swap_verts_max;
    out[5] = nds->GPU.GPU3D.DispCnt;
}
unsigned long long ml_a9_ts() { return nds->ARM9Timestamp; }
int ml_jit_on() {
#ifdef JIT_ENABLED
    return nds->IsJITEnabled() ? 1 : 0;
#else
    return 0;
#endif
}

// exp60: cumulative ARM9 halted cycles / other-region cycles while profiling (ml_prof_start)
unsigned long long ml_prof_halt() { return g_prof_halt; }
unsigned long long ml_prof_other() { return g_prof_other; }
// sum of the PC table (main RAM + ITCM) = executed cycles there
unsigned long long ml_prof_sum() {
    unsigned long long s = 0;
    if (g_prof_tab) for (u32 i = 0; i < (1u << 21); i++) s += g_prof_tab[i];
    for (u32 i = 0; i < 0x4000; i++) s += g_prof_itcm[i];
    return s;
}
// cycles executed in [lo, hi) since ml_prof_start
unsigned long long ml_prof_range(u32 lo, u32 hi) {
    unsigned long long s = 0;
    if (!g_prof_tab) return 0;
    for (u32 a = lo & ~1u; a < hi; a += 2) {
        if ((a & 0xFF000000) == 0x02000000) s += g_prof_tab[(a & 0x3FFFFF) >> 1];
        else if (a >= 0x01FF8000 && a < 0x02000000) s += g_prof_itcm[(a - 0x01FF8000) >> 1];
    }
    return s;
}
// 3D: geometry engine polygon / vertex counts of the list being built, and the displayed one
void ml_g3d_counts(u32* out) {
    auto& g = nds->GPU.GPU3D;
    out[0] = g.NumPolygons; out[1] = g.NumVertices; out[2] = g.RenderNumPolygons; out[3] = g.CurRAMBank;
}

}
