#!/usr/bin/env python3
"""
sanitize_mjres.py — Санитизация и валидация символов для компилятора Majiro (CP932/Shift-JIS)
Адаптирован для «終わる世界とバースデイ» (Owari no Sekai to Birthday).

Заменяет символы, отсутствующие в кодировке CP932 (« », —, –, „, •, ಠ, неразрывные пробелы и др.),
на их совместимые аналоги, предотвращая сбои компилятора maji.exe assemble.

Использование:
  python sanitize_mjres.py [scenario_dir]
"""

import sys
import os
import glob
import argparse

REPLACEMENTS = {
    "\u00AB": "\u201C",   # « -> “
    "\u00BB": "\u201D",   # » -> ”
    "\u201E": "\u201C",   # „ -> “
    "\u2014": "\u2015",   # — (em dash) -> ― (horizontal bar)
    "\u2013": "\u2015",   # – (en dash) -> ― (horizontal bar)
    "\u2012": "\u2015",   # figure dash -> ―
    "\u2022": "\u30FB",   # • (bullet) -> ・ (Japanese middle dot)
    "\u0CA0": "\u30FB",   # ಠ (Kannada letter / kaomoji ಠ_ಠ) -> ・ (・_・)
    "\u00A0": " ",        # non-breaking space -> space
    "\u202F": " ",        # narrow NBSP -> space
    "\u2009": " ",        # thin space -> space
    "\u200B": "",         # zero-width space -> nothing
    "\u200E": "",         # LTR mark -> nothing
    "\u200F": "",         # RTL mark -> nothing
    "\uFEFF": "",         # BOM inside text -> nothing
    "\u00F3": "o",        # ó -> o
    "\u00E9": "e",        # é -> e
    "\u00E8": "e",        # è -> e
    "\u00E0": "a",        # à -> a
}


def sanitize_file(path: str) -> tuple[bool, list[str]]:
    """Санитизирует файл и проверяет совместимость с CP932."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    changed = False
    for src, dst in REPLACEMENTS.items():
        if src in text:
            text = text.replace(src, dst)
            changed = True

    if changed:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(text)

    # Проверка совместимости с CP932
    unsupported = []
    for line_idx, line in enumerate(text.splitlines(), 1):
        for ch in line:
            try:
                ch.encode("cp932")
            except UnicodeEncodeError:
                unsupported.append(f"Строка {line_idx}: неподдерживаемый символ '{ch}' (U+{ord(ch):04X})")

    return changed, unsupported


def main():
    parser = argparse.ArgumentParser(description="Санитизация символов Unicode для Majiro")
    parser.add_argument("target_dir", nargs="?", default="scenario", help="Папка с .mjres файлами")
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.target_dir, "*.mjres")))
    if not files:
        print(f"Не найдено .mjres файлов в {args.target_dir}")
        return

    print(f"Санитизация символов в {len(files)} файлах...")
    sanitized_count = 0
    errors_found = 0

    for path in files:
        changed, unsupp = sanitize_file(path)
        if changed:
            sanitized_count += 1
        if unsupp:
            errors_found += 1
            print(f"  [ОШИБКА] {os.path.basename(path)}:")
            for err in unsupp[:5]:
                print(f"    {err}")
            if len(unsupp) > 5:
                print(f"    ... и ещё {len(unsupp) - 5} символов")

    print(f"Санитизировано файлов: {sanitized_count} из {len(files)}.")
    if errors_found == 0:
        print("Все символы полностью совместимы с CP932 / Majiro.")
        sys.exit(0)
    else:
        print(f"ОШИБКА: Найдено {errors_found} файлов с неподдерживаемыми символами!")
        sys.exit(1)


if __name__ == "__main__":
    main()
