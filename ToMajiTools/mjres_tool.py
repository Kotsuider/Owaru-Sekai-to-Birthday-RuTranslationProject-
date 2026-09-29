#!/usr/bin/env python3
"""
mjres_tool.py — Универсальный инструмент извлечения, вставки и конвертации для Majiro (.mjres <-> .md / .xlsx)
Адаптирован для «終わる世界とバースデイ» (Owari no Sekai to Birthday).

Основные команды:
  python mjres_tool.py insert Owari -o scenario
  python mjres_tool.py insert Owari.xlsx -o scenario
  python mjres_tool.py extract scenario -o Owari_export.xlsx
  python mjres_tool.py md2xlsx Owari -o Owari.xlsx
  python mjres_tool.py xlsx2md Owari.xlsx -o Owari
"""

import sys
import os
import csv
import io
import re
import glob
import argparse

# ---------------------------------------------------------------------------
# Формат таблиц
# ---------------------------------------------------------------------------
HEADERS = ["L", "OrigName", "Orig", "NameTL", "TL", "TLE", "Notes"]


# ---------------------------------------------------------------------------
# Парсер .mjres
# ---------------------------------------------------------------------------
def parse_mjres(path: str) -> list[tuple[str, str]]:
    """Парсит CSV-файл .mjres. Возвращает список кортежей (Key, Value)."""
    with open(path, encoding="utf-8", newline="") as f:
        content = f.read()

    reader = csv.reader(io.StringIO(content))
    rows = []
    first = True
    for row in reader:
        if first:
            first = False
            continue  # Пропускаем заголовок "Key,Value"
        if len(row) < 2:
            continue
        key = row[0].strip()
        value = row[1]
        rows.append((key, value))
    return rows


def split_name(value: str) -> tuple[str, str]:
    """
    Извлекает имя персонажа из строки вида: Имя「реплика」
    Возвращает (имя, текст). Если имени нет, возвращает ("", value).
    """
    idx = value.find("「")
    if idx == -1:
        return "", value
    return value[:idx], value


# ---------------------------------------------------------------------------
# Парсер Markdown (.md)
# ---------------------------------------------------------------------------
def parse_md_table(path: str) -> list[dict]:
    """
    Парсит markdown-таблицу перевода:
    | L | OrigName | Orig | NameTL | TL | TLE | Notes |
    """
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                continue

            # Разбиение с учётом экранированных пайпов \|
            parts = re.split(r"(?<!\\)\|", line)
            parts = [p.strip().replace(r"\|", "|") for p in parts]
            if parts and parts[0] == "":
                parts = parts[1:]
            if parts and parts[-1] == "":
                parts = parts[:-1]

            if not parts:
                continue

            # Пропускаем строку заголовка и разделителя
            if parts[0] == "L" or parts[0].startswith("---"):
                continue

            key = parts[0]
            origname = parts[1] if len(parts) > 1 else ""
            orig = parts[2] if len(parts) > 2 else ""
            nametl = parts[3] if len(parts) > 3 else ""
            tl = parts[4] if len(parts) > 4 else ""
            tle = parts[5] if len(parts) > 5 else ""
            notes = parts[6] if len(parts) > 6 else ""

            rows.append({
                "key": key,
                "origname": origname,
                "orig": orig,
                "nametl": nametl,
                "tl": tl,
                "tle": tle,
                "notes": notes,
            })
    return rows


# ---------------------------------------------------------------------------
# ВСТАВКА (INSERT): из Markdown или Excel в .mjres
# ---------------------------------------------------------------------------
def get_mjres_name_from_md(md_basename: str) -> str:
    """Преобразует имя .md файла (например Owari_プロローグ前半010.md) в имя .mjres."""
    name = os.path.splitext(md_basename)[0]
    if name.startswith("Owari_"):
        name = name[6:]
    return name + ".mjres"


def write_mjres_rows(outpath: str, rows: list[tuple[str, str]]):
    """Записывает строки в .mjres с соблюдением стандартов CSV Majiro."""
    out_buf = io.BytesIO()
    out_buf.write(b"Key,Value\r\n")
    for key, val in rows:
        if "," in val or '"' in val or "\n" in val:
            escaped = val.replace('"', '""')
            line_str = f'{key},"{escaped}"\r\n'
        else:
            line_str = f"{key},{val}\r\n"
        out_buf.write(line_str.encode("utf-8"))

    os.makedirs(os.path.dirname(outpath) or ".", exist_ok=True)
    with open(outpath, "wb") as f:
        f.write(out_buf.getvalue())


