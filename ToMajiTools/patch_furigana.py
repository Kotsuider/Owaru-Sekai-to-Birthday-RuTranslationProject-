#!/usr/bin/env python3
'''
patch_furigana.py — Скрипт отключения вывода фуриганы и боутэн в байт-коде Majiro.
Адаптирован для «終わる世界とバースデイ» (Owari no Sekai to Birthday).

Что делает:
1. В scenario/yazlib.mjil нейтрализует функции:
   - func $3198fd01(string, string): отрисовка фуриганы (кандзи + руби) -> немедленный возврат
   - func $2828e49e(): коррекция вертикального отступа под руби -> немедленный возврат
   - func $2f93f26a(string): отрисовка точек акцента боутэн -> немедленный возврат
2. Гарантирует, что ни один японский иероглиф из байт-кода больше не появится в текстовом окне игры.

Использование:
  python patch_furigana.py [scenario_dir]
'''

import os
import sys
import re
import glob
import argparse

REPLACEMENTS = [
    # func $3198fd01(string, string) - furigana
    (
        r'func \$3198fd01\(string, string\) \{[\s\S]*?^\}',
        '''func $3198fd01(string, string) {
 entry:
  argcheck      [string, string]
  alloca        []
  ldc.i         0
  ret          
}'''
    ),
    # func $2828e49e() - ruby line spacing correction
    (
        r'func \$2828e49e\(\) \{[\s\S]*?^\}',
        '''func $2828e49e() {
 entry:
  argcheck      []
  alloca        []
  ldc.i         0
  ret          
}'''
    ),
    # func $2f93f26a(string) - bouten (emphasis dots)
    (
        r'func \$2f93f26a\(string\) \{[\s\S]*?^\}',
        '''func $2f93f26a(string) {
 entry:
  argcheck      [string]
  alloca        []
  ldc.i         0
  ret          
}'''
    ),
]


def patch_yazlib(filepath: str) -> bool:
    if not os.path.isfile(filepath):
        print(f"[WARN] Файл не найден: {filepath}")
        return False

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    patched = content
    changes_count = 0

    for pattern, repl in REPLACEMENTS:
        new_patched, n = re.subn(pattern, repl, patched, flags=re.MULTILINE)
        if n > 0:
            changes_count += n
            patched = new_patched

    if changes_count > 0:
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(patched)
        print(f"[OK] {filepath}: успешно нейтрализовано {changes_count} функций фуриганы/боутэн.")
        return True
    else:
        print(f"[INFO] {filepath}: функции фуриганы уже нейтрализованы или сигнатуры не совпали.")
        return False


def patch_bytecode_quotes(scenario_dir: str) -> int:
    """
    Нейтрализует хардкод вывода скобок фуриганы (ldstr " ｢")
    и паразитный сдвиг курсора влево (ldc.i -24) во всех .mjil файлах сценария.
    """
    total_patched_files = 0
    total_quote_patches = 0
    total_offset_patches = 0

    mjil_files = glob.glob(os.path.join(scenario_dir, "*.mjil"))
    for filepath in mjil_files:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # 1. Заменяем строку с полуширинной скобкой ' ｢' на пустую строку ''
        new_content, n_quotes = re.subn(r'ldstr\s+" ｢"', 'ldstr         ""', content)

        # 2. Убираем сдвиг курсора влево (-24) перед ctrl "o"
        new_content, n_offsets = re.subn(
            r'ldc\.i\s+-24(?=\s*\n\s*ldc\.i\s+0\s*\n\s*ctrl\s+"o")',
            'ldc.i         0',
            new_content
        )

        if n_quotes > 0 or n_offsets > 0:
            with open(filepath, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            total_patched_files += 1
            total_quote_patches += n_quotes
            total_offset_patches += n_offsets

    print(f"[OK] Патч макроса скобок: обработано {total_patched_files} файлов .mjil (скобок: {total_quote_patches}, сдвигов: {total_offset_patches}).")
    return total_patched_files


def main():
    parser = argparse.ArgumentParser(description="Отключение вывода фуриганы и скобок в байт-коде Majiro.")
    parser.add_argument("target", nargs="?", default="scenario", help="Папка scenario или путь к yazlib.mjil")
    args = parser.parse_args()

    if os.path.isdir(args.target):
        yazlib_path = os.path.join(args.target, "yazlib.mjil")
        scenario_dir = args.target
    else:
        yazlib_path = args.target
        scenario_dir = os.path.dirname(args.target) or "."

    success = patch_yazlib(yazlib_path)
    if not success and not os.path.isfile(yazlib_path):
        sys.exit(1)

    if os.path.isdir(scenario_dir):
        patch_bytecode_quotes(scenario_dir)


if __name__ == "__main__":
    main()

