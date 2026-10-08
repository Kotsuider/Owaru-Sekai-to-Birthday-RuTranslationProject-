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


def main():
    parser = argparse.ArgumentParser(description="Отключение вывода фуриганы в байт-коде Majiro.")
    parser.add_argument("target", nargs="?", default="scenario", help="Папка scenario или путь к yazlib.mjil")
    args = parser.parse_args()

    if os.path.isdir(args.target):
        yazlib_path = os.path.join(args.target, "yazlib.mjil")
    else:
        yazlib_path = args.target

    success = patch_yazlib(yazlib_path)
    if not success and not os.path.isfile(yazlib_path):
        sys.exit(1)


if __name__ == "__main__":
    main()
