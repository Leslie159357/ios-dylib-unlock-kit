#!/usr/bin/env python3
"""
inject_dylib.py — 给 Mach-O 注入 LC_LOAD_WEAK_DYLIB（免越狱 IPA 用）

用法:
  python3 inject_dylib.py <macho文件> <dylib安装路径> [--dry-run]

示例:
  python3 inject_dylib.py Payload/App.app/App @executable_path/Frameworks/IGMenuVIPCrack.dylib

特点:
  * 只做「弱加载」注入（LC_LOAD_WEAK_DYLIB），dylib 缺失时 App 不会崩
  * 自动找 header padding，不破坏已有段
  * 支持 arm64 / arm64e 单架构；fat 包会先报错要求 thin
  * 幂等：已注入过同一路径则跳过
"""
import struct, sys, os

LC_LOAD_DYLIB       = 0x0C
LC_LOAD_WEAK_DYLIB  = 0x80000018
MH_MAGIC_64         = 0xfeedfacf
MH_MAGIC_32         = 0xfeedface
FAT_MAGIC           = 0xcafebabe
FAT_CIGAM           = 0xbebafeca


def align(v, a):
    return (v + a - 1) // a * a


def is_fat(data):
    m = struct.unpack(">I", data[:4])[0]
    return m in (FAT_MAGIC,)


def thin_inject(path, dylib_path, dry=False):
    data = bytearray(open(path, "rb").read())
    magic = struct.unpack("<I", data[:4])[0]
    if magic != MH_MAGIC_64:
        raise SystemExit(f"不支持的 Mach-O magic: {hex(magic)}（只处理 64 位）")

    (cputype, cpusub, filetype, ncmds, sizeofcmds, flags, _res) = struct.unpack("<iiIIIII", data[4:32])

    # 遍历 load commands
    off = 32
    existing = []
    first_section_off = None
    end_of_cmds = 32 + sizeofcmds
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack("<II", data[off:off + 8])
        if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB):
            nameoff = struct.unpack("<I", data[off + 8:off + 12])[0]
            nm = bytes(data[off + nameoff:off + cmdsize]).split(b"\x00")[0].decode("utf-8", "ignore")
            existing.append(nm)
        off += cmdsize

    # 找 header 之后可用的空隙：第一个 section 的 file offset，或第一个非 __PAGEZERO 段的 fileoff
    off = 32
    seg_offsets = []
    for _ in range(ncmds):
        cmd, cmdsize = struct.unpack("<II", data[off:off + 8])
        if cmd == 0x19:  # LC_SEGMENT_64
            segname = bytes(data[off + 8:off + 24]).split(b"\x00")[0].decode("utf-8", "ignore")
            vmaddr, vmsize, fileoff, filesize = struct.unpack("<QQQQ", data[off + 24:off + 56])
            nsects = struct.unpack("<I", data[off + 64:off + 68])[0]
            if segname != "__PAGEZERO" and filesize > 0:
                seg_offsets.append((segname, fileoff))
            # 段内 section
            s_off = off + 72
            for _s in range(nsects):
                s_fileoff = struct.unpack("<I", data[s_off + 48:s_off + 52])[0]
                if s_fileoff > 0:
                    seg_offsets.append((segname + " section", s_fileoff))
                s_off += 80
        off += cmdsize

    payload_start = min((o for n, o in seg_offsets if o >= end_of_cmds), default=None)
    if payload_start is None:
        raise SystemExit("找不到 header 空隙，无法安全扩容 load commands")

    name = dylib_path.encode("utf-8") + b"\x00"
    cmdsize = align(24 + len(name), 8)
    if end_of_cmds + cmdsize > payload_start:
        raise SystemExit(
            f"header 空间不足：需要 {cmdsize} 字节，仅剩 {payload_start - end_of_cmds} 字节")

    if dylib_path in existing:
        print(f"[=] 已存在同一 dylib 引用，跳过：{dylib_path}")
        return False

    lc = struct.pack("<IIIIII", LC_LOAD_WEAK_DYLIB, cmdsize, 24, 0x10000, 0x10000, 0x10000)
    lc += name
    lc += b"\x00" * (cmdsize - len(lc))

    if dry:
        print(f"[dry] 将注入 weak dylib：{dylib_path} ({cmdsize} bytes) 空隙 {payload_start - end_of_cmds}")
        return False

    data[end_of_cmds:end_of_cmds + cmdsize] = lc
    # 更新 header
    struct.pack_into("<I", data, 16, ncmds + 1)
    struct.pack_into("<I", data, 20, sizeofcmds + cmdsize)

    open(path, "wb").write(data)
    print(f"[+] 注入成功：{dylib_path}  ncmds {ncmds}->{ncmds+1}  "
          f"sizeofcmds {sizeofcmds}->{sizeofcmds+cmdsize}")
    return True


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    path, dylib_path = sys.argv[1], sys.argv[2]
    dry = "--dry-run" in sys.argv
    if not os.path.isfile(path):
        raise SystemExit(f"文件不存在：{path}")
    data = open(path, "rb").read(8)
    if is_fat(data):
        raise SystemExit("这是 fat 二进制，请先 lipo -thin arm64 拆分后再注入")
    thin_inject(path, dylib_path, dry)


if __name__ == "__main__":
    main()
