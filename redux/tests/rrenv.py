"""rrenv.py : paths and emulator environment for the ReRedux test harness (redux/tests). Imported first by every test
script (one bootstrap line), so nothing in the harness hard-codes a worktree.

  RR_T     redux/tests (this directory)
  RR_RX    redux/
  RR_REPO  the repository root
  RR_B     the build tree the tests read and write: $RR_B (rr.py sets it to the run's shadow tree: test outputs in real
           directories, everything else symlinked to redux/build), else $REDUX_BUILD, else redux/build
  RR_PY    the emulator Python (py-desmume 0.0.9 + Pillow + numpy): $REDUX_EMU_PY, else redux/build/emu-venv/bin/python,
           else this interpreter
  RR_MEL   headless-melonDS scripts dir (mel.py + ../lib/libbf.dylib): $REDUX_MELON_SCRIPTS or build/melon-lib/scripts
  RR_DSV   DeSmuME's battery-save dir: $XDG_CONFIG_HOME/desmume (rr.py gives every job its own), else ~/.config/desmume

Emulator setup done here, before any DeSmuME is created: SDL's dummy video / audio drivers (no Dock icon or window;
RR_SDL_WINDOW=1 keeps the real ones) and, with RR_DESMUME_THREADS=N, N SoftRasterizer threads instead of one per core
(rendering results are identical; only the CPU split changes)."""
import os
import sys

RR_T = os.path.dirname(os.path.abspath(__file__))
RR_RX = os.path.dirname(RR_T)
RR_REPO = os.path.dirname(RR_RX)
RR_B = os.environ.get('RR_B') or os.environ.get('REDUX_BUILD') or os.path.join(RR_RX, 'build')
RR_REAL_B = os.environ.get('REDUX_BUILD') or os.path.join(RR_RX, 'build')


def _first(*cands):
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


RR_PY = (os.environ.get('REDUX_EMU_PY') or _first(os.path.join(RR_REAL_B, 'emu-venv', 'bin', 'python')) or sys.executable)
RR_MEL = (os.environ.get('REDUX_MELON_SCRIPTS') or _first(os.path.join(RR_REAL_B, 'melon-lib', 'scripts')) or '')
RR_DSV = os.path.join(os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config'), 'desmume')

if not os.environ.get('RR_SDL_WINDOW'):
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

_CORES_OFF = 0x10CC          # CommonSettings.num_cores in py-desmume 0.0.9's libdesmume.dylib (probed: = os.cpu_count())


def tune_desmume():
    """apply RR_DESMUME_THREADS (SoftRasterizer thread count) before the first DeSmuME(); a no-op if unset or if the
    library doesn't look like the probed build"""
    n = os.environ.get('RR_DESMUME_THREADS')
    if not n or getattr(tune_desmume, 'done', False):
        return
    tune_desmume.done = True
    try:
        import ctypes
        import desmume.emulator as de
        lib = ctypes.CDLL(os.path.join(os.path.dirname(de.__file__), 'libdesmume.dylib'))
        cell = ctypes.c_int.from_address(ctypes.addressof(ctypes.c_char.in_dll(lib, 'CommonSettings')) + _CORES_OFF)
        if cell.value == os.cpu_count():
            cell.value = max(1, int(n))
    except Exception as e:                      # not the probed library: leave the default
        print('rrenv: RR_DESMUME_THREADS not applied:', e, file=sys.stderr)


RR_SKIP_RENDER = os.environ.get('RR_SKIP_RENDER') == '1'
RENDER_TAIL = 3          # frames rendered before any frame that may be looked at (3D output lags 2D by a frame or two)


def skip_frames(emu, n):
    """the caller knows nothing looks at the screen during the next n frames: with RR_SKIP_RENDER=1 DeSmuME skips
    drawing them (2D + 3D; the emulation itself is identical). step(n) asks for n - RENDER_TAIL."""
    if RR_SKIP_RENDER and n > 0:
        emu.__dict__['_rr_hint'] = max(emu.__dict__.get('_rr_hint', 0), n)


def no_skip(emu):
    emu.__dict__['_rr_hint'] = 0


def _install_render_skip():
    """DeSmuME.cycle skips drawing while a skip_frames() hint lasts (never while display capture is on: it writes
    VRAM); DeSmuME.screenshot prints RR-RENDER-STALE if fewer than RENDER_TAIL frames were drawn since a skipped one
    (rr.py fails such a job, so a test can never look at a stale picture)"""
    import desmume.emulator as de
    D = de.DeSmuME
    if getattr(D, '_rr_patched', False):
        return
    cyc, shot = D.cycle, D.screenshot

    def cycle(self, with_joystick=True):
        d = self.__dict__
        h = d.get('_rr_hint', 0)
        if h > 0:
            d['_rr_hint'] = h - 1
            if not self.memory.unsigned.read_long(0x04000064) >> 31:
                self.lib.desmume_skip_next_frame()
                d['_rr_clean'] = 0
                return cyc(self, with_joystick)
        cyc(self, with_joystick)
        d['_rr_clean'] = d.get('_rr_clean', RENDER_TAIL) + 1

    def screenshot(self):
        if self.__dict__.get('_rr_clean', RENDER_TAIL) < RENDER_TAIL:
            print('RR-RENDER-STALE: screenshot', RENDER_TAIL - self.__dict__['_rr_clean'], 'frame(s) after a skipped one',
                  file=sys.stderr, flush=True)
        return shot(self)

    D.cycle, D.screenshot, D._rr_patched = cycle, screenshot, True


try:                                            # only in the emulator venv
    import desmume  # noqa: F401
    tune_desmume()
    if RR_SKIP_RENDER:
        _install_render_skip()
except ImportError:
    pass
