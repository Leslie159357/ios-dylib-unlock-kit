#!/bin/bash
# 官方 2.1.0.11 arm64 单包：重编译 → 对齐 → 签名（容器内执行）
set -e
cd /opt/data/cache/scratch/yamby
APKTOOL="java -jar /opt/data/docker/rea-agent/apktool_3.0.3.jar"
KS=/opt/data/cache/scratch/yamby/yamby.keystore
OUT=Yamby_2.1.0.11_arm64_official_unlocked.apk

echo "=== 0) 资源修正（targetSdk34 私有色引用）==="
if [ -f off_smali/res/values-v34/colors.xml ]; then
  python3 fix_v34_colors.py off_smali/res/values-v34/colors.xml || echo "  (色修正跳过)"
fi

echo "=== 1) 重编译（含 12 处补丁）==="
rm -f ${OUT%.apk}_raw.apk ${OUT%.apk}_aligned.apk "$OUT"
$APKTOOL b off_smali -o ${OUT%.apk}_raw.apk
ls -la ${OUT%.apk}_raw.apk

echo "=== 2) 对齐 + 签名 ==="
zipalign -f -p 4 ${OUT%.apk}_raw.apk ${OUT%.apk}_aligned.apk
apksigner sign --ks $KS --ks-pass pass:yamby123 --key-pass pass:yamby123 \
  --v1-signing-enabled true --v2-signing-enabled true --v3-signing-enabled true \
  --out "$OUT" ${OUT%.apk}_aligned.apk

echo "=== 3) 校验 ==="
apksigner verify --print-certs "$OUT" | head -4
unzip -l "$OUT" 2>/dev/null | grep -E "classes.*dex|lib/arm64-v8a/libnmmp|libnmmvm" | head -6
sha256sum "$OUT"
ls -la "$OUT"
echo BUILD_OK