def cmd_insert_from_md(md_input: str, outdir: str):
    """Вставляет перевод из одного .md файла или папки с .md файлами в .mjres."""
    if os.path.isdir(md_input):
        md_files = sorted(glob.glob(os.path.join(md_input, "*.md")))
    elif os.path.isfile(md_input):
        md_files = [md_input]
    else:
        sys.exit(f"Ошибка: путь не найден: {md_input}")

    if not md_files:
        sys.exit(f"Ошибка: не найдено .md файлов в: {md_input}")

    os.makedirs(outdir, exist_ok=True)
    processed = 0
    total_tl_lines = 0

    for mf in md_files:
        mjres_filename = get_mjres_name_from_md(os.path.basename(mf))
        target_mjres = os.path.join(outdir, mjres_filename)

        md_rows = parse_md_table(mf)
        if not md_rows:
            continue

        md_dict = {r["key"]: r for r in md_rows}

        # Если целевой mjres уже существует (например, скопирован из st/), обновляем его
        if os.path.isfile(target_mjres):
            orig_mjres_rows = parse_mjres(target_mjres)
        else:
            orig_mjres_rows = [(r["key"], r["orig"]) for r in md_rows]

        updated_rows = []
        file_tl_count = 0

        for key, orig_val in orig_mjres_rows:
            if key in md_dict:
                row = md_dict[key]
                tle = row["tle"]
                tl = row["tl"]
                nametl = row["nametl"]
                origname = row["origname"]
                orig_text = row["orig"]

                chosen_text = tle if tle else (tl if tl else orig_text)
                if chosen_text:
                    chosen_text = chosen_text.replace("\\n", "\n")

                if tle or tl or nametl:
                    file_tl_count += 1

                final_name = nametl if nametl else origname
                if final_name:
                    final_val = f"{final_name}「{chosen_text}」"
                else:
                    final_val = chosen_text
            else:
                final_val = orig_val

            updated_rows.append((key, final_val))

        write_mjres_rows(target_mjres, updated_rows)
        processed += 1
        total_tl_lines += file_tl_count

    print(f"Успешно обработано {processed} файлов .md ({total_tl_lines} переведённых строк) -> {outdir}/")


def cmd_insert_from_xlsx(input_xlsx: str, outdir: str):
    """Вставляет перевод из .xlsx файла в .mjres."""
    try:
        import openpyxl
    except ImportError:
        sys.exit("Ошибка: библиотека openpyxl не установлена. Выполните: pip install openpyxl")

    if not os.path.isfile(input_xlsx):
        sys.exit(f"Ошибка: файл не найден: {input_xlsx}")

    os.makedirs(outdir, exist_ok=True)
    wb = openpyxl.load_workbook(input_xlsx, data_only=True)

    processed = 0
    for ws in wb.worksheets:
        rows_out = []
        has_translation = False

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or row[0] is None:
                continue

            key = str(row[0]).strip()
            orig_name = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            orig_text = str(row[2]).strip() if len(row) > 2 and row[2] is not None else ""
            name_tl = str(row[3]).strip() if len(row) > 3 and row[3] is not None else ""
            tl = str(row[4]).strip() if len(row) > 4 and row[4] is not None else ""
            tle = str(row[5]).strip() if len(row) > 5 and row[5] is not None else ""

            if name_tl or tl or tle:
                has_translation = True

            insert_value = tle if tle else (tl if tl else orig_text)
            if insert_value is None:
                continue

            insert_value = insert_value.replace("\\n", "\n")

            final_name = name_tl if name_tl else orig_name
            if final_name:
                full_value = final_name + "「" + insert_value + "」"
            else:
                full_value = insert_value

            rows_out.append((key, full_value))

        if not rows_out or not has_translation:
            continue

        safe_name = re.sub(r'[\\/:*?"<>|]', "_", ws.title)
        outpath = os.path.join(outdir, safe_name + ".mjres")
        write_mjres_rows(outpath, rows_out)
        processed += 1

    print(f"Успешно обработано {processed} листов из {input_xlsx} -> {outdir}/")


