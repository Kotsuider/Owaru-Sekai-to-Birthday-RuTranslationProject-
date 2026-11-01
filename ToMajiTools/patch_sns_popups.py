#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Патч для scenario/sns.mjil:
1. Восстановление аватаров при переведённых именах персонажей (Мисаки-чи, Нару, Мика-тан, Кито, ИРИ и т.д.)
2. Перевод городских всплывающих сообщений и системных уведомлений в плашках SNS/TEXI.
"""

import sys
import os
import re

AVATAR_NAME_MAP = {
    "Нару": "ナル",
    "Мика-тан": "ミカたん",
    "Мисаки-чи": "みさきち",
    "Кито": "木冬",
    "ИРИ": "ＩＬＩ",
    "Администрация texi": "ｔｅｘｉ管理局",
    "Администрация TEXI": "ｔｅｘｉ管理局",
}

def patch_sns_mjil(sns_path: str):
    if not os.path.exists(sns_path):
        print(f"Warning: {sns_path} not found.")
        return False

    with open(sns_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Патчим func $a34a2c6f для обратного маппинга русских имён в японские перед загрузкой аватара
    # Оригинальный код в func $a34a2c6f:
    # func $a34a2c6f(string) {
    #  entry:
    #   line          #107
    #   argcheck      [string]
    #   alloca        []
    #   line          #108
    #   ld            local string $de39f0d4 -2
    #   ldstr         "ナル"
    
    mapping_code = ""
    for ru_name, jp_name in AVATAR_NAME_MAP.items():
        mapping_code += f"""  ld            local string $de39f0d4 -2
  ldstr         "{ru_name}"
  ceq.s        
  brfalse       @block_skip_map_{abs(hash(ru_name))}
  ldstr         "{jp_name}"
  st.s          local string $de39f0d4 -2
  pop          
 block_skip_map_{abs(hash(ru_name))}:
