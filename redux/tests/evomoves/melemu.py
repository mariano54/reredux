"""melemu.py : the py-desmume DeSmuME API the statview / evomoves test drivers use (cycle, input, screenshot, memory),
backed by the headless melonDS of bfix/lib/libbf.dylib (interpreter, MPU and data aborts emulated like hardware).

EMU=melon in the environment makes em.py install it: every EM test then runs in melonDS. The battery save the driver
copied to <battery dir>/<rom name>.dsv is loaded as a raw .sav (the DeSmuME footer cut off). One emulator per
process (libbf is global). A data abort is noted (abort count in `aborts()`, from melonDS' log on stdout)."""
import os as _rr_os, sys as _rr_sys; _rr_sys.path.insert(0, _rr_os.path.normpath(_rr_os.path.join(_rr_os.path.dirname(_rr_os.path.abspath(__file__)), '..')))  # noqa: E702
from rrenv import RR_T, RR_B, RR_RX, RR_REPO, RR_PY, RR_MEL, RR_DSV  # noqa: E402,F401
import os, sys
sys.path.insert(0, f'{RR_MEL}')
from mel import Mel, L

B = f'{RR_B}'
DSV_DIR = os.path.expanduser(f'{RR_DSV}')


class _Mem:
    def __init__(self, mel):
        self.mel = mel

    def __getitem__(self, k):
        if isinstance(k, slice):
            return list(self.mel.read(k.start, k.stop - k.start))
        t = self.mel.tcm(k, 1)              # ITCM / DTCM (the follower code's data) are not on the bus
        return t[0] if t is not None else self.mel.r8(k)

    def __setitem__(self, k, v):
        import ctypes as C
        db = L.ml_dtcm_base()
        if db <= k < db + 0x4000:
            C.c_uint8.from_address(L.ml_dtcm() + (k - db)).value = v & 0xFF
        elif k < 0x02000000:
            C.c_uint8.from_address(L.ml_itcm() + (k & 0x7FFF)).value = v & 0xFF
        else:
            L.ml_write8(k, v & 0xFF)


class _Memory:
    def __init__(self, mel):
        self.unsigned = _Mem(mel)


class _Input:
    def __init__(self, emu):
        self.emu = emu

    def keypad_add_key(self, m):
        self.emu.keys |= m

    def keypad_rm_key(self, m):
        self.emu.keys &= ~m

    def touch_set_pos(self, x, y):
        self.emu.touch = (1, x, y)

    def touch_release(self):
        self.emu.touch = (0, 0, 0)


class MelonDeSmuME:
    def __init__(self):
        self.mel = None
        self.keys = 0
        self.touch = (0, 0, 0)
        self.input = _Input(self)

    def open(self, rom):
        name = os.path.splitext(os.path.basename(rom))[0]
        dsv = os.path.join(DSV_DIR, name + '.dsv')
        sav = None
        if os.path.exists(dsv):
            d = open(dsv, 'rb').read()
            cut = d.find(b'|<--Snip')
            os.makedirs(B + '/melon', exist_ok=True)
            sav = f'{B}/melon/{name}.sav'
            open(sav, 'wb').write(d[:cut] if cut > 0 else d)
        self.mel = Mel(os.path.realpath(rom), sav)
        self.memory = _Memory(self.mel)

    def volume_set(self, v):
        pass

    def cycle(self, with_joystick=False):
        t, x, y = self.touch
        L.ml_frame(self.keys, t, x, y)
        self.mel.frame += 1

    def screenshot(self):
        return self.mel.image()


def install():
    import desmume.emulator
    desmume.emulator.DeSmuME = MelonDeSmuME
