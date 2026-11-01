#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Отдельные строки интерфейса: таблица ui.md и вставка при сборке.

В отличие от выборов и SNS, здесь нет повторяющейся структуры — это редкие
строки, которые собираются в рантайме. Пример — вопрос подтверждения дня рождения
(`sns.mjil`)::

    ldstr         "誕生日を"
    ld  savefile int $7af3da5e      ; месяц
    call $e55f0668 (1)              ; число -> строка
    add.s
    ldstr         "月"
    add.s
    ld  savefile int $c1dbe37a      ; день
    call $e55f0668 (1)
    add.s
    ldstr         "日に設定しますか？"
    add.s
    call  $$askyesno@MSG_BOX (1)

Итоговая строка = «誕生日を» + месяц + «月» + день + «日に設定しますか？».
Переводить надо три куска, сохраняя осмысленный порядок «месяц/день».

Строки ищутся **последовательно**: строки таблицы для одного файла применяются
по порядку, каждая следующая ищется начиная с места предыдущей. Поэтому
неоднозначные тексты (например, «月» встречается дважды) попадают куда надо.

Если перевод должен заканчиваться пробелом, заключите его в кавычки::

    | U001 | sns.mjil | 誕生日を | "День рождения: " | ... |

Команды::

    python ui_tool.py list  ui.md
    python ui_tool.py apply ui.md scenario [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

LDSTR_RE = re.compile(r'^(?P<indent>\s*ldstr\s+)"(?P<text>(?:[^"\\]|\\.)*)"\s*$')

SANITIZE = {
    "\u00ab": "\u201c",
    "\u00bb": "\u201d",
    "\u2014": "\u2015",
    "\u2013": "\u2015",
    "\u201e": "\u201c",
    "\u00f3": "o",
}


@dataclass
class Row:
    sid: str
    file: str
    orig: str
    tl: str
    note: str


def sanitize(text: str) -> str:
    for src, dst in SANITIZE.items():
        text = text.replace(src, dst)
    return text


def read_table(path: Path) -> list[Row]:
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or cells[0] in ("ID", "") or set(cells[0]) <= set("- "):
            continue
        tl = cells[3]
        # кавычки защищают значимые пробелы по краям
        if len(tl) >= 2 and tl[0] == '"' and tl[-1] == '"':
            tl = tl[1:-1]
        rows.append(Row(sid=cells[0], file=cells[1], orig=cells[2],
                        tl=sanitize(tl), note=cells[4] if len(cells) > 4 else ""))
    return rows


def cmd_list(args) -> int:
    rows = read_table(Path(args.table))
    print(f"строк в таблице: {len(rows)}")
    for r in rows:
        mark = "" if r.tl else "  (без перевода)"
        print(f"  {r.sid} {r.file}: «{r.orig}» -> «{r.tl}»{mark}")
    return 0


def cmd_apply(args) -> int:
    rows = read_table(Path(args.table))
    if not rows:
        print(f"error: {args.table} пуст", file=sys.stderr)
        return 1

    scenario = Path(args.scenario)
    by_file: dict[str, list[Row]] = {}
    for row in rows:
        by_file.setdefault(row.file, []).append(row)

    applied = skipped = 0
    problems: list[str] = []

    for name, file_rows in by_file.items():
        path = scenario / name
        if not path.exists():
            problems.append(f"{name}: файла нет в {scenario}")
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            lines = fh.read().splitlines(keepends=True)

        cursor = 0
        changed = False
        for row in file_rows:
            if not row.tl:
                skipped += 1
                continue
            found = -1
            for i in range(cursor, len(lines)):
                m = LDSTR_RE.match(lines[i])
                if m and m.group("text") == row.orig:
                    found = i
                    break
            if found < 0:
                problems.append(f"{row.sid} ({name}): не найдено «{row.orig}» "
                                f"после строки {cursor}")
                continue

            old = lines[found]
            ending = old[len(old.rstrip("\r\n")):]
            indent = old[: len(old) - len(old.lstrip())]
            lines[found] = f'{indent}ldstr         "{row.tl}"{ending}'
            cursor = found + 1
            applied += 1
            changed = True

        if changed and not args.dry_run:
            with path.open("w", encoding="utf-8", newline="") as fh:
                fh.write("".join(lines))

    print(f"{'[dry-run] ' if args.dry_run else ''}заменено строк: {applied}, "
          f"файлов: {len(by_file)}")
    for p in problems:
        print(f"  warning: {p}")
    if skipped:
        print(f"  без перевода: {skipped}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Отдельные строки интерфейса")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="показать таблицу")
    p.add_argument("table")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("apply", help="вставить перевод в .mjil")
    p.add_argument("table")
    p.add_argument("scenario")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_apply)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