"""

    func_entry_target = """func $a34a2c6f(string) {
 entry:
  line          #107
  argcheck      [string]
  alloca        []
  line          #108"""

    if func_entry_target in content:
        content = content.replace(func_entry_target, func_entry_target + "\n" + mapping_code, 1)
        print("Patched func $a34a2c6f avatar mapping.")
    else:
        print("Warning: func $a34a2c6f entry pattern not found.")

    # 2. Патчим городские уведомления и всплывающие плашки
    # В func $3adb47f7 и $767bb922:
    # " さんよりメッセージが届きました" -> ": получено новое сообщение"
    # " さんのツブヤキが更新されました" -> ": опубликована новая заметка"
    # "ｔｅｘｉ管理局" -> "Администрация TEXI" (для отображения заголовка плашки)

    # Замена текста уведомлений о входящих
    old_msg1 = 'ldstr         " さんよりメッセージが届きました"'
    new_msg1 = 'ldstr         ": получено новое сообщение"'
    old_msg2 = 'ldstr         " さんのツブヤキが更新されました"'
    new_msg2 = 'ldstr         ": опубликована новая заметка"'

    count1 = content.count(old_msg1)
    content = content.replace(old_msg1, new_msg1)

    count2 = content.count(old_msg2)
    content = content.replace(old_msg2, new_msg2)

    print(f"Replaced {count1} message notifications, {count2} tweet notifications.")

    # Заменяем отображаемый заголовок плашки "ｔｅｘｉ管理局" на "Администрация TEXI"
    # В func $3adb47f7:
    # line          #2263
    # ldc.i         12
    # ldc.i         48
    # ldstr         "ｔｅｘｉ管理局"
    # syscallp      $fontout (3)
    #
    # И в func $767bb922:
    # line          #2419
    # ldc.i         12
    # ldc.i         48
    # ldstr         "ｔｅｘｉ管理局"
    # syscallp      $fontout (3)

    target_disp1 = """  line          #2263
  ldc.i         12
  ldc.i         48
  ldstr         "ｔｅｘｉ管理局"
  syscallp      $fontout (3)"""

    repl_disp1 = """  line          #2263
  ldc.i         12
  ldc.i         48
  ldstr         "Администрация TEXI"
  syscallp      $fontout (3)"""

    target_disp2 = """  line          #2419
  ldc.i         12
  ldc.i         48
  ldstr         "ｔｅｘｉ管理局"
  syscallp      $fontout (3)"""

    repl_disp2 = """  line          #2419
  ldc.i         12
  ldc.i         48
  ldstr         "Администрация TEXI"
  syscallp      $fontout (3)"""

    if target_disp1 in content:
        content = content.replace(target_disp1, repl_disp1)
        print("Patched display header 1 (Администрация TEXI).")
    else:
        print("Warning: target_disp1 not found.")

    if target_disp2 in content:
        content = content.replace(target_disp2, repl_disp2)
        print("Patched display header 2 (Администрация TEXI).")
    else:
        print("Warning: target_disp2 not found.")

    # 3. Фикс обрезания и отступов в описаниях профилей (.profile):
    # В функциях $841a4675 и $8f28eb6f:
    # Исходно: ldc.i 99 / ldc.i 5 / ld local string $b134b5f0 4 / syscall $strmid$ (3)
    # Движок безусловно отрезал 5 символов от КАЖДОЙ строки блока 自己紹介.
    # Заменяем на условный срез: если строка начинается с '自己紹介：', отрезаем 5 символов,
    # иначе оставляем строку без изменений (срез 0 символов).
    target_strmid1 = """ block_69b2:
  line          #1039
  ldc.i         99
  ldc.i         5
  ld            local string $b134b5f0 4
  syscall       $strmid$ (3)
  st.s          local string $b134b5f0 4
  pop          """

    repl_strmid1 = """ block_69b2:
  line          #1039
  ldstr         "自己紹介："
  ld            local string $b134b5f0 4
  syscall       $strstr (2)
  ldc.i         0
  ceq.i        
  brfalse       @block_skip_strmid_69b2
  ldc.i         99
  ldc.i         5
  ld            local string $b134b5f0 4
  syscall       $strmid$ (3)
  st.s          local string $b134b5f0 4
  pop          
 block_skip_strmid_69b2:"""

    target_strmid2 = """ block_72f0:
  line          #1128
  ldc.i         99
  ldc.i         5
  ld            local string $b134b5f0 4
  syscall       $strmid$ (3)
  st.s          local string $b134b5f0 4
  pop          """

    repl_strmid2 = """ block_72f0:
  line          #1128
  ldstr         "自己紹介："
  ld            local string $b134b5f0 4
  syscall       $strstr (2)
  ldc.i         0
  ceq.i        
  brfalse       @block_skip_strmid_72f0
  ldc.i         99
  ldc.i         5
  ld            local string $b134b5f0 4
  syscall       $strmid$ (3)
  st.s          local string $b134b5f0 4
  pop          
 block_skip_strmid_72f0:"""

    if target_strmid1 in content:
        content = content.replace(target_strmid1, repl_strmid1, 1)
        print("Patched profile intro strmid in func $841a4675.")
    else:
        print("Warning: target_strmid1 not found in content.")

    if target_strmid2 in content:
        content = content.replace(target_strmid2, repl_strmid2, 1)
        print("Patched profile intro strmid in func $8f28eb6f.")
    else:
        print("Warning: target_strmid2 not found in content.")

    # 4. Перевод захардкоженных диалоговых окон в SNS/TEXI
    # Диалог подтверждения установки дня рождения (Скриншот 3)
    # line #2982: ldstr "誕生日を" + month + "月" + day + "日に設定しますか？"
    old_bday_dialog = """  line          #2982
  ldstr         "誕生日を"
  ld            savefile int $7af3da5e 
  call          $e55f0668 (1)
  add.s        
  ldstr         "月"
  add.s        
  ld            savefile int $c1dbe37a 
  call          $e55f0668 (1)
  add.s        
  ldstr         "日に設定しますか？"
  add.s        
  call          $$askyesno@MSG_BOX (1) ; $askyesno@MSG_BOX"""

    new_bday_dialog = """  line          #2982
  ldstr         "Установить день рождения на "
  ld            savefile int $7af3da5e 
  call          $e55f0668 (1)
  add.s        
  ldstr         " мес. "
  add.s        
  ld            savefile int $c1dbe37a 
  call          $e55f0668 (1)
  add.s        
  ldstr         " дн.?"
  add.s        
  call          $$askyesno@MSG_BOX (1) ; $askyesno@MSG_BOX"""

    if old_bday_dialog in content:
        content = content.replace(old_bday_dialog, new_bday_dialog, 1)
        print("Patched birthday confirmation dialog (誕生日を...日に設定しますか？ -> Установить день рождения на...).")
    else:
        print("Warning: old_bday_dialog pattern not found.")

    # Ошибка: день рождения не задан
    old_no_bday = 'ldstr         "誕生日が設定されていません"'
    new_no_bday = 'ldstr         "День рождения не выбран"'
    if old_no_bday in content:
        content = content.replace(old_no_bday, new_no_bday)
        print("Patched no-birthday dialog.")

    # Добавление в список друзей: Name + "を友人リストに登録した"
    old_add_friend = 'ldstr         "を友人リストに登録した"'
    new_add_friend = 'ldstr         " добавлен(а) в список друзей"'
    if old_add_friend in content:
        content = content.replace(old_add_friend, new_add_friend)
        print("Patched friend registration dialog.")

    # Ошибка подключения к сети: "現在接続できません"
    old_no_conn = 'ldstr         "現在接続できません"'
    new_no_conn = 'ldstr         "В данный момент подключение невозможно"'
    if old_no_conn in content:
        content = content.replace(old_no_conn, new_no_conn)
        print("Patched connection error dialog.")

    # Открытие URL в браузере: "URLをブラウザで開きますか？"
    old_open_url = 'ldstr         "URLをブラウザで開きますか？"'
    new_open_url = 'ldstr         "Открыть ссылку в браузере?"'
    if old_open_url in content:
        content = content.replace(old_open_url, new_open_url)
        print("Patched open browser URL dialog.")

    # Количество друзей в сайдбаре: "フレンド(" + num + "人)" -> "Друзья (" + num + ")"
    content = content.replace('ldstr         "フレンド("', 'ldstr         "Друзья ("')
    content = content.replace('ldstr         "人)"', 'ldstr         ")"')
    print("Patched friends counter label in sidebar.")

    with open(sns_path, "w", encoding="utf-8") as f:
        f.write(content)

    return True

if __name__ == "__main__":
    scenario_dir = sys.argv[1] if len(sys.argv) > 1 else "scenario"
    sns_file = os.path.join(scenario_dir, "sns.mjil")
    patch_sns_mjil(sns_file)
