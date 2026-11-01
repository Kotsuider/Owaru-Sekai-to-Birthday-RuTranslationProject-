#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNS-переписка Owari: таблица для перевода (md) и вставка при сборке.

Сообщение в игре — вызов из сценария::

    ldstr         "третья строка"
    ldstr         "вторая строка"
    ldstr         "первая строка"
    ldstr         "ナル"                 ; имя отправителя — ВСЕГДА последний аргумент
    callp         $03b8d38a (4)

Строки идут в обратном порядке отображения, максимум три строки на сообщение
(функция читает ``-3``/``-4``/``-5``). Текст лежит инлайн в .mjil, в .mjres его нет.

Сообщения — это праздная болтовня, не связанная с сценой, поэтому контекст в таблицу
не включается; зато одинаковые сообщения встречаются по несколько раз и схлопываются
в одну строку таблицы.

Команды::

    python sns_tool.py list  scenario
    python sns_tool.py gen   scenario -o sns.md
    python sns_tool.py apply sns.md scenario [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path

CALL_RE = re.compile(r"^\s*callp\s+\$03b8d38a\s+\((?P<argc>\d+)\)")
LDSTR_RE = re.compile(r'^(?P<indent>\s*ldstr\s+)"(?P<text>(?:[^"\\]|\\.)*)"\s*$')

SANITIZE = {
    "\u00ab": "\u201c",
    "\u00bb": "\u201d",
    "\u2014": "\u2015",
    "\u2013": "\u2015",
    "\u201e": "\u201c",
    "\u00f3": "o",
}

HEADER = ["ID", "Sender", "Orig", "TL", "×", "Where", "Notes"]
NAME_HEADER = ["Orig", "TL"]


@dataclass
class Message:
    file: str
    line: int          # строка вызова
    body: tuple[str, ...]   # строки в порядке отображения
    sender: str
    lines: list[int]   # индексы строк ldstr в файле (в порядке файла)


def sanitize(text: str) -> str:
    for src, dst in SANITIZE.items():
        text = text.replace(src, dst)
    return text


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "\\n")


def scan(path: Path) -> list[Message]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[Message] = []
    for i, line in enumerate(lines):
        m = CALL_RE.match(line)
        if not m:
            continue
        argc = int(m.group("argc"))
        texts: list[tuple[int, str]] = []
        j = i - 1
        while j >= 0 and len(texts) < argc:
            mm = LDSTR_RE.match(lines[j])
            if mm:
                texts.append((j, mm.group("text")))
            elif lines[j].strip() and not lines[j].strip().startswith("line "):
                break
            j -= 1
        if len(texts) != argc:
            continue
        texts.reverse()                      # порядок в файле
        sender = texts[-1][1]
        body = tuple(t for _, t in texts[:-1][::-1])   # порядок отображения
        out.append(Message(path.name, i + 1, body, sender, [k for k, _ in texts]))
    return out


def collect(scenario: Path) -> list[Message]:
    msgs: list[Message] = []
    for path in sorted(scenario.glob("*.mjil")):
        msgs.extend(scan(path))
    return msgs


def cmd_list(args) -> int:
    msgs = collect(Path(args.scenario))
    senders = Counter(m.sender for m in msgs)
    print(f"сообщений: {len(msgs)}, уникальных: {len({(m.sender, m.body) for m in msgs})}")
    for name, count in senders.most_common():
        print(f"  {name:12} {count}")
    return 0


def cmd_gen(args) -> int:
    scenario = Path(args.scenario)
    msgs = collect(scenario)
    if not msgs:
        print("error: сообщений не найдено", file=sys.stderr)
        return 1

    grouped: "OrderedDict[tuple[str, tuple[str, ...]], list[Message]]" = OrderedDict()
    for m in msgs:
        grouped.setdefault((m.sender, m.body), []).append(m)

    out = [
        f"# SNS-переписка — {scenario.resolve().name}",
        "",
        "Сообщения в углу экрана. Контекста нет: это праздная болтовня, она не связана",
        "со сценой и часто повторяется — одинаковые сообщения схлопнуты в одну строку.",
        "",
        "`Orig` — строки через литерал `\\n` (первая строка — верхняя в облачке).",
        "**TL обязан содержать столько же строк, сколько Orig**: число аргументов вызова",
        "фиксировано, лишние строки вставить нельзя. Пустой TL = сообщение останется",
        "на японском. Колонка `×` — сколько раз сообщение встречается в игре.",
        "",
        "| " + " | ".join(HEADER) + " |",
        "| " + " | ".join("---" for _ in HEADER) + " |",
    ]

    for n, ((sender, body), occurrences) in enumerate(grouped.items(), 1):
        first = occurrences[0]
        where = f"{first.file}:{first.line}"
        if len(occurrences) > 1:
            where += f" +{len(occurrences) - 1}"
        out.append(f"| S{n:03d} | {cell(sender)} | {cell(chr(10).join(body))} "
                   f"|  | {len(occurrences)} | {where} |  |")

    names = sorted({m.sender for m in msgs})
    out += [
        "",
        "## Имена отправителей",
        "",
        "Показываются в облачке рядом с аватаром. Пустой TL = остаётся как есть.",
        "",
        "| " + " | ".join(NAME_HEADER) + " |",
        "| " + " | ".join("---" for _ in NAME_HEADER) + " |",
    ]
    for name in names:
        out.append(f"| {cell(name)} |  |")

    Path(args.output).write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"{args.output}: {len(grouped)} уникальных сообщений из {len(msgs)}, "
          f"отправителей {len(names)}")
    return 0


