#!/usr/bin/env python3
"""rr.py : the ReRedux regression runner (job graph from suite.py, many emulators in parallel).

  python3 redux/tests/rr.py --quick            # ~3 min: boot + new game, settings menu, views, rules new game, statview / evomoves
  python3 redux/tests/rr.py --full             # everything (both languages, both emulators, perf measurements)
  python3 redux/tests/rr.py --changed [REF]    # the jobs whose areas the files changed since REF (default HEAD) touch
  python3 redux/tests/rr.py --only 'qa\\.(ng\\.rel_def|story|smoke|continue)\\.' --lang en   # e.g. the old quick_m3 chain
  python3 redux/tests/rr.py --perf [--baseline NAME]   # ~10-20 s: field performance benchmark (perf/perf.py; README)
Options: --lang en,jp  -j N (parallel emulators; default: cores - 2)  --build (rebuild the release ROMs first)
  --determinism (rebuild once more at the end, SHA-1s must match)  --fail-fast  --list  --keep N (old runs kept)

Every run gets build/testruns/<id>/ (also build/testruns/latest): b/ = a shadow of redux/build (test output
directories are real, everything else is a symlink to redux/build, so a run never sees an earlier run's savestates),
logs/<job>.log, cfg/<job>/desmume (that job's DeSmuME battery saves: XDG_CONFIG_HOME; ~/.config/desmume is never
touched), summary.txt, results.json. Jobs are started longest-chain-first using the durations of earlier runs
(build/testruns/durations.json); a failed job's dependents are skipped. Exit status 0 = all passed."""
import argparse, glob, json, os, re, shutil, subprocess, sys, time

T = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, T)
import rrenv  # noqa: E402
import suite  # noqa: E402

RX, REPO, B = rrenv.RR_RX, rrenv.RR_REPO, rrenv.RR_REAL_B
RUNS = os.path.join(B, 'testruns')
OUTDIRS = ('qa', 'qa2', 'qol2', 'rules', 'statview_integ', 'fastsave_integ', 'battleexit', 'ff_integ', 'melon', 'shadow',
           'evomoves', 'integ_logs')
FIXTURES = ('statview_integ/dsv', 'ff_integ/sav')
NOISE = re.compile(r'^(ROM |DeSmuME|SoftRasterizer|Microphone|Slot[12]|BackupDevice|Already decrypted|WIFI:|ARM[79] BIOS|'
                   r'Firmware|Autodetecting|\[melon\]|$)')


def shadow(run_b, langs):
    os.makedirs(run_b)
    for e in sorted(os.listdir(B)):
        if e in ('testruns',) or e.startswith('.'):
            continue
        if e in OUTDIRS:
            continue
        os.symlink(os.path.join(B, e), os.path.join(run_b, e))
    for d in OUTDIRS:
        os.makedirs(os.path.join(run_b, d), exist_ok=True)
    for f in FIXTURES:
        if os.path.exists(os.path.join(B, f)):
            os.symlink(os.path.join(B, f), os.path.join(run_b, f))
    os.makedirs(os.path.join(run_b, 'qol2', 'states'), exist_ok=True)
    for L in langs:                         # qol2 kind qa = the QA test ROM (built into this run's b/qa/roms)
        for ext in ('nds', 'elf'):
            os.symlink(f'../qa/roms/qa_test_{L}.{ext}', os.path.join(run_b, 'qol2', f'qa_{L}.{ext}'))
        q = os.path.join(B, 'qol', f'qa_{L}')
        if not os.path.lexists(q):
            os.symlink(f'qa_test_{L}', q)


def fs_snap(run_b, langs):
    """fastsave_integ/rr: the release ROMs + qol maps + follower ELFs the fast-save tests run on (links)"""
    s = os.path.join(run_b, 'fastsave_integ', 'rr')
    os.makedirs(s, exist_ok=True)
    for L in langs:
        os.makedirs(f'{s}/qol_{L}', exist_ok=True)
        for src, dst in ((f'{B}/out/redux3_{L}.nds', f'{s}/redux3_{L}.nds'), (f'{B}/qol/{L}/qol_map.json', f'{s}/qol_{L}/qol_map.json'),
                         (f'{B}/redux3/{L}_follow.elf', f'{s}/follow_{L}.elf')):
            if not os.path.lexists(dst):
                os.symlink(src, dst)