# ---------------------------------------------------------------------------
# ИЗВЛЕЧЕНИЕ (EXTRACT): из .mjres в Excel или Markdown
# ---------------------------------------------------------------------------
def cmd_extract_to_xlsx(inputs: list[str], output_xlsx: str):
    """Извлекает строки из .mjres файлов в книгу .xlsx."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        sys.exit("Ошибка: библиотека openpyxl не установлена. Выполните: pip install openpyxl")

    files = []
    for inp in inputs:
        if os.path.isdir(inp):
            files.extend(sorted(glob.glob(os.path.join(inp, "*.mjres"))))
        elif os.path.isfile(inp):
            files.append(inp)

    if not files:
        sys.exit("Не найдено файлов .mjres для извлечения.")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill("solid", fgColor="2F5496")
    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    cell_font = Font(name="Arial", size=10)
    wrap = Alignment(wrap_text=True, vertical="top")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    col_widths = [8, 18, 45, 18, 45, 45, 25]

    for path in files:
        sheet_name = os.path.splitext(os.path.basename(path))[0][:31]
        ws = wb.create_sheet(title=sheet_name)

        for ci, h in enumerate(HEADERS, 1):
            c = ws.cell(row=1, column=ci, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = wrap
            c.border = border
        ws.row_dimensions[1].height = 18

        for ri, (key, value) in enumerate(parse_mjres(path), 2):
            orig_name, _ = split_name(value)
            if orig_name:
                orig_text = value[len(orig_name) + 1:]
                if orig_text.endswith("」"):
                    orig_text = orig_text[:-1]
            else:
                orig_text = value

            orig_text_cell = orig_text.replace("\n", "\\n")

            def put(ci, v):
                c = ws.cell(row=ri, column=ci, value=v)
                c.font = cell_font
                c.alignment = wrap
                c.border = border

            put(1, key)
            put(2, orig_name if orig_name else None)
            put(3, orig_text_cell)
            put(4, None)
            put(5, None)
            put(6, None)
            put(7, None)

        for ci, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(ci)].width = w
        ws.freeze_panes = "A2"

    wb.save(output_xlsx)
    print(f"Экспортировано {len(files)} файлов .mjres в {output_xlsx}")


# ---------------------------------------------------------------------------
# КОНВЕРТАЦИЯ: MD <-> XLSX
# ---------------------------------------------------------------------------
def cmd_md2xlsx(md_dir: str, out_xlsx: str):
    """Конвертирует все файлы .md в один файл .xlsx со страницами."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        sys.exit("Ошибка: библиотека openpyxl не установлена.")

    md_files = sorted(glob.glob(os.path.join(md_dir, "*.md")))
    if not md_files:
        sys.exit(f"Не найдено .md файлов в {md_dir}")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill("solid", fgColor="2F5496")
    header_font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    cell_font = Font(name="Arial", size=10)
    wrap = Alignment(wrap_text=True, vertical="top")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    col_widths = [8, 18, 45, 18, 45, 45, 25]

    for mf in md_files:
        name = os.path.splitext(os.path.basename(mf))[0]
        if name.startswith("Owari_"):
            name = name[6:]
        sheet_name = name[:31]
        ws = wb.create_sheet(title=sheet_name)

        for ci, h in enumerate(HEADERS, 1):
            c = ws.cell(row=1, column=ci, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = wrap
            c.border = border
        ws.row_dimensions[1].height = 18

        rows = parse_md_table(mf)
        for ri, r in enumerate(rows, 2):
            def put(ci, v):
                c = ws.cell(row=ri, column=ci, value=v if v else None)
                c.font = cell_font
                c.alignment = wrap
                c.border = border

            put(1, r["key"])
            put(2, r["origname"])
            put(3, r["orig"])
            put(4, r["nametl"])
            put(5, r["tl"])
            put(6, r["tle"])
            put(7, r["notes"])

        for ci, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(ci)].width = w
        ws.freeze_panes = "A2"

    wb.save(out_xlsx)
    print(f"Сконвертировано {len(md_files)} файлов .md -> {out_xlsx}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="mjres_tool.py — Извлечение, вставка и конвертация ресурсов для Majiro.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # insert
    p_ins = sub.add_parser("insert", help="Вставка перевода из .md (папка/файл) или .xlsx в .mjres")
    p_ins.add_argument("input", help="Папка с .md файлами (например Owari) или файл .xlsx")
    p_ins.add_argument("-o", "--outdir", default="scenario", help="Папка вывода для .mjres (по умолчанию 'scenario')")

    # extract
    p_ext = sub.add_parser("extract", help="Извлечение .mjres -> .xlsx")
    p_ext.add_argument("files", nargs="+", help="Папка со .mjres или список файлов")
    p_ext.add_argument("-o", "--output", default="output.xlsx", help="Выходной файл .xlsx")

    # md2xlsx
    p_m2x = sub.add_parser("md2xlsx", help="Конвертация Markdown (.md) таблиц в .xlsx")
    p_m2x.add_argument("input", help="Папка с файлами .md")
    p_m2x.add_argument("-o", "--output", default="Owari.xlsx", help="Выходной файл .xlsx")

    args = parser.parse_args()

    if args.command == "insert":
        if args.input.lower().endswith(".xlsx"):
            print(f"Вставка из Excel ({args.input}) -> {args.outdir}/")
            cmd_insert_from_xlsx(args.input, args.outdir)
        else:
            print(f"Вставка из Markdown ({args.input}) -> {args.outdir}/")
            cmd_insert_from_md(args.input, args.outdir)
    elif args.command == "extract":
        cmd_extract_to_xlsx(args.files, args.output)
    elif args.command == "md2xlsx":
        cmd_md2xlsx(args.input, args.output)


if __name__ == "__main__":
    main()