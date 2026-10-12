# -*- coding: utf-8 -*-
"""Проверка Ctrl+A в полях и отката конфига в %APPDATA%."""
import importlib.util
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


# --- 1. Ctrl+A выделяет весь текст в поле пути ----------------------------
app = mod.LaunchApp()
app.update()

# находим поле ввода (это widget класса Entry)
entries = [w for w in app.winfo_children() if w.winfo_class() == "Entry"]
check("поля путей созданы", len(entries) == 2, len(entries))

if entries:
    e = entries[0]
    path_text = r"C:\Программы\тестовый файл.exe"
    e.delete(0, "end")
    e.insert(0, path_text)
    e.focus_force()
    app.update()

    # selection_get() требует PRIMARY selection, которой нет без настоящего
    # фокуса окна, поэтому проверяем диапазон выделения в самом виджете
    # и отдельно — что привязка <Control-a> вообще зарегистрирована.
    has_binding = bool(e.bind("<Control-KeyPress>"))
    check("привязка <Control-KeyPress> зарегистрирована", has_binding, e.bind("<Control-KeyPress>"))

    # Проверка горячих клавиш для русской раскладки: Ctrl приходит символом
    # \x01, поэтому обработчик вызывается напрямую с поддельным событием.
    class Ev:
        pass

    def fire(widget, char):
        ev = Ev()
        ev.widget = widget
        ev.char = char
        return mod.LaunchApp._on_entry_hotkey(ev)

    e.selection_clear()
    app.update()
    res = fire(e, "\x01")
    app.update()
    try:
        direct = (e.index("sel.first"), e.index("sel.last"))
    except Exception as exc:
        direct = "выделения нет: %s" % exc
    check("Ctrl+A (\x01) выделяет всё", direct == (0, len(path_text)), direct)
    check("обработчик возвращает 'break'", res == "break", res)

    # Ctrl+C копирует выделенное в буфер
    e.clipboard_clear()
    fire(e, "\x03")
    app.update()
    try:
        copied = e.clipboard_get()
    except Exception as exc:
        copied = "буфер пуст: %s" % exc
    check("Ctrl+C (\x03) копирует выделенное", copied == path_text, copied)

    # Ctrl+V вставляет путь и снимает кавычки + перевод строки
    wanted = r"C:\Проверка вставки\файл тест.txt"
    e.delete(0, "end")
    e.clipboard_clear()
    e.clipboard_append('"' + wanted + '"\r\n')
    fire(e, "\x16")
    app.update()
    check("Ctrl+V (\x16) вставляет путь без кавычек и переводов строк",
          e.get() == wanted, e.get())

    # Ctrl+X вырезает
    e.delete(0, "end")
    e.insert(0, "ВЫРЕЗАТЬ")
    e.select_range(0, "end")
    fire(e, "\x18")
    app.update()
    check("Ctrl+X (\x18) вырезает выделенное", e.get() == "", repr(e.get()))

# --- 2. Полей ввода столько же, сколько кнопок ---------------------------
check("кнопок и полей поровну", len(app.buttons) == len(entries))

# --- 3. Вертикальные подписи нарисованы с поворотом ----------------------
canvases = [w for w in app.winfo_children() if w.winfo_class() == "Canvas"]
check("подписи на Canvas (2 шт.)", len(canvases) == 2, len(canvases))
if canvases:
    items = canvases[0].find_all()
    angles = [canvases[0].itemcget(i, "angle") for i in items]
    check("угол поворота подписи = 90",
          all(abs(float(a) - 90.0) < 0.01 for a in angles), angles)
    texts = [canvases[0].itemcget(i, "text") for i in items]
    check("текст подписи «ред. 1»", "ред. 1" in texts, texts)

# --- 4. Число кнопок берётся из конфига (расширяемость) ------------------
import json
extra_cfg = os.path.join(tempfile.mkdtemp(prefix="zap_exp_"), "settings.json")
mod.save_config(extra_cfg, {
    "settings": dict(mod.DEFAULTS["settings"]),
    "buttons": [{"text": "к%d" % i, "label": "ред. %d" % i, "path": ""} for i in range(1, 6)],
})
loaded, _ = mod.load_config(extra_cfg)
check("конфиг с 5 кнопками читается", len(loaded["buttons"]) == 5, len(loaded["buttons"]))

app.destroy()
app.update()

# --- 5. Откат в %APPDATA%, когда папка программы недоступна --------------
real_app_dir = mod.app_dir
real_can_write = mod.can_write_dir

mod.can_write_dir = lambda path: False          # имитируем запрет записи
mod.app_dir = lambda: os.path.join(tempfile.gettempdir(), "Несуществующий_Защищённый_Диск")
path, used_fallback = mod.resolve_config_path()
mod.can_write_dir = real_can_write
mod.app_dir = real_app_dir

check("откат сработал", used_fallback is True, used_fallback)
check("конфиг уехал в %APPDATA%",
      os.path.dirname(path).lower() == mod.fallback_dir().lower(), path)

# сохранение в откатную папку реально работает
try:
    mod.save_config(path, {"settings": {}, "buttons": [{"text": "T", "label": "L", "path": "P"}]})
    back, _ = mod.load_config(path)
    check("в %APPDATA% конфиг пишется и читается",
          back["buttons"][0]["text"] == "T", back["buttons"][0])
except OSError as exc:
    check("в %APPDATA% конфиг пишется и читается", False, exc)

print()
print("ИТОГ:", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if not fails else "ПРОВАЛЕНО: %d -> %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