def read_table(path: Path) -> tuple[dict[tuple[str, tuple[str, ...]], str],
                                    dict[str, str]]:
    msgs: dict[tuple[str, tuple[str, ...]], str] = {}
    names: dict[str, str] = {}
    section = "msg"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("##"):
            section = "name" if "Имена" in line else "msg"
            continue
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or cells[0] in ("ID", "Orig") or set(cells[0]) <= set("- "):
            continue
        if section == "name" and len(cells) >= 2:
            if cells[1]:
                names[cells[0]] = sanitize(cells[1])
            continue
        if len(cells) < 4:
            continue
        sender, orig, tl = cells[1], cells[2], cells[3]
        if not tl:
            continue
        body = norm(orig.split("\\n"))
        msgs[(sender, body)] = sanitize(tl)
    return msgs, names


def norm(body) -> tuple[str, ...]:
    """Ключ сообщения: хвостовые пробелы (в т.ч. идеографические) не значимы."""
    return tuple(line.rstrip() for line in body)


def cmd_apply(args) -> int:
    table, names = read_table(Path(args.table))
    if not table and not names:
        print(f"error: в {args.table} нет заполненных переводов", file=sys.stderr)
        return 1

    scenario = Path(args.scenario)
    msgs = collect(scenario)
    applied = already = skipped = 0
    warnings: list[str] = []
    touched: dict[str, list[tuple[int, str]]] = {}
    reverse_names = {v: k for k, v in names.items()}
    # обратная таблица: чтобы отличить «уже переведено» от «нет в таблице»
    reverse_table = {(snd, norm(tl.split("\\n"))) for (snd, _), tl in table.items()}

    for m in msgs:
        # если имя уже переведено прошлым прогоном — возвращаемся к оригиналу,
        # иначе сообщение не найдётся в таблице
        sender = reverse_names.get(m.sender, m.sender)
        new_name = names.get(sender)
        if new_name == m.sender:
            new_name = None
        key = (sender, norm(m.body))
        new_text = table.get(key)

        if new_text is None and key in reverse_table:
            already += 1
            if new_name:
                touched.setdefault(m.file, []).append(
                    (m.lines[-1], f'  ldstr         "{new_name}"'))
            continue

        if new_text:
            parts = new_text.split("\\n")
            if len(parts) != len(m.body):
                warnings.append(
                    f"{m.file}:{m.line} — в переводе {len(parts)} строк(и), "
                    f"а в вызове {len(m.body)}: {new_text[:40]}")
                skipped += 1
                new_text = None
            elif any('"' in p or "\\" in p for p in parts):
                warnings.append(f"{m.file}:{m.line} — кавычка/бэкслеш в переводе")
                skipped += 1
                new_text = None

        if not new_text and not new_name:
            continue
        if new_text and tuple(parts) == m.body:
            already += 1
            continue

        # индекс строки ldstr для i-й строки тела: тело идёт в обратном порядке
        for i, text in enumerate(m.body):
            if new_text:
                replacement = parts[i]
            else:
                replacement = text
            line_index = m.lines[len(m.body) - 1 - i]
            touched.setdefault(m.file, []).append(
                (line_index, f'  ldstr         "{replacement}"'))

        if new_name:
            touched.setdefault(m.file, []).append(
                (m.lines[-1], f'  ldstr         "{new_name}"'))

        if new_text:
            applied += 1

    for name, changes in touched.items():
        path = scenario / name
        with path.open(encoding="utf-8", newline="") as fh:
            lines = fh.read().splitlines(keepends=True)
        for index, new_line in changes:
            old = lines[index]
            ending = old[len(old.rstrip("\r\n")):]
            indent = old[: len(old) - len(old.lstrip())]
            lines[index] = indent + new_line.lstrip() + ending
        if not args.dry_run:
            with path.open("w", encoding="utf-8", newline="") as fh:
                fh.write("".join(lines))

    print(f"{'[dry-run] ' if args.dry_run else ''}вставлено сообщений: {applied}, "
          f"файлов: {len(touched)}, уже было: {already}")
    for w in warnings[:15]:
        print(f"  warning: {w}")
    if len(warnings) > 15:
        print(f"  ... ещё {len(warnings) - 15} предупреждений")
    if skipped:
        print(f"  пропущено: {skipped}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="SNS-переписка: таблица и вставка перевода")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="сводка по сообщениям")
    p.add_argument("scenario")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("gen", help="сгенерировать md-таблицу")
    p.add_argument("scenario")
    p.add_argument("-o", "--output", default="sns.md")
    p.set_defaults(func=cmd_gen)

    p = sub.add_parser("apply", help="вставить перевод из md в .mjil")
    p.add_argument("table")
    p.add_argument("scenario")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_apply)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
