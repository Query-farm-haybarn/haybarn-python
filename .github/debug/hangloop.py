"""Runs TestAfterASubinterpreter's child N times; on a hang saves faulthandler + `sample` stacks.
usage: python hangloop.py <tests-dir> <N> <outdir>"""
import importlib.util, os, subprocess, sys, textwrap, time, collections

tests, n, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
os.makedirs(out, exist_ok=True)
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
h = load("subinterpreter_gil", os.path.join(tests, "fast", "test_subinterpreter_gil.py"))
src = open(os.path.join(tests, "fast", "arrow", "scan", "test_arrow_scan_rules.py")).read()
start = src.index('GENERATOR_INPUT = """') + len('GENERATOR_INPUT = """')
body = src[start:src.index('"""', start)]
script = "".join(textwrap.dedent(p) for p in (
    h.NO_CORE_DUMP, "import sys\nimport faulthandler\nfaulthandler.dump_traceback_later(40, exit=False)\n",
    h.SUBINTERPRETER, "import haybarn\n", "", h.SPINNER, body, h.SPINNER_DONE, f"print({h.BODY_DONE!r})\n"))
res = collections.Counter()
for i in range(n):
    t0 = time.time()
    child = subprocess.Popen([sys.executable, "-u", "-c", script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        so, se = child.communicate(timeout=60)
        ok = child.returncode == 0 and so.splitlines()[-1:] == [h.BODY_DONE]
        res["ok" if ok else f"rc={child.returncode}"] += 1
        if not ok:
            open(f"{out}/bad-{i}.txt", "w").write(f"rc={child.returncode}\n{so}\n=== stderr\n{se}")
    except subprocess.TimeoutExpired:
        smp = subprocess.run(["sample", str(child.pid), "3"], capture_output=True, text=True).stdout
        child.kill(); so, se = child.communicate()
        where = "after-BODY_DONE" if h.BODY_DONE in so else ("in-scan" if "STARTED" in so else "before")
        res[f"hang-{where}"] += 1
        open(f"{out}/hang-{i}.txt", "w").write(f"{where}\nstdout:\n{so}\n=== stderr (faulthandler)\n{se}\n=== sample\n{smp}")
    print(i, f"{time.time()-t0:.1f}s", dict(res), flush=True)
print("RESULT", sys.version.split()[0], dict(res))
