"""Exact copy map of the Redux xdelta, parsed from `xdelta3 printdelta` (build/rom/delta.txt).

Every target byte is either written by Redux (ADD/RUN) or copied: from the vanilla ROM (S@, relative
to the window's copy-window offset) or from earlier target bytes (T@, relative to the target window).
`source(t)` resolves a target offset to the vanilla ROM offset it ultimately came from, or None if
Redux wrote it.
"""
import array, bisect, os, re, subprocess

WIN = 1 << 23   # xdelta3 target window size used for this patch (8 MiB)
INSN = re.compile(r'(CPY_\d+|ADD|RUN)\s+(\d+)(?:\s+([ST])@(\d+))?')


class CopyMap:
    def __init__(self, delta_txt=None, patch=None):
        if delta_txt is None:
            from redux_rom import BUILD
            delta_txt = os.path.join(BUILD, 'rom', 'delta.txt')
            patch = patch or os.path.join(BUILD, 'patch', 'complete.xdelta')
            if not os.path.exists(delta_txt):
                with open(delta_txt, 'w') as f:
                    subprocess.run(['xdelta3', 'printdelta', patch], stdout=f, check=True)
        self.start = array.array('Q')   # absolute target start of each run
        self.length = array.array('I')
        self.kind = array.array('b')    # 0 literal, 1 source, 2 target
        self.src = array.array('Q')     # absolute source/target offset of the run's first byte
        win = cwo = 0
        for line in open(delta_txt):
            if line.startswith('VCDIFF window number:'):
                win = int(line.split()[-1])
                cwo = 0
                continue
            if line.startswith('VCDIFF copy window offset:'):
                cwo = int(line.split()[-1])
                continue
            m = re.match(r'\s+(\d{6,})\s+\d{3}\s+(.*)', line)
            if not m:
                continue
            t = win * WIN + int(m.group(1))
            for typ, size, st, addr in INSN.findall(m.group(2)):
                size = int(size)
                if typ.startswith('CPY'):
                    k, s = (1, cwo + int(addr)) if st == 'S' else (2, win * WIN + int(addr))
                else:
                    k, s = 0, 0
                self.start.append(t); self.length.append(size); self.kind.append(k); self.src.append(s)
                t += size

    def source(self, t, depth=0):
        i = bisect.bisect_right(self.start, t) - 1
        if i < 0 or t >= self.start[i] + self.length[i] or depth > 64:
            return None
        k = self.kind[i]
        if k == 0:
            return None
        s = self.src[i] + (t - self.start[i])
        return s if k == 1 else self.source(s, depth + 1)
