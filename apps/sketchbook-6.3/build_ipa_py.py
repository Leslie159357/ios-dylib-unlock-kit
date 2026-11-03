#!/usr/bin/env python3
"""build_ipa_py.py — 无 unzip/zip 依赖的 IPA 注入打包（zipfile 实现）"""
import os, sys, shutil, zipfile, plistlib, subprocess, tempfile

src_ipa, hook, out = sys.argv[1], sys.argv[2], sys.argv[3]
work = tempfile.mkdtemp(prefix="ipabuild_", dir="/opt/data/cache/scratch")
x = os.path.join(work, "x")
os.makedirs(x, exist_ok=True)
with zipfile.ZipFile(src_ipa) as z:
    z.extractall(x)
app = [os.path.join(x, "Payload", d) for d in os.listdir(os.path.join(x, "Payload")) if d.endswith(".app")][0]
info = plistlib.load(open(os.path.join(app, "Info.plist"), "rb"))
binname = info["CFBundleExecutable"]
frameworks = os.path.join(app, "Frameworks")
os.makedirs(frameworks, exist_ok=True)
shutil.copy(hook, os.path.join(frameworks, os.path.basename(hook)))

inj = "/opt/data/ipa_unlocker_inspect/ipa-unlocker/scripts/inject_weak.py"
r = subprocess.run([sys.executable, inj, os.path.join(app, binname),
                    "@executable_path/Frameworks/" + os.path.basename(hook)],
                   capture_output=True, text=True)
print("inject:", r.stdout.strip(), r.stderr.strip()[:300], "rc=", r.returncode)

if os.path.exists(out):
    os.remove(out)
n = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, dirs, files in os.walk(x):
        for f in files:
            p = os.path.join(root, f)
            z.write(p, os.path.relpath(p, x))
            n += 1
print(f"[OK] {out} files={n} size={os.path.getsize(out)}")
shutil.rmtree(work, ignore_errors=True)
