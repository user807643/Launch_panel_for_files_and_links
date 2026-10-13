# -*- coding: utf-8 -*-
"""Проверка поведения окна: запуск файлов и смена цвета кнопок."""
import importlib.util
import os
import sys
import tempfile
import time

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ЗапускПрограмм.py")
spec = importlib.util.spec_from_file_location("zapusk", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  | " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


app = mod.LaunchApp()
app.update()

# --- геометрия окна -------------------------------------------------------
w = app.winfo_width()
h = app.winfo_height()
check("ширина окна как в макете (950)", abs(w - app.px(950)) <= 2, w)
check("высота окна как в макете (529)", abs(h - app.px(529)) <= 2, h)
check("кнопок две", len(app.buttons) == 2, len(app.buttons))

# --- стартовый цвет -------------------------------------------------------
for i, btn in enumerate(app.buttons):
    check("кнопка %d стартует зелёной" % (i + 1), btn.cget("bg") == mod.COLOR_OK, btn.cget("bg"))

# --- 1. существующий .exe -------------------------------------------------
victim = os.path.join(os.environ["SystemRoot"], "System32", "where.exe")
check("тестовый exe существует", os.path.exists(victim), victim)
app.path_vars[0].set(victim)
app.launch(0)
app.update()
check("exe: кнопка зелёная", app.buttons[0].cget("bg") == mod.COLOR_OK, app.buttons[0].cget("bg"))
check("exe: статус об успехе", "запущено" in app.status_text.get(), app.status_text.get())

# --- 2. несуществующий путь ----------------------------------------------
missing = r"C:\НетТакойПапки\нет_файла.exe"
app.path_vars[0].set(missing)
app.launch(0)
app.update()
check("нет файла: кнопка красная",
      app.buttons[0].cget("bg") == mod.COLOR_FAIL, app.buttons[0].cget("bg"))
check("нет файла: статус о причине",
      "не найден" in app.status_text.get(), app.status_text.get())

# --- 3. возврат в зелёный после исправления ------------------------------
app.path_vars[0].set(victim)
app.launch(0)
app.update()
check("после исправления снова зелёная",
      app.buttons[0].cget("bg") == mod.COLOR_OK, app.buttons[0].cget("bg"))

# --- 4. пустой путь -------------------------------------------------------
app.path_vars[1].set("")
app.launch(1)
app.update()
check("пустой путь: кнопка красная",
      app.buttons[1].cget("bg") == mod.COLOR_FAIL, app.buttons[1].cget("bg"))
check("пустой путь: понятное сообщение",
      "путь не указан" in app.status_text.get(), app.status_text.get())

# --- 5. путь с пробелами и кириллицей, .txt ------------------------------
base = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "Моя папка тест")
os.makedirs(base, exist_ok=True)
txt = os.path.join(base, "пробный файл.txt")
with open(txt, "w", encoding="utf-8") as fh:
    fh.write("тест")

app.path_vars[1].set(txt)
app.launch(1)
app.update()
check("txt с кириллицей: запущено",
      "запущено" in app.status_text.get(), app.status_text.get())
check("txt с кириллицей: кнопка зелёная",
      app.buttons[1].cget("bg") == mod.COLOR_OK, app.buttons[1].cget("bg"))

# --- 6. путь в кавычках (как при «Копировать как путь») ------------------
app.path_vars[1].set('"%s"' % victim)
app.launch(1)
app.update()
check("путь в кавычках распознан",
      "запущено" in app.status_text.get(), app.status_text.get())

# --- 7. сохранение настроек ----------------------------------------------
ok = app.save(force=True)
app.update()
check("настройки сохранены", ok is True)
check("конфиг лежит рядом с программой",
      os.path.dirname(app.config_path) == mod.app_dir() and not app.used_fallback,
      app.config_path)

import json
saved = json.load(open(app.config_path, "r", encoding="utf-8"))
check("в конфиге сохранён путь с кириллицей",
      saved["buttons"][1]["path"].strip('"') == victim, saved["buttons"][1]["path"])
check("в конфиге структура settings+buttons",
      "settings" in saved and isinstance(saved["buttons"], list))

app.destroy()
app.update()

print()
print("ИТОГ:", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if not fails else "ПРОВАЛЕНО: %d -> %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
