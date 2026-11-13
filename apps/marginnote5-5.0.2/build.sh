#!/bin/sh
# 编译 mn5hook.dylib（无 SDK，freestanding；在 linux 上交叉编译 arm64 iOS dylib）
# 依赖: clang (任意 target 可用) + ld64.lld。容器内执行方式见 README。
set -e
SRC=${1:-mn5hook.c}
OUT=${2:-mn5hook.dylib}
RES=$(clang -print-resource-dir)

clang --target=arm64-apple-ios15.0 -O2 -ffreestanding -nostdinc -I"$RES/include" -w \
      -c "$SRC" -o /tmp/mn5hook.o

ld64.lld -dylib -arch arm64 /tmp/mn5hook.o -o "$OUT" \
      -platform_version ios 15.0.0 15.0.0 \
      -install_name @executable_path/Frameworks/mn5hook.dylib \
      -undefined dynamic_lookup -no_fixup_chains

ls -l "$OUT"
echo "objc 方法全部按类名/selector 名解析，不依赖偏移；重建后无需改源码"
