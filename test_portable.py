# -*- coding: utf-8 -*-
"""Проверка переноса папки и кнопки выбора файла «…»."""
import ctypes
import ctypes.wintypes as wt
import json
import os
import shutil
import subprocess
import sys
import time

user32 = ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(2)

SRC_EXE = sys.argv[1]
NEW_FOLDER = os.path.join(os.environ["TEMP"], "Перенесённая папка с пробелами")
GOOD = os.path.join(os.environ["SystemRoot"], "System32", "where.exe")

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  | " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


# --- 1. Переносим папку с программой и её настройками в другое место ------
shutil.rmtree(NEW_FOLDER, ignore_errors=True)
os.makedirs(NEW_FOLDER, exist_ok=True)
shutil.copy2(SRC_EXE, NEW_FOLDER)

# Готовим настройки с заранее заполненным путём и переносим их тоже
cfg = {"settings": {}, "buttons": [
    {"text": "Перенесённая кнопка", "label": "ред. 1", "path": GOOD},
    {"text": "кнопка 2", "label": "ред. 2", "path": ""}]}
cfg_path = os.path.join(NEW_FOLDER, "settings.json")
with open(cfg_path, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, ensure_ascii=False, indent=2)

exe = os.path.join(NEW_FOLDER, "ЗапускПрограмм.exe")
check("папка с кириллицей и пробелами создана", os.path.isdir(NEW_FOLDER), NEW_FOLDER)

proc = subprocess.Popen([exe])
time.sleep(7)
check(".exe запустился из новой папки", proc.poll() is None,
      "код выхода %s" % proc.returncode)
if proc.poll() is not None:
    sys.exit(1)

CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


def find_window(title_part):
    found = []

    def cb(h, l):
        if user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, buf, n + 1)
                if title_part in buf.value:
                    found.append(h)
        return True

    user32.EnumWindows(CB(cb), 0)
    return found


hwnd = 0
for _ in range(30):
    f = find_window("Запуск программ")
    if f:
        hwnd = f[0]
        break
    time.sleep(1)
check("окно открылось после переноса", hwnd != 0, hwnd)


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


r = RECT()
user32.GetClientRect(hwnd, ctypes.byref(r))
pt = wt.POINT(0, 0)
user32.ClientToScreen(hwnd, ctypes.byref(pt))
scale = r.right / 950.0


def click(x_log, y_log, wait=1.5):
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.4)
    user32.SetCursorPos(int(pt.x + x_log * scale), int(pt.y + y_log * scale))
    time.sleep(0.25)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(wait)


# --- 2. Проверяем, что настройки подхватились из перенесённого файла ------
# Кнопка 1 имеет рабочий путь, значит при нажатии кнопка станет зелёной.
GREEN = (60, 179, 113)
gdi32 = ctypes.windll.gdi32


def pixel(x_log, y_log):
    x = int(round(x_log * scale))
    y = int(round(y_log * scale))
    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, r.right, r.bottom)
    gdi32.SelectObject(hdc_mem, hbmp)
    try:
        user32.PrintWindow(hwnd, hdc_mem, 2)
        color = gdi32.GetPixel(hdc_mem, x, y)
    finally:
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
    return color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF


def near(rgb, target, tol=40):
    return all(abs(a - b) <= tol for a, b in zip(rgb, target))


click(231, 257, wait=1.0)
c = pixel(231, 257)
check("кнопка с перенесённым путём запустилась (зелёная)", near(c, GREEN), c)

# --- 3. Кнопка «…» открывает диалог выбора файла -------------------------
dialogs_before = find_window("Выберите файл")
click(911, 257, wait=3.0)          # кнопка «…» первой строки
dialogs_after = find_window("Выберите файл")
check("кнопка «…» открыла диалог выбора файла",
      len(dialogs_after) > len(dialogs_before),
      "было %d, стало %d" % (len(dialogs_before), len(dialogs_after)))

# Закрываем диалог по Escape — программа не должна упасть
user32.SetForegroundWindow(dialogs_after[0]) if dialogs_after else None
time.sleep(0.5)
user32.keybd_event(0x1B, 0, 0, 0)      # Escape down
user32.keybd_event(0x1B, 0, 0x0002, 0)  # Escape up
time.sleep(1.5)
check("после закрытия диалога программа жива", proc.poll() is None,
      "код выхода %s" % proc.returncode)

# --- 4. Настройки всё ещё пишутся в перенесённую папку -------------------
time.sleep(0.5)
saved = json.load(open(cfg_path, encoding="utf-8"))
check("настройки читаются из перенесённой папки",
      saved["buttons"][0]["text"] == "Перенесённая кнопка",
      saved["buttons"][0]["text"])
check("путь сохранён в перенесённую папку, не в исходную",
      saved["buttons"][0]["path"].strip() == GOOD, saved["buttons"][0]["path"])

proc.terminate()
time.sleep(2)
if proc.poll() is None:
    proc.kill()

print()
print("ИТОГ:", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if not fails else "ПРОВАЛЕНО: %d -> %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
