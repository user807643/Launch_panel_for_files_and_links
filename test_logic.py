# -*- coding: utf-8 -*-
"""Проверка логики без открытия окна."""
import importlib.util
import json
import os
import sys
import tempfile

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ЗапускПрограмм.py")
spec = importlib.util.spec_from_file_location("zapusk", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  | " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


# 1. app_dir не указывает во временную папку
d = mod.app_dir()
check("app_dir существует", os.path.isdir(d), d)
check("app_dir не в TEMP", os.path.abspath(tempfile.gettempdir()).lower() not in d.lower(), d)

# 2. merge_config: пустой и битый вход дают рабочий конфиг
cfg = mod.merge_config(None)
check("merge(None) даёт 2 кнопки", len(cfg["buttons"]) == 2, len(cfg["buttons"]))

cfg2 = mod.merge_config({"settings": {"window_width": 800}, "buttons": [{"text": "A"}]})
check("сохранённая настройка читается", cfg2["settings"]["window_width"] == 800)
check("недостающие настройки добираются", cfg2["settings"]["margin_left"] == 80)
check("кнопка из конфига читается", cfg2["buttons"][0]["text"] == "A")

cfg3 = mod.merge_config({"buttons": ["Строка"]})
check("кнопка-строка конвертируется", cfg3["buttons"][0]["text"] == "Строка")

# 3. save/load круговой рейс с кириллицей и пробелами
tmpdir = tempfile.mkdtemp(prefix="zap_test_")
cfg_path = os.path.join(tmpdir, "settings.json")
data = {"settings": dict(mod.DEFAULTS["settings"]),
        "buttons": [{"text": "Кнопка Ё", "label": "ред. 1",
                     "path": r"C:\Program Files\Моя папка\файл тест.txt"}]}
mod.save_config(cfg_path, data)
check("файл конфига создан", os.path.exists(cfg_path))

loaded, note = mod.load_config(cfg_path)
check("кириллица в пути сохранена",
      loaded["buttons"][0]["path"] == data["buttons"][0]["path"],
      loaded["buttons"][0]["path"])
check("загрузка без замечаний", note == "", note)

raw = open(cfg_path, "r", encoding="utf-8").read()
check("кириллица в файле не экранирована", "Моя папка" in raw)

# 4. битый конфиг -> .bak и работоспособность
bad = os.path.join(tmpdir, "bad.json")
open(bad, "w", encoding="utf-8").write("{это не json")
loaded2, note2 = mod.load_config(bad)
check("битый конфиг даёт замечание", note2 != "", note2)
check("битый конфиг отложен в .bak", os.path.exists(bad + ".bak"))
check("после битого конфига 2 кнопки", len(loaded2["buttons"]) == 2)

# 5. can_write_dir на реальной папке
check("can_write_dir(APP_DIR)", mod.can_write_dir(mod.app_dir()) is True)

# 6. resolve_config_path
p, fb = mod.resolve_config_path()
check("конфиг рядом с программой", os.path.dirname(p) == d and fb is False, (p, fb))

# 7. чистка кавычек
class Dummy:
    _clean_path = mod.LaunchApp._clean_path
check("кавычки убираются", Dummy()._clean_path('"C:\\a b\\f.txt"') == r"C:\a b\f.txt")
check("пробелы убираются", Dummy()._clean_path("   C:\\f.exe  ") == r"C:\f.exe")

print()
print("ИТОГ:", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if not fails else "ПРОВАЛЕНО: %d -> %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
