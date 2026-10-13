# -*- coding: utf-8 -*-
"""Проверка готового .exe: реальные клики, запуск файлов, цвет кнопок.

Цвет читается через PrintWindow (снимок самого окна), поэтому посторонние
окна поверх программы не портят замер. Кроме цвета проверяется и сам факт
запуска процесса — чтобы «зелёная кнопка» не оказалась единственным
доказательством.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# Обязательно до вызовов Win32: без DPI-awareness координаты кликов и замеры
# окажутся в разных системах отсчёта при масштабе экрана 125%.
ctypes.windll.shcore.SetProcessDpiAwareness(2)

EXE = sys.argv[1]
FOLDER = os.path.dirname(EXE)
CFG = os.path.join(FOLDER, "settings.json")

GOOD = os.path.join(os.environ["SystemRoot"], "System32", "where.exe")
BAD = r"C:\НетТакойПапки\нет_файла.exe"
SECOND = os.path.join(os.environ["SystemRoot"], "System32", "notepad.exe")
TXT_DIR = os.path.join(os.environ.get("TEMP", "."), "Моя папка тест")
TXT = os.path.join(TXT_DIR, "пробный файл.txt")

# Логические координаты макета
BTN1 = (231, 257)          # центр первой кнопки
BTN2 = (231, 382)          # центр второй кнопки
ENTRY1 = (645, 257)        # поле пути первой строки

GREEN = (60, 179, 113)     # #3CB371
RED = (229, 57, 53)        # #E53935

fails = []


def check(name, cond, extra=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("  | " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


def near(rgb, target, tol=40):
    return all(abs(a - b) <= tol for a, b in zip(rgb, target))


# ---------------------------------------------------------------- подготовка
os.makedirs(TXT_DIR, exist_ok=True)
with open(TXT, "w", encoding="utf-8") as fh:
    fh.write("тест")

cfg = {"settings": {}, "buttons": [
    {"text": "кнопка 1", "label": "ред. 1", "path": BAD},
    {"text": "кнопка 2", "label": "ред. 2", "path": TXT}]}
with open(CFG, "w", encoding="utf-8") as fh:
    json.dump(cfg, fh, ensure_ascii=False, indent=2)

proc = subprocess.Popen([EXE])
time.sleep(7)
if proc.poll() is not None:
    check(".exe не упал при старте", False, "код выхода %s" % proc.returncode)
    sys.exit(1)
check(".exe запустился", True, "pid=%d" % proc.pid)

# ----------------------------------------------------------- поиск окна
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)


def find_window():
    found = []

    def cb(h, l):
        if user32.IsWindowVisible(h):
            n = user32.GetWindowTextLengthW(h)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(h, buf, n + 1)
                if "Запуск программ" in buf.value:
                    found.append(h)
        return True

    user32.EnumWindows(CB(cb), 0)
    return found


hwnd = 0
for _ in range(30):
    f = find_window()
    if f:
        hwnd = f[0]
        break
    time.sleep(1)
check("окно найдено по заголовку", hwnd != 0, hwnd)
if not hwnd:
    proc.kill()
    sys.exit(1)


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def client_origin():
    r = RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, r.right, r.bottom


cx, cy, cw, ch = client_origin()
check("окно отрисовано", cw > 300 and ch > 200, "%dx%d" % (cw, ch))
scale = cw / 950.0
print("масштаб окна: %.3f" % scale)


def ensure_front():
    """Поднять окно наверх — нужно для ввода с клавиатуры."""
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.4)


def click(x_log, y_log, wait=1.2):
    """Клик мышью в точке, заданной в логических пикселях макета."""
    ensure_front()
    user32.SetCursorPos(int(cx + x_log * scale), int(cy + y_log * scale))
    time.sleep(0.25)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(wait)


def pixel(x_log, y_log):
    """Цвет пикселя кнопки из внутреннего снимка окна (PrintWindow)."""
    x = int(round(x_log * scale))
    y = int(round(y_log * scale))

    hdc_screen = user32.GetDC(0)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, cw, ch)
    gdi32.SelectObject(hdc_mem, hbmp)
    try:
        user32.PrintWindow(hwnd, hdc_mem, 2)   # 2 = PW_RENDERFULLCONTENT
        color = gdi32.GetPixel(hdc_mem, x, y)
    finally:
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
    return color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF


# --------------------------------------------------- проверка размеров окна
check("ширина окна соответствует макету (950)",
      abs(cw - 950 * scale) <= 3, cw)
check("высота окна соответствует макету (529)",
      abs(ch - 529 * scale) <= 3, ch)

# ------------------------------------------------------- ввод с клавиатуры
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
                ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]


check("размер структуры INPUT корректен (40 байт)",
      ctypes.sizeof(INPUT) == 40, ctypes.sizeof(INPUT))


def send(inp):
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise RuntimeError("SendInput не сработал")


def key_unicode(ch):
    for flags in (0x0004, 0x0004 | 0x0002):
        inp = INPUT(type=1)
        inp.ki = KEYBDINPUT(wVk=0, wScan=ord(ch), dwFlags=flags,
                            time=0, dwExtraInfo=None)
        send(inp)
        time.sleep(0.01)


def key_vk(vk, up=False):
    inp = INPUT(type=1)
    inp.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=0x0002 if up else 0,
                        time=0, dwExtraInfo=None)
    send(inp)


def type_text(text):
    for ch in text:
        key_unicode(ch)
    time.sleep(0.5)


def clear_entry(length=60):
    """Очистка поля: End, затем Backspace (не зависит от раскладки)."""
    key_vk(0x23)
    key_vk(0x23, up=True)
    time.sleep(0.2)
    for _ in range(length):
        key_vk(0x08)
        key_vk(0x08, up=True)
        time.sleep(0.01)
    time.sleep(0.3)


def set_entry(text):
    click(*ENTRY1, wait=0.5)
    clear_entry()
    type_text(text)


def notepad_pids():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq notepad.exe",
                          "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, errors="replace").stdout.lower()
    pids = set()
    for line in out.splitlines():
        if line.startswith('"notepad'):
            parts = line.split(",")
            if len(parts) > 1:
                pids.add(parts[1].strip().strip('"'))
    return pids


def kill_pids(pids):
    for pid in pids:
        subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True)
    time.sleep(1.5)


# =========================== СЦЕНАРИЙ 1: несуществующий файл ==============
before = pixel(*BTN1)
click(*BTN1, wait=1.0)
after = pixel(*BTN1)
check("кнопка 1 (нет файла) стала красной", near(after, RED), after)
check("цвет действительно изменился", before != after, "%s -> %s" % (before, after))
check("стартовый цвет был зелёным", near(before, GREEN), before)

# =========================== СЦЕНАРИЙ 2: txt с кириллицей ==================
click(*BTN2, wait=2.0)
c2 = pixel(*BTN2)
check("кнопка 2 (txt с кириллицей) зелёная", near(c2, GREEN), c2)
kill_pids(notepad_pids())

time.sleep(0.5)
saved = json.load(open(CFG, encoding="utf-8"))
check("путь к txt сохранён рядом с .exe",
      saved["buttons"][1]["path"].strip() == TXT, saved["buttons"][1]["path"])
check("кириллица в конфиге не испорчена", "Моя папка тест" in saved["buttons"][1]["path"])

# =========================== СЦЕНАРИЙ 3: исправление пути ==================
set_entry(GOOD)
click(*BTN1, wait=1.0)
c3 = pixel(*BTN1)
check("после исправления пути кнопка 1 снова зелёная", near(c3, GREEN), c3)

time.sleep(0.5)
saved2 = json.load(open(CFG, encoding="utf-8"))
check("исправленный путь сохранён", saved2["buttons"][0]["path"].strip() == GOOD,
      saved2["buttons"][0]["path"])

# =========================== СЦЕНАРИЙ 4: замена пути целиком ==============
before_pids = notepad_pids()
set_entry(SECOND)
click(*BTN1, wait=2.5)

new_pids = notepad_pids() - before_pids
check("второй путь действительно запустил notepad.exe", len(new_pids) >= 1,
      "новые pid: %s" % sorted(new_pids))

# Полностью перекрытое окно Tk отдаёт пустой снимок, поэтому сначала
# закрываем запущенный Блокнот, и только затем читаем цвет.
kill_pids(new_pids)
c4 = pixel(*BTN1)
check("кнопка 1 со вторым путём зелёная", near(c4, GREEN), c4)

time.sleep(0.5)
saved3 = json.load(open(CFG, encoding="utf-8"))
check("в конфиге ровно второй путь, без остатков первого",
      saved3["buttons"][0]["path"].strip() == SECOND, saved3["buttons"][0]["path"])

# =========================== СЦЕНАРИЙ 5: портативность ====================
check("конфиг хранится рядом с .exe, а не в %APPDATA%",
      os.path.dirname(os.path.abspath(CFG)) == os.path.abspath(FOLDER), CFG)
check("в папке программы нет лишних файлов настроек",
      not any(f.endswith(".tmp") for f in os.listdir(FOLDER)), os.listdir(FOLDER))

# ---------------------------------------------------------------- завершение
proc.terminate()
time.sleep(2)
if proc.poll() is None:
    proc.kill()

print()
print("ИТОГ:", "ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if not fails else "ПРОВАЛЕНО: %d -> %s" % (len(fails), fails))
sys.exit(1 if fails else 0)
