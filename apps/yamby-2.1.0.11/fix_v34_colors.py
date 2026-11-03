#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 values-v34/colors.xml 里的私有 @android:color 引用替换为 Material 3 标准色值字面量。
原因：aapt2 在 targetSdk 34+ 下拒绝框架私有资源，导致 apktool 重编译失败。"""
import re, sys

M = {
 # dark dynamic
 "m3_sys_color_dynamic_dark_background": "#FF1C1B1F",
 "m3_sys_color_dynamic_dark_error": "#FFF2B8B5",
 "m3_sys_color_dynamic_dark_error_container": "#FF8C1D18",
 "m3_sys_color_dynamic_dark_inverse_on_surface": "#FF1C1B1F",
 "m3_sys_color_dynamic_dark_inverse_primary": "#FF6750A4",
 "m3_sys_color_dynamic_dark_inverse_surface": "#FFE6E1E5",
 "m3_sys_color_dynamic_dark_on_background": "#FFE6E1E5",
 "m3_sys_color_dynamic_dark_on_error": "#FF601410",
 "m3_sys_color_dynamic_dark_on_error_container": "#FFF9DEDC",
 "m3_sys_color_dynamic_dark_on_primary": "#FF381E72",
 "m3_sys_color_dynamic_dark_on_primary_container": "#FFF3EDF7",
 "m3_sys_color_dynamic_dark_on_secondary": "#FF332D41",
 "m3_sys_color_dynamic_dark_on_secondary_container": "#FFE8DEF8",
 "m3_sys_color_dynamic_dark_on_surface": "#FFE6E1E5",
 "m3_sys_color_dynamic_dark_on_surface_variant": "#FFCAC4D0",
 "m3_sys_color_dynamic_dark_on_tertiary": "#FF492532",
 "m3_sys_color_dynamic_dark_on_tertiary_container": "#FFFFD8E4",
 "m3_sys_color_dynamic_dark_outline": "#FF938F99",
 "m3_sys_color_dynamic_dark_outline_variant": "#FF49454F",
 "m3_sys_color_dynamic_dark_primary": "#FFD0BCFF",
 "m3_sys_color_dynamic_dark_primary_container": "#FF4F378B",
 "m3_sys_color_dynamic_dark_secondary": "#FFCCC2DC",
 "m3_sys_color_dynamic_dark_secondary_container": "#FF4A4458",
 "m3_sys_color_dynamic_dark_surface": "#FF1C1B1F",
 "m3_sys_color_dynamic_dark_surface_bright": "#FF3B383E",
 "m3_sys_color_dynamic_dark_surface_container": "#FF211F26",
 "m3_sys_color_dynamic_dark_surface_container_high": "#FF2B2930",
 "m3_sys_color_dynamic_dark_surface_container_highest": "#FF36343B",
 "m3_sys_color_dynamic_dark_surface_container_low": "#FF1D1B20",
 "m3_sys_color_dynamic_dark_surface_container_lowest": "#FF0F0D13",
 "m3_sys_color_dynamic_dark_surface_dim": "#FF141218",
 "m3_sys_color_dynamic_dark_surface_variant": "#FF49454F",
 "m3_sys_color_dynamic_dark_tertiary": "#FFEFB8C8",
 "m3_sys_color_dynamic_dark_tertiary_container": "#FF633B48",
 # light dynamic
 "m3_sys_color_dynamic_light_background": "#FFFEF7FF",
 "m3_sys_color_dynamic_light_error": "#FFB3261E",
 "m3_sys_color_dynamic_light_error_container": "#FFF9DEDC",
 "m3_sys_color_dynamic_light_inverse_on_surface": "#FFF5EFF7",
 "m3_sys_color_dynamic_light_inverse_primary": "#FFD0BCFF",
 "m3_sys_color_dynamic_light_inverse_surface": "#FF322F35",
 "m3_sys_color_dynamic_light_on_background": "#FF1D1B20",
 "m3_sys_color_dynamic_light_on_error": "#FFFFFFFF",
 "m3_sys_color_dynamic_light_on_error_container": "#FF410E0B",
 "m3_sys_color_dynamic_light_on_primary": "#FFFFFFFF",
 "m3_sys_color_dynamic_light_on_primary_container": "#FF21005D",
 "m3_sys_color_dynamic_light_on_secondary": "#FFFFFFFF",
 "m3_sys_color_dynamic_light_on_secondary_container": "#FF1D192B",
 "m3_sys_color_dynamic_light_on_surface": "#FF1D1B20",
 "m3_sys_color_dynamic_light_on_surface_variant": "#FF49454F",
 "m3_sys_color_dynamic_light_on_tertiary": "#FFFFFFFF",
 "m3_sys_color_dynamic_light_on_tertiary_container": "#FF31111D",
 "m3_sys_color_dynamic_light_outline": "#FF79747E",
 "m3_sys_color_dynamic_light_outline_variant": "#FFCAC4D0",
 "m3_sys_color_dynamic_light_primary": "#FF6750A4",
 "m3_sys_color_dynamic_light_primary_container": "#FFEADDFF",
 "m3_sys_color_dynamic_light_secondary": "#FF625B71",
 "m3_sys_color_dynamic_light_secondary_container": "#FFE8DEF8",
 "m3_sys_color_dynamic_light_surface": "#FFFEF7FF",
 "m3_sys_color_dynamic_light_surface_bright": "#FFFFFBFE",
 "m3_sys_color_dynamic_light_surface_container": "#FFF3EDF7",
 "m3_sys_color_dynamic_light_surface_container_high": "#FFECE6F0",
 "m3_sys_color_dynamic_light_surface_container_highest": "#FFE6E0E9",
 "m3_sys_color_dynamic_light_surface_container_low": "#FFF7F2FA",
 "m3_sys_color_dynamic_light_surface_container_lowest": "#FFFFFFFF",
 "m3_sys_color_dynamic_light_surface_dim": "#FFDED8E1",
 "m3_sys_color_dynamic_light_surface_variant": "#FFE7E0EC",
 "m3_sys_color_dynamic_light_tertiary": "#FF7D5260",
 "m3_sys_color_dynamic_light_tertiary_container": "#FFFFD8E4",
 # fixed
 "m3_sys_color_dynamic_on_primary_fixed": "#FF21005D",
 "m3_sys_color_dynamic_on_primary_fixed_variant": "#FF4F378B",
 "m3_sys_color_dynamic_on_secondary_fixed": "#FF1D192B",
 "m3_sys_color_dynamic_on_secondary_fixed_variant": "#FF4A4458",
 "m3_sys_color_dynamic_on_tertiary_fixed": "#FF31111D",
 "m3_sys_color_dynamic_on_tertiary_fixed_variant": "#FF633B48",
 "m3_sys_color_dynamic_primary_fixed": "#FFEADDFF",
 "m3_sys_color_dynamic_primary_fixed_dim": "#FFD0BCFF",
 "m3_sys_color_dynamic_secondary_fixed": "#FFE8DEF8",
 "m3_sys_color_dynamic_secondary_fixed_dim": "#FFCCC2DC",
 "m3_sys_color_dynamic_tertiary_fixed": "#FFFFD8E4",
 "m3_sys_color_dynamic_tertiary_fixed_dim": "#FFEFB8C8",
}

path = sys.argv[1]
src = open(path, encoding='utf-8').read()
out, miss = [], []
for line in src.splitlines():
    m = re.match(r'(\s*<color name="([^"]+)">)@android:color/([A-Za-z0-9_]+)(</color>)', line)
    if m:
        name = m.group(2)
        val = M.get(name)
        if not val:
            miss.append((name, m.group(3)))
            val = "#FF000000"
        line = f'{m.group(1)}{val}{m.group(4)}'
    out.append(line)
open(path, 'w', encoding='utf-8').write("\n".join(out) + "\n")
print("替换完成；未在映射表中的条目:", miss if miss else "无")