def changed_files(ref):
    out = set()
    for args in (['diff', '--name-only', ref], ['diff', '--name-only', '--cached'], ['ls-files', '--others', '--exclude-standard']):
        r = subprocess.run(['git'] + args, cwd=REPO, capture_output=True, text=True)
        out |= {l.strip() for l in r.stdout.splitlines() if l.strip()}
    return sorted(out)


def select(jobs, a):
    by = {j.id: j for j in jobs}
    if a.only:
        rx = re.compile(a.only)
        want = {j.id for j in jobs if rx.search(j.id)}
    elif a.changed is not None:
        files = changed_files(a.changed)
        areas = suite.areas_for(files)
        print(f'changed since {a.changed}: {len(files)} files -> areas {sorted(areas) or "none"}')
        want = {j.id for j in jobs if 'all' in areas or (j.areas & areas and j.result != 'internal')}
        want = {i for i in want if by[i].tiers & {'full', 'quick'}}
    else:
        tier = 'quick' if a.quick else 'full'
        want = {j.id for j in jobs if tier in j.tiers}
    if a.skip:
        rx = re.compile(a.skip)
        want = {i for i in want if not rx.search(i)}
    todo = list(want)
    while todo:                              # + everything they start from
        for d in by[todo.pop()].deps:
            if d not in want:
                want.add(d)
                todo.append(d)
    return [j for j in jobs if j.id in want]


def subst(s, ctx):
    s = s.replace('{B}', ctx['b']).replace('{RX}', RX)
    return re.sub(r'\{CFG:([^}]+)\}', lambda m: os.path.join(ctx['cfg'], m.group(1), 'desmume'), s)


class Cache:
    """ROM-keyed checkpoint / result cache: build/testcache/jobs/<key>/{meta.json, b/..., cfg/...}. Files are hard links
    of the run's outputs (no copy; an APFS volume shares the blocks)."""
    def __init__(self):
        self.root = os.path.join(B, 'testcache')
        self.hfile = os.path.join(self.root, 'filehash.json')
        try:
            self.fh = json.load(open(self.hfile))
        except (OSError, ValueError):
            self.fh = {}
        self.harness = {}

    def file_sha(self, p):
        import hashlib
        p = os.path.realpath(p)
        st = os.stat(p)
        k = f'{p}|{st.st_size}|{st.st_mtime_ns}'
        if k not in self.fh:
            h = hashlib.sha1()
            with open(p, 'rb') as f:
                for blk in iter(lambda: f.read(1 << 24), b''):
                    h.update(blk)
            self.fh[k] = h.hexdigest()
        return self.fh[k]

    def harness_sha(self, grp):
        import hashlib
        if grp not in self.harness:
            h = hashlib.sha1()
            files = [os.path.join(T, f) for f in sorted(os.listdir(T)) if f.endswith('.py') and f not in ('rr.py', 'suite.py')]
            for d in suite.LIBS.get(grp, (grp,) if grp else ()):
                dd = os.path.join(T, d)
                files += [os.path.join(dd, f) for f in sorted(os.listdir(dd)) if f.endswith('.py')] if os.path.isdir(dd) else []
            for f in files:
                h.update(f.encode() + open(f, 'rb').read())
            self.harness[grp] = h.hexdigest()
        return self.harness[grp]

    def save_index(self):
        try:
            os.makedirs(self.root, exist_ok=True)
            json.dump(self.fh, open(self.hfile + '.tmp', 'w'))
            os.replace(self.hfile + '.tmp', self.hfile)
        except OSError:
            pass

    def meta(self, key):
        try:
            return json.load(open(os.path.join(self.root, 'jobs', key, 'meta.json')))
        except (OSError, ValueError):
            return None

    def store(self, key, meta, files):
        """files: [(abs path in the run, relative name in the entry)]"""
        d = os.path.join(self.root, 'jobs', key)
        tmp = d + '.tmp'
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        for src, rel in files:
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
        json.dump(meta, open(os.path.join(tmp, 'meta.json'), 'w'), indent=1)
        shutil.rmtree(d, ignore_errors=True)
        os.replace(tmp, d)

    def restore(self, key, b, cfg):
        d = os.path.join(self.root, 'jobs', key)
        n = 0
        for root, _, fs in os.walk(d):
            for f in fs:
                rel = os.path.relpath(os.path.join(root, f), d)
                if rel == 'meta.json':
                    continue
                top, rest = rel.split(os.sep, 1)
                dst = os.path.join(b if top == 'b' else cfg, rest)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(root, f), dst)     # a copy: later jobs may write the run's files
                n += 1
        return n

    def prune(self, keep=3):
        """keep the newest `keep` entries per job id"""
        jd = os.path.join(self.root, 'jobs')
        if not os.path.isdir(jd):
            return
        by = {}
        for k in os.listdir(jd):
            m = self.meta(k)
            if m:
                by.setdefault(m['job'], []).append((m.get('time', 0), k))
        for v in by.values():
            for _, k in sorted(v)[:-keep]:
                shutil.rmtree(os.path.join(jd, k), ignore_errors=True)


