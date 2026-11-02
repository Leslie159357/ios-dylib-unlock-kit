#!/usr/bin/env bash
# 一条龙：编译 dylib → 打序言补丁 → 注入 LC_LOAD_DYLIB → 重打包
# 用法：./scripts/build.sh <原始解密IPA> <工作目录> <输出IPA>
set -euo pipefail

IPA="${1:?原始解密 IPA 路径}"
WORK="${2:?工作目录}"
OUT="${3:?输出 IPA 路径}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$WORK"
cd "$WORK"

echo "[1/4] 解包"
rm -rf Payload
python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall('.')" "$IPA"

APP="$(ls -d Payload/*.app)"
KIT="$APP/Frameworks/ScriptingKit.framework/ScriptingKit"

echo "[2/4] 序言补丁（ScriptingKit）"
python3 "$ROOT/scripts/patch_scriptingkit.py" "$KIT" "$WORK/ScriptingKit.patched"
cp "$WORK/ScriptingKit.patched" "$KIT"

echo "[3/4] 注入 dylib 加载命令"
cp "$APP/Scripting" "$WORK/Scripting.injected"
python3 "$ROOT/scripts/inject_lc.py" \
    "$WORK/Scripting.injected" \
    @executable_path/Frameworks/ScriptingGroupFix.dylib \
    "$WORK/Scripting.injected"
cp "$WORK/Scripting.injected" "$APP/Scripting"
cp "$ROOT/lib/ScriptingGroupFix.dylib" "$APP/Frameworks/ScriptingGroupFix.dylib"

echo "[4/4] 重打包"
python3 - <<PY
import json
json.dump({
 "$APP/Scripting": "$WORK/Scripting.injected",
 "$APP/Frameworks/ScriptingKit.framework/ScriptingKit": "$WORK/ScriptingKit.patched",
 "$APP/Frameworks/ScriptingGroupFix.dylib": "$ROOT/lib/ScriptingGroupFix.dylib",
}, open("$WORK/manifest.json","w"), indent=1)
PY
python3 "$ROOT/scripts/repack_multi.py" "$IPA" "$OUT" "$WORK/manifest.json"
echo "done: $OUT"
