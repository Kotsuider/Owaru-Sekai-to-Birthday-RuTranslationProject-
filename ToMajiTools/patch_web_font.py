#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_web_font.py — Патчинг шрифтов для онлайн-чата, сети TEXI, меню выборов и UI в Majiro.
Адаптирован для «終わる世界とバースデイ» (Owari no Sekai to Birthday).

Что делает:
1. Заменяет все жестко захардкоженные японские шрифты во всех .mjil файлах scenario:
   - "ＭＳ Ｐゴシック" -> новый шрифт (чат, TEXI/SNS)
   - "MS UI Gothic"     -> новый шрифт (системные message box'ы)
   - "ＭＳ ゴシック"   -> новый шрифт (pic, console, yazlib)
   - "ＭＳ Ｐ明朝"     -> новый шрифт (music)
2. Патчит шрифт кнопок меню выборов в scenario/menu.mjil:
   Заменяет чтение шрифта меню $04f9eb39 на прямой вызов нового шрифта.

Использование:
  python patch_web_font.py [scenario_dir] [--font "M+ 1m regular"]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_NEW_FONT = "M+ 1m regular"

# Список оригинальных японских шрифтов для сквозной замены
HARDCODED_FONTS = [
    "ＭＳ Ｐゴシック",
    "MS UI Gothic",
    "ＭＳ ゴシック",
    "ＭＳ Ｐ明朝",
]


def patch_mjil_files(scenario_dir: Path, new_font: str) -> tuple[int, int]:
    """Сквозная замена всех строковых имён японских шрифтов во всех .mjil файлах."""
    total_replaced = 0
    files_changed = 0

    for mjil_path in sorted(scenario_dir.glob("*.mjil")):
        try:
            content = mjil_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  [ERROR] Cannot read {mjil_path.name}: {e}", file=sys.stderr)
            continue

        file_replacements = 0
        for old_font in HARDCODED_FONTS:
            old_pattern = f'ldstr         "{old_font}"'
            new_pattern = f'ldstr         "{new_font}"'
            count = content.count(old_pattern)
            if count > 0:
                content = content.replace(old_pattern, new_pattern)
                file_replacements += count

        if file_replacements > 0:
            mjil_path.write_text(content, encoding="utf-8", newline="\n")
            total_replaced += file_replacements
            files_changed += 1
            print(f"  [OK] {mjil_path.name}: replaced {file_replacements} font occurrence(s)")

    return total_replaced, files_changed


def patch_menu_choices_font(scenario_dir: Path, new_font: str) -> bool:
    """
    В menu.mjil шрифт меню выборов читается в переменную $04f9eb39 из menudata.cfg.
    Патчим menu.mjil, чтобы переменная $04f9eb39 принудительно перезаписывалась новым шрифтом,
    а также заменяем прямое обращение к ней перед вызовом $fontout_font на ldstr "{new_font}".
    """
    menu_path = scenario_dir / "menu.mjil"
    if not menu_path.exists():
        return False

    content = menu_path.read_text(encoding="utf-8")

    # 1. Заменяем чтение переменной $04f9eb39 перед syscallp $fontout_font (4)
    old_call = 'ld            persistent string $04f9eb39 \n  syscallp      $fontout_font (4)'
    new_call = f'ldstr         "{new_font}"\n  syscallp      $fontout_font (4)'

    # Также проверяем вариант без пробела перед переводом строки
    old_call_trim = 'ld            persistent string $04f9eb39\n  syscallp      $fontout_font (4)'

    count = content.count(old_call) + content.count(old_call_trim)
    if count > 0:
        content = content.replace(old_call, new_call).replace(old_call_trim, new_call)
        print(f"  [OK] menu.mjil: patched {count} choice menu $fontout_font call(s) to '{new_font}'")

    # 2. Перезаписываем переменную $04f9eb39 в функциях $menu_renewal@MENU и $main@MENU
    # Вместо чтения из menudata.cfg принудительно кладём new_font
    old_assign = 'st.s          persistent string $04f9eb39'
    if old_assign in content:
        # заменяем:
        # ld local int ... / syscall $file_read$ (1) / st.s persistent string $04f9eb39
        # на принудительную установку
        content = content.replace(
            f'st.s          persistent string $04f9eb39 \n  pop',
            f'pop\n  ldstr         "{new_font}"\n  st.s          persistent string $04f9eb39 \n  pop'
        )

    menu_path.write_text(content, encoding="utf-8", newline="\n")
    return True


def patch_config_font_dialog(scenario_dir: Path) -> bool:
    """
    Патчит scenario/config.mjil:
    В функции диалога выбора шрифта кнопкой ID 121 заменяет флаг confont_isproportional на 2 (любой шрифт / без фильтрации Shift-JIS/пропорциональности):
      ld persistent int $b5788291 -> ldc.i 2
    """
    config_path = scenario_dir / "config.mjil"
    if not config_path.exists():
        return False

    content = config_path.read_text(encoding="utf-8")

    old_target = """ block_5280:
  line          #735
  ld            persistent int $b5788291  ; #confont_isproportional@SYSTEM
  ld            persistent string $391053c5  ; #confont_name$@SYSTEM
  syscall       $font_dialog$ (2)"""

    new_target = """ block_5280:
  line          #735
  ldc.i         2  ; #confont_isproportional@SYSTEM
  ld            persistent string $391053c5  ; #confont_name$@SYSTEM
  syscall       $font_dialog$ (2)"""

    if old_target in content:
        content = content.replace(old_target, new_target)
        config_path.write_text(content, encoding="utf-8", newline="\n")
        print("  [OK] config.mjil: patched $font_dialog$ to ldc.i 2 (unlock all fonts in config)")
        return True
    elif new_target in content:
        print("  [INFO] config.mjil: $font_dialog$ is already patched (ldc.i 2)")
        return True
    else:
        print("  [WARN] config.mjil: target pattern for $font_dialog$ not found!")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Patch hardcoded fonts in Majiro scenario disassemblies (.mjil)"
    )
    parser.add_argument(
        "scenario_dir",
        nargs="?",
        default="scenario",
        help="Path to scenario directory (default: 'scenario')"
    )
    parser.add_argument(
        "--font",
        default=DEFAULT_NEW_FONT,
        help=f"New font name (default: '{DEFAULT_NEW_FONT}')"
    )

    args = parser.parse_args()
    scenario_path = Path(args.scenario_dir)

    if not scenario_path.is_dir():
        print(f"[ERROR] Directory not found: {scenario_path}", file=sys.stderr)
        return 1

    print(f"=== Patching All Hardcoded Fonts ===")
    print(f"Scenario directory: {scenario_path}")
    print(f"Target font: '{args.font}'")

    total, files = patch_mjil_files(scenario_path, args.font)
    patch_menu_choices_font(scenario_path, args.font)
    patch_config_font_dialog(scenario_path)

    print(f"Completed: updated {total} hardcoded font string(s) across {files} file(s) + menu.mjil + config.mjil.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