class Runner:
    def __init__(self, jobs, a, run_dir):
        self.jobs = {j.id: j for j in jobs}
        self.a, self.dir = a, run_dir
        self.b = os.path.join(run_dir, 'b')
        self.ctx = dict(b=self.b, cfg=os.path.join(run_dir, 'cfg'))
        self.logs = os.path.join(run_dir, 'logs')
        os.makedirs(self.logs, exist_ok=True)
        self.state = {i: 'wait' for i in self.jobs}
        self.res = {}
        self.dur_file = os.path.join(RUNS, 'durations.json')
        try:
            self.hist = json.load(open(self.dur_file))
        except (OSError, ValueError):
            self.hist = {}
        self.prio = {}
        for i in self.jobs:
            self._prio(i)
        self.cache = Cache()
        self.keys = {}

    def key(self, j):
        """cache key (None: never cached): command, ROM SHA-1, inputs, harness files, dependencies' keys"""
        import hashlib
        if j.id.startswith('build.'):
            return None
        parts = [j.id, j.cmds, sorted(j.env.items()), j.result, [list(map(str, p)) for p in j.pre],
                 self.cache.harness_sha(j.grp), bool(self.a.skip_render)]
        try:
            if j.rom:
                parts.append(self.cache.file_sha(subst(suite.ROMS[j.rom].replace('{L}', j.lang), self.ctx)))
            for p in j.inputs:
                parts.append(self.cache.file_sha(subst(p, self.ctx)))
            for d in j.deps:
                dj = self.jobs[d]
                if d.startswith('build.'):         # a test ROM: its SHA-1 (via the dependent's rom) is the key
                    continue
                if self.keys.get(d) is None:
                    return None
                parts.append(self.keys[d])
        except OSError:
            return None
        return hashlib.sha1(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()

    def outputs(self, j):
        cfg = os.path.join(self.ctx['cfg'], j.id, 'desmume')
        out = []
        for p in j.outputs:
            p = subst(p.replace('{CFG}', cfg), self.ctx)
            for f in sorted(glob.glob(p)):
                base, top = (self.b, 'b') if f.startswith(self.b + os.sep) else (cfg, 'cfg')
                out.append((f, os.path.join(top, os.path.relpath(f, base))))
        return out

    def try_cached(self, j):
        k = self.keys[j.id] = self.key(j)
        if not (k and self.a.reuse):
            return False
        m = self.cache.meta(k)
        if not m or m.get('status') != 'PASS':
            return False
        self.pre(j)
        n = self.cache.restore(k, self.b, os.path.join(self.ctx['cfg'], j.id, 'desmume'))
        self.state[j.id] = 'ok'
        self.res[j.id] = dict(status='CACHED', why=f"{m.get('why', '')} (run {m.get('run')}, {n} files restored)"[:160],
                              secs=0, ran_secs=m.get('secs'))
        return True

    def remember(self, j, why, secs):
        k = self.keys.get(j.id)
        if not k or j.result == 'internal':
            return
        try:
            self.cache.store(k, dict(job=j.id, status='PASS', why=why, secs=round(secs, 1), run=os.path.basename(self.dir),
                                     time=time.time()), self.outputs(j))
        except OSError as e:
            print('cache store failed for', j.id, e, flush=True)

    def est(self, i):
        return self.hist.get(i, self.jobs[i].est)

    def _prio(self, i):
        """estimated time from this job's start to the end of its longest chain of dependents"""
        if i not in self.prio:
            kids = [k for k, j in self.jobs.items() if i in j.deps]
            self.prio[i] = self.est(i) + max((self._prio(k) for k in kids), default=0)
        return self.prio[i]

    def pre(self, j):
        cfg = os.path.join(self.ctx['cfg'], j.id, 'desmume')
        os.makedirs(cfg, exist_ok=True)
        for p in j.pre:
            if p[0] == 'copy':
                src, dst = subst(p[1], self.ctx), subst(p[2], self.ctx)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy(src, dst)
            elif p[0] == 'dsv':
                shutil.copy(os.path.join(self.ctx['cfg'], p[1], 'desmume', p[2]), os.path.join(cfg, p[2]))
            elif p[0] == 'fs_snap':
                fs_snap(self.b, p[1])

    def env(self, j):
        e = dict(os.environ)
        e.update(RR_B=self.b, XDG_CONFIG_HOME=os.path.join(self.ctx['cfg'], j.id), PYTHONUNBUFFERED='1',
                 SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', PYTHONDONTWRITEBYTECODE='1')
        if self.a.threads:
            e['RR_DESMUME_THREADS'] = str(self.a.threads)
        if self.a.skip_render:
            e['RR_SKIP_RENDER'] = '1'
        for k, v in j.env.items():
            e[k] = subst(v, self.ctx)
        # jobs far from the critical path yield the CPU to it (the run's wall time is its longest chain)
        if self.a.nice and self.prio[j.id] < 0.5 * max(self.prio.values()):
            e['RR_NICE'] = '10'
        return e

    def start(self, j):
        """a job = its command list run in sequence in a small shell-free wrapper process"""
        log = os.path.join(self.logs, j.id + '.log')
        cwd = os.path.join(RX, 'tools') if j.grp == 'tools' else os.path.join(T, j.grp)
        cmds = []
        for c in j.cmds:
            argv = []
            for x in c:
                x = subst(x, self.ctx)
                argv += sorted(glob.glob(x)) if '*' in x else [x]
            cmds.append([rrenv.RR_PY, '-u'] + argv)
        f = open(log, 'w')
        f.write(f'# {j.id}  cwd {cwd}\n' + ''.join('# ' + ' '.join(c) + '\n' for c in cmds))
        f.flush()
        wrapper = [sys.executable, os.path.abspath(__file__), '--exec', json.dumps(cmds)]
        p = subprocess.Popen(wrapper, cwd=cwd, env=self.env(j), stdout=f, stderr=subprocess.STDOUT)
        return p, f, log

    def verdict(self, j, rc, log):
        txt = open(log, errors='replace').read().splitlines()
        res = [l for l in txt if l.startswith('RESULT')]
        bad = [l for l in txt if l.startswith('FAIL') or 'Traceback' in l or re.search(r'\w+Error\b', l)
               or 'data abort' in l or 'prefetch abort' in l]
        aborts = [l for l in txt if 'data abort' in l or 'prefetch abort' in l]
        if j.result == 'RESULT':
            ok = bool(res) and all('PASS' in l and 'FAIL' not in l for l in res) and not aborts
            why = res[-1] if res else f'no RESULT (rc {rc})'
            if ok and rc:
                why += f' (rc {rc})'
        elif j.result == 'expect_fail':        # a negative control: the check must catch the planted problem
            ok = bool(res) and any('FAIL' in l for l in res)
            why = ('expected FAIL seen: ' if ok else 'expected a FAIL, got: ') + (res[-1] if res else f'rc {rc}')
        elif j.result == 'meas':
            ok = rc == 0 and not any('Traceback' in l for l in txt)
            meas = [l for l in txt if l.startswith('MEAS') or ' frames' in l]
            why = (meas[-1] if meas else 'done') if ok else f'rc {rc}'
        else:
            ok = rc == 0 and not any('Traceback' in l for l in txt)
            why = 'ok' if ok else f'rc {rc}'
        if aborts:
            why += f' [{len(aborts)} abort lines]'
        stale = [l for l in txt if l.startswith('RR-RENDER-STALE')]
        if stale:                              # a picture was looked at that the render skip didn't draw: a harness bug
            ok = False
            why = f'{len(stale)} stale screenshot(s) (render skip; rerun with --render-all) / ' + why
            bad = stale[:2] + bad
        return ok, why[:160], bad[:6]

    def run(self):
        N = self.a.jobs
        running = {}
        t0 = time.time()
        failed_any = False
        total = len(self.jobs)
        while True:
            for i, j in self.jobs.items():          # skip dependents of failures
                if self.state[i] == 'wait' and any(self.state[d] in ('fail', 'skip') for d in j.deps):
                    self.state[i] = 'skip'
                    self.res[i] = dict(status='SKIP', why='dependency failed: ' + ', '.join(
                        d for d in j.deps if self.state[d] in ('fail', 'skip')), secs=0)
            ready = [i for i, j in self.jobs.items() if self.state[i] == 'wait' and all(self.state[d] == 'ok' for d in j.deps)]
            ready.sort(key=lambda i: -self.prio[i])
            stop = failed_any and self.a.fail_fast
            for i in ready:
                j = self.jobs[i]
                if j.result == 'internal':
                    try:
                        self.keys[i] = self.key(j)
                        self.pre(j)
                        self.state[i] = 'ok'
                        self.res[i] = dict(status='PASS', why='ok', secs=0)
                    except Exception as e:
                        self.state[i] = 'fail'
                        self.res[i] = dict(status='FAIL', why=f'{type(e).__name__}: {e}', secs=0)
                    continue
                try:
                    if self.try_cached(j):
                        print(f'[{time.time() - t0:6.0f}s] cached {i:34s} {self.res[i]["why"][:90]}', flush=True)
                        continue
                except Exception as e:
                    print('cache restore failed for', i, e, flush=True)
                if stop or len(running) >= N:
                    break
                try:
                    self.pre(j)
                except Exception as e:
                    self.state[i] = 'fail'
                    self.res[i] = dict(status='FAIL', why=f'setup: {type(e).__name__}: {e}', secs=0)
                    continue
                running[i] = self.start(j) + (time.time(),)
                self.state[i] = 'run'
            if not running and (stop or not ready):
                if not any(s == 'wait' for s in self.state.values()) or stop or not ready:
                    break
            time.sleep(0.25)
            for i in list(running):
                p, f, log, ts = running[i]
                j = self.jobs[i]
                limit = j.timeout or max(1800, 6 * self.est(i))
                if p.poll() is None and time.time() - ts > limit:
                    p.kill()
                    p.wait()
                    f.write(f'\nRR: killed after {limit:.0f} s (timeout)\n')
                if p.poll() is None:
                    continue
                f.close()
                dt = time.time() - ts
                ok, why, bad = self.verdict(j, p.returncode, log)
                self.state[i] = 'ok' if ok else 'fail'
                self.res[i] = dict(status='PASS' if ok else 'FAIL', why=why, secs=round(dt, 1), bad=bad,
                                   log=os.path.relpath(log, self.dir))
                if ok:
                    self.hist[i] = round(dt, 1)
                    self.remember(j, why, dt)
                del running[i]
                done = sum(1 for s in self.state.values() if s in ('ok', 'fail', 'skip'))
                print(f'[{time.time() - t0:6.0f}s {done:3d}/{total}] {"ok  " if ok else "FAIL"} {i:34s} {dt:6.1f}s  {why[:90]}',
                      flush=True)
                if not ok:
                    failed_any = True
                    for l in bad:
                        print('        ', l[:200], flush=True)
                    print('         log:', log, flush=True)
            if stop and not running:
                break
        for i in self.jobs:
            if i not in self.res:
                self.res[i] = dict(status='SKIP', why='not started (fail-fast)' if self.a.fail_fast else 'not started', secs=0)
        self.wall = time.time() - t0
        try:
            json.dump(self.hist, open(self.dur_file, 'w'), indent=1, sort_keys=True)
        except OSError:
            pass
        self.cache.save_index()
        self.cache.prune()


def summary(r, run_dir, a):
    lines = []
    st = {}
    for i, v in r.res.items():
        st.setdefault(v['status'], []).append(i)
    cpu = sum(v['secs'] for v in r.res.values())
    head = (f"ReRedux regression {os.path.basename(run_dir)}: {len(st.get('PASS', []))} passed, "
            f"{len(st.get('CACHED', []))} cached (same ROMs + harness: earlier PASS reused), {len(st.get('FAIL', []))} failed, "
            f"{len(st.get('SKIP', []))} skipped; wall {r.wall / 60:.1f} min, job time {cpu / 60:.1f} min, -j {a.jobs}")
    lines.append(head)
    lines.append('')
    lines.append(f"{'job':36s} {'status':6s} {'secs':>7s}  detail")
    order = sorted(r.res, key=lambda i: ({'FAIL': 0, 'SKIP': 1, 'PASS': 2, 'CACHED': 3}[r.res[i]['status']], i))
    for i in order:
        v = r.res[i]
        lines.append(f"{i:36s} {v['status']:6s} {v['secs']:7.1f}  {v['why']}")
    txt = '\n'.join(lines) + '\n'
    open(os.path.join(run_dir, 'summary.txt'), 'w').write(txt)
    json.dump(dict(run=os.path.basename(run_dir), wall=r.wall, jobs=a.jobs, results=r.res),
              open(os.path.join(run_dir, 'results.json'), 'w'), indent=1)
    print('\n' + txt)
    print('logs:', os.path.join(run_dir, 'logs'))
    return not st.get('FAIL') and not st.get('SKIP')


def exec_cmds(cmds):
    """--exec: run the commands in order (stop at the first failing one), filtering emulator start-up noise"""
    rc = 0
    if os.environ.get('RR_NICE'):
        try:
            os.nice(int(os.environ['RR_NICE']))
        except OSError:
            pass
    for c in cmds:
        p = subprocess.Popen(c, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
        for l in p.stdout:
            if not NOISE.match(l):
                sys.stdout.write(l)
                sys.stdout.flush()
        rc = p.wait()
        if rc:
            break
    sys.exit(rc)


def build_release(run_dir, determinism=False):
    """tools/build_redux3.py --lang both (one at a time: build/followers is shared); returns the output SHA-1s"""
    log = os.path.join(run_dir, 'logs', 'build.release' + ('.2' if determinism else '') + '.log')
    os.makedirs(os.path.dirname(log), exist_ok=True)
    t = time.time()
    with open(log, 'w') as f:
        rc = subprocess.run([rrenv.RR_PY, '-u', 'build_redux3.py', '--lang', 'both'], cwd=os.path.join(RX, 'tools'),
                            stdout=f, stderr=subprocess.STDOUT).returncode
    print(f'build_redux3.py --lang both: rc {rc}, {time.time() - t:.0f} s  (log {log})', flush=True)
    return rc, release_shas()


def release_shas():
    import hashlib
    shas = {}
    for p in ('out/redux3_en.nds', 'out/redux3_jp.nds', 'redux3/en_followers.nds', 'redux3/jp_followers.nds',
              'qol/en/qol_map.json', 'qol/jp/qol_map.json'):
        h = hashlib.sha1()
        with open(os.path.join(B, p), 'rb') as f:
            for blk in iter(lambda: f.read(1 << 24), b''):
                h.update(blk)
        shas[p] = h.hexdigest()
    return shas


def main():
    if len(sys.argv) > 2 and sys.argv[1] == '--exec':
        exec_cmds(json.loads(sys.argv[2]))
    if len(sys.argv) > 1 and sys.argv[1] == '--perf':      # the field-performance benchmark (perf/perf.py; its options follow)
        perf = os.path.join(T, 'perf', 'perf.py')
        os.execv(rrenv.RR_PY, [rrenv.RR_PY, perf] + sys.argv[2:])
    ap =argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--quick', action='store_true')
    g.add_argument('--full', action='store_true')
    g.add_argument('--changed', nargs='?', const='HEAD', default=None, metavar='REF')
    g.add_argument('--only', metavar='REGEX', help='jobs whose id matches (+ their dependencies)')
    ap.add_argument('--skip', metavar='REGEX', help='leave these out')
    ap.add_argument('--lang', default='en,jp')
    ap.add_argument('-j', '--jobs', type=int, default=max(2, (os.cpu_count() or 8) - 2))
    ap.add_argument('--threads', type=int, default=0, help='SoftRasterizer threads per DeSmuME (default: one per core)')
    ap.add_argument('--build', action='store_true', help='rebuild the release ROMs first')
    ap.add_argument('--determinism', action='store_true', help='rebuild the release ROMs again at the end: SHA-1s equal')
    ap.add_argument('--fail-fast', action='store_true', help='start nothing new after the first failure')
    ap.add_argument('--list', action='store_true', help='print the selected jobs and exit')
    ap.add_argument('--keep', type=int, default=6, help='old runs kept in build/testruns (default 6)')
    ap.add_argument('--reuse', dest='reuse', action='store_true', default=None,
                    help='reuse cached PASS results / checkpoints of jobs whose key (ROM SHA-1, harness, deps) is '
                         'unchanged (default: on, except --full)')
    ap.add_argument('--no-reuse', dest='reuse', action='store_false')
    ap.add_argument('--render-all', dest='skip_render', action='store_false',
                    help="draw every frame (default: DeSmuME skips drawing frames nothing looks at; see rrenv.py)")
    ap.add_argument('--no-nice', dest='nice', action='store_false',
                    help="don't lower the priority of jobs off the critical path")
    ap.add_argument('--m3', action='store_true', help='the old quick_m3 chain: new game -> story -> smoke -> continue')
    a = ap.parse_args()
    if a.m3:
        a.only = r'^qa\.(ng\.rel_def|story|smoke|continue)\.'
    if a.reuse is None:
        a.reuse = not a.full
    langs = [l for l in a.lang.split(',') if l]
    jobs = select(suite.build(langs), a)
    if a.list:
        for j in jobs:
            print(f'{j.id:36s} deps {",".join(j.deps) or "-"}')
        print(len(jobs), 'jobs')
        return
    for L in langs:
        for p in (f'out/redux3_{L}.nds', f'redux3/{L}_followers.nds', f'redux3/{L}_follow.elf', f'qol/{L}/qol_map.json'):
            if not a.build and not os.path.exists(os.path.join(B, p)):
                sys.exit(f'missing {B}/{p}: build the release ROMs (tools/build_redux3.py) or pass --build')
    os.makedirs(RUNS, exist_ok=True)
    lock = os.path.join(RUNS, '.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        pid = open(lock).read().strip()
        try:
            os.kill(int(pid), 0)
            sys.exit(f'another rr.py run (pid {pid}) uses {RUNS}; wait for it or remove {lock}')
        except (ValueError, ProcessLookupError):
            os.remove(lock)
            return main()
    try:
        run_id = time.strftime('%Y%m%d-%H%M%S')
        run_dir = os.path.join(RUNS, run_id)
        os.makedirs(os.path.join(run_dir, 'logs'))
        latest = os.path.join(RUNS, 'latest')
        if os.path.lexists(latest):
            os.remove(latest)
        os.symlink(run_id, latest)
        t0 = time.time()
        shas = None
        if a.build:
            rc, shas = build_release(run_dir)
            if rc:
                sys.exit('release build failed')
        shadow(os.path.join(run_dir, 'b'), langs)
        print(f'run {run_dir}: {len(jobs)} jobs, -j {a.jobs}, langs {",".join(langs)}', flush=True)
        r = Runner(jobs, a, run_dir)
        r.run()
        ok = summary(r, run_dir, a)
        if a.determinism:
            shas = shas or release_shas()
            rc, shas2 = build_release(run_dir, determinism=True)
            if shas and shas != shas2:
                print('NOT DETERMINISTIC:', {k: (shas[k][:10], shas2[k][:10]) for k in shas if shas[k] != shas2[k]})
                ok = False
            elif shas:
                print('DETERMINISTIC: both builds have the same SHA-1s')
        print(f'total wall {(time.time() - t0) / 60:.1f} min')
        runs = sorted(d for d in os.listdir(RUNS) if re.match(r'\d{8}-\d{6}$', d))
        for old in runs[:-a.keep]:
            shutil.rmtree(os.path.join(RUNS, old), ignore_errors=True)
        sys.exit(0 if ok else 1)
    finally:
        try:
            os.remove(lock)
        except OSError:
            pass


if __name__ == '__main__':
    main()
