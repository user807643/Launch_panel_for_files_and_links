import json
import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog


APP_TITLE = "Запуск панели"
CONFIG_NAME = "settings.json"


COLOR_OK = "#3CB371"
COLOR_FAIL = "#E53935"
COLOR_TEXT = "#FFFFFF"
COLOR_BG = "#FFFFFF"
COLOR_STATUS_OK = "#1B7F4B"
COLOR_STATUS_FAIL = "#C62828"
COLOR_STATUS_NEUTRAL = "#444444"

FILE_EXTENSIONS = {
    "exe", "bat", "cmd", "lnk", "msi", "dll", "txt", "pdf", "doc", "docx",
    "xls", "xlsx", "ppt", "pptx", "md", "py", "json", "ini", "log", "zip",
    "rar", "7z", "jpg", "jpeg", "png", "bmp", "gif", "mp3", "mp4", "avi",
}


DEFAULTS = {
    "settings": {
        "title": "Запуск панели",
        "window_width": 950,
        "window_height": 0,
        "window_maximized": False,
        "button_width": 302,
        "button_height": 115,
        "row_pitch": 125,
        "first_row_y": 200,
        "margin_left": 80,
        "gap_button_label": 8,
        "label_width": 40,
        "gap_label_entry": 15,
        "margin_right": 25,
        "browse_width": 44,
        "browse_gap": 10,
        "font_family": "Segoe UI",
        "font_title": 30,
        "font_button": 20,
        "font_label": 17,
        "font_entry": 16,
        "font_status": 14,
        "min_height": 529,
        "bottom_space": 40,
    },
    "buttons": [
        {"text": "кнопка 1", "label": "ред. 1", "path": ""},
        {"text": "кнопка 2", "label": "ред. 2", "path": ""},
    ],
}


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def fallback_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_TITLE)


def can_write_dir(path):
    probe = os.path.join(path, ".write_test.tmp")
    try:
        os.makedirs(path, exist_ok=True)
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("x")
        os.remove(probe)
        return True
    except OSError:
        try:
            if os.path.exists(probe):
                os.remove(probe)
        except OSError:
            pass
        return False


def resolve_config_path():
    primary = os.path.join(app_dir(), CONFIG_NAME)
    if os.path.exists(primary) or can_write_dir(app_dir()):
        return primary, False
    fb_dir = fallback_dir()
    try:
        os.makedirs(fb_dir, exist_ok=True)
    except OSError:
        pass
    return os.path.join(fb_dir, CONFIG_NAME), True


def merge_config(data):
    cfg = {"settings": dict(DEFAULTS["settings"]), "buttons": []}
    if isinstance(data, dict):
        loaded = data.get("settings")
        if isinstance(loaded, dict):
            for key, value in loaded.items():
                cfg["settings"][key] = value
        buttons = data.get("buttons")
        if isinstance(buttons, list):
            for item in buttons:
                if isinstance(item, dict):
                    button = {
                        "text": str(item.get("text", "")),
                        "label": str(item.get("label", "")),
                        "path": str(item.get("path", "")),
                    }
                    for key in ("x", "y"):
                        value = item.get(key)
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            button[key] = float(value)
                    cfg["buttons"].append(button)
                elif isinstance(item, str):
                    cfg["buttons"].append({"text": item, "label": "", "path": ""})
    if not cfg["buttons"]:
        cfg["buttons"] = [dict(b) for b in DEFAULTS["buttons"]]
    return cfg


def load_config(path):
    note = ""
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return merge_config(json.load(fh)), note
        except (OSError, ValueError) as exc:
            note = "Конфиг повреждён (%s), взяты настройки по умолчанию." % exc
            try:
                os.replace(path, path + ".bak")
                note += " Старый файл сохранён как settings.json.bak."
            except OSError:
                pass
    return merge_config(None), note


def save_config(path, cfg):
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    tmp = os.path.join(folder, CONFIG_NAME + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def dpi_scale():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi and dpi > 0:
            return dpi / 96.0
    except Exception:
        pass
    return 1.0


class LaunchApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.scale = dpi_scale()
        self.config_path, self.used_fallback = resolve_config_path()
        self.cfg, self.load_note = load_config(self.config_path)
        self.s = self.cfg["settings"]

        self.buttons = []
        self.path_vars = []
        self.status_text = tk.StringVar(value="")

        self.menu = None
        self.editor = None
        self.edit_index = None
        self.edit_mode = None
        self.hint = None
        self.hint_job = None

        self.positions = []
        self.drag = None
        self.move_index = None
        self.fullscreen = False
        self.normal_size = None

        self._build_window()
        self._build_rows()
        self._build_status()
        self._bind_drag()
        self._bind_window()
        self._restore_maximized()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.load_note:
            self.set_status(self.load_note, COLOR_STATUS_FAIL)
        elif self.used_fallback:
            self.set_status(
                "Папка программы недоступна для записи — настройки сохраняются в %APPDATA%.",
                COLOR_STATUS_NEUTRAL,
            )
        else:
            self.set_status(
                "Колесо — перемещение кнопки, F11 — весь экран, правый клик — путь или ссылка, запуск.",
                COLOR_STATUS_NEUTRAL,
            )

        if not os.path.exists(self.config_path):
            self.save()

    def px(self, value):
        return int(round(float(value) * self.scale))

    def font(self, key):
        return (self.s["font_family"], -self.px(self.s[key]))

    def _build_window(self):
        self.title(self.s["title"] or APP_TITLE)
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)
        rows = len(self.cfg["buttons"])
        height = self.px(self.s.get("window_height") or 0) or self._window_height(rows)
        self.geometry("%dx%d" % (self.px(self.s["window_width"]), height))
        self.minsize(self.px(360), self.px(260))
        self.normal_size = (self.px(self.s["window_width"]), height)

    def _bind_window(self):
        self.bind("<Configure>", self._on_configure)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Escape>", self._on_escape)

    def _restore_maximized(self):
        if not self.s.get("window_maximized"):
            return
        try:
            self.state("zoomed")
        except tk.TclError:
            pass

    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self.winfo_width() <= 1 or not self.positions:
            return
        self._clamp_all()
        self._fit_status()
        if not self.fullscreen and self.state() == "normal":
            self.normal_size = (event.width, event.height)

    def _fit_status(self):
        label = getattr(self, "status_label", None)
        if label is None:
            return
        width = (self.winfo_width() - self.px(self.s["margin_left"])
                 - self.px(self.s["margin_right"]))
        label.place_configure(width=max(1, width))

    def _clamp_all(self):
        for index, button in enumerate(self.buttons):
            x, y = self.positions[index]
            cx, cy = self._clamp_position(button, x, y)
            if (cx, cy) != (x, y):
                button.place_configure(x=cx, y=cy)
                self.positions[index] = [cx, cy]

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        try:
            self.attributes("-fullscreen", self.fullscreen)
        except tk.TclError:
            self.fullscreen = False
            return "break"
        if self.fullscreen:
            self.set_status("Полный экран: F11 или Esc — вернуться в окно.",
                            COLOR_STATUS_NEUTRAL)
        else:
            self.set_status("Обычное окно: F11 — во весь экран.", COLOR_STATUS_NEUTRAL)
        return "break"

    def _on_escape(self, event=None):
        if self.fullscreen:
            self.toggle_fullscreen()
            return "break"
        return None

    def _remember_window(self):
        if self.fullscreen:
            return
        try:
            state = self.state()
        except tk.TclError:
            return
        size = (self.winfo_width(), self.winfo_height())
        if state != "normal" and self.normal_size:
            size = self.normal_size
        if size[0] > 1 and size[1] > 1:
            self.s["window_width"] = int(round(size[0] / self.scale))
            self.s["window_height"] = int(round(size[1] / self.scale))
        self.s["window_maximized"] = (state == "zoomed")

    def _window_height(self, rows):
        needed = self.s["first_row_y"] + rows * self.s["row_pitch"] + self.s["bottom_space"]
        return self.px(max(self.s["min_height"], needed))

    def _build_rows(self):
        btn_w = self.px(self.s["button_width"])
        btn_h = self.px(self.s["button_height"])
        pitch = self.px(self.s["row_pitch"])
        first_y = self.px(self.s["first_row_y"])
        left = self.px(self.s["margin_left"])

        for index, spec in enumerate(self.cfg["buttons"]):
            saved = self._saved_position(spec)
            if saved is None:
                x, y = left, first_y + index * pitch
            else:
                x, y = self.px(saved[0]), self.px(saved[1])

            button = tk.Button(
                self,
                text=spec.get("text") or ("кнопка %d" % (index + 1)),
                font=self.font("font_button"),
                bg=COLOR_OK,
                fg=COLOR_TEXT,
                activebackground=COLOR_OK,
                activeforeground=COLOR_TEXT,
                relief="flat",
                borderwidth=0,
                highlightthickness=0,
                cursor="hand2",
                wraplength=btn_w - self.px(24),
                justify="center",
                command=lambda i=index: self.launch(i),
            )
            button.place(x=x, y=y, width=btn_w, height=btn_h)
            button.bind("<Button-3>", lambda event, i=index: self.popup_menu(event, i))
            button.bind("<Button-2>", lambda event, i=index: self.begin_drag(event, i))
            button.bind("<Enter>", lambda event, i=index: self.schedule_hint(i))
            button.bind("<Leave>", lambda event: self.hide_hint())

            self.buttons.append(button)
            self.positions.append([x, y])
            self.path_vars.append(tk.StringVar(value=spec.get("path", "")))

    def _build_status(self):
        self.status_label = tk.Label(
            self, textvariable=self.status_text, font=self.font("font_status"),
            bg=COLOR_BG, fg=COLOR_STATUS_NEUTRAL, anchor="w", justify="left",
        )
        self.status_label.place(
            x=self.px(self.s["margin_left"]), rely=1.0, y=-self.px(10),
            width=self.px(self.s["window_width"] - self.s["margin_left"] - self.s["margin_right"]),
            anchor="sw")

    def _menu(self):
        if self.menu is None:
            self.menu = tk.Menu(
                self, tearoff=0, font=self.font("font_entry"),
                bg="#FFFFFF", fg="#000000", activebackground=COLOR_OK,
                activeforeground="#FFFFFF", bd=1,
            )
        return self.menu

    def caption(self, index):
        return self.buttons[index].cget("text")

    def popup_menu(self, event, index):
        self.hide_hint()
        self.exit_move_mode()
        self.finish_edit(commit=True)
        menu = self._menu()
        self.fill_menu(menu, index)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def fill_menu(self, menu, index):
        menu.delete(0, "end")
        menu.add_command(label=self.caption(index), state="disabled")
        menu.add_separator()
        menu.add_command(label="Изменить путь…", command=lambda: self.edit_path(index))
        menu.add_command(label="Обзор файла…", command=lambda: self.choose_file(index))
        menu.add_command(label="Переименовать…", command=lambda: self.edit_name(index))
        menu.add_command(label="Переместить", command=lambda: self.enter_move_mode(index))
        menu.add_separator()
        menu.add_command(label="Скопировать путь", command=lambda: self.copy_path(index))
        menu.add_command(label="Очистить путь", command=lambda: self.clear_path(index))
        menu.add_separator()
        menu.add_command(label="Запустить", command=lambda: self.launch(index))

    def edit_path(self, index):
        self.begin_edit(index, "path", self.path_vars[index].get())

    def edit_name(self, index):
        self.begin_edit(index, "name", self.caption(index))

    def begin_edit(self, index, mode, initial):
        self.finish_edit(commit=True)
        button = self.buttons[index]
        info = button.place_info()
        x = int(float(info.get("x") or 0))
        y = int(float(info.get("y") or 0))
        width = int(float(info.get("width") or 0)) or button.winfo_width()
        height = int(float(info.get("height") or 0)) or button.winfo_height()

        editor = tk.Entry(
            self,
            font=self.font("font_button" if mode == "name" else "font_entry"),
            bg="#FFFFFF", fg="#000000",
            relief="flat", borderwidth=0,
            highlightthickness=max(1, self.px(3)),
            highlightbackground=COLOR_OK, highlightcolor=COLOR_OK,
            insertwidth=max(1, self.px(1)),
            justify="center" if mode == "name" else "left",
        )
        editor.place(x=x, y=y, width=width, height=height)
        if initial:
            editor.insert(0, initial)
        editor.bind("<Return>", self._commit_edit_event)
        editor.bind("<KP_Enter>", self._commit_edit_event)
        editor.bind("<Escape>", self._cancel_edit_event)
        editor.bind("<FocusOut>", self._commit_edit_event)
        editor.bind("<Control-KeyPress>", self._on_entry_hotkey)
        editor.bind("<Button-3>", lambda event, i=index: self._editor_menu(event, i))

        self.update_idletasks()
        editor.focus_set()
        editor.select_range(0, "end")
        editor.icursor("end")
        if mode == "path":
            self.after_idle(lambda: self._reveal_tail(editor))

        self.editor = editor
        self.edit_index = index
        self.edit_mode = mode
        if mode == "path":
            self.set_status(
                "Кнопка «%s»: впишите путь или ссылку, Enter — сохранить, Esc — отмена."
                % self.caption(index), COLOR_STATUS_NEUTRAL)
        else:
            self.set_status(
                "Кнопка «%s»: впишите новое имя, Enter — сохранить, Esc — отмена."
                % self.caption(index), COLOR_STATUS_NEUTRAL)

    def _editor_menu(self, event, index):
        self.popup_menu(event, index)
        return "break"

    def _reveal_tail(self, editor):
        if editor is not self.editor:
            return
        try:
            editor.icursor("end")
            editor.xview_moveto(1.0)
        except tk.TclError:
            pass

    def finish_edit(self, commit=True):
        editor = self.editor
        if editor is None:
            return False
        index = self.edit_index
        mode = self.edit_mode
        raw = editor.get()

        self.editor = None
        self.edit_index = None
        self.edit_mode = None
        try:
            editor.destroy()
        except tk.TclError:
            pass

        if not commit:
            self.set_status("Правка отменена.", COLOR_STATUS_NEUTRAL)
            return False

        if mode == "path":
            value = self._clean_path(raw)
            self.path_vars[index].set(value)
            if value:
                self.set_status("Кнопка «%s»: путь или ссылка — %s"
                                % (self.caption(index), value), COLOR_STATUS_NEUTRAL)
            else:
                self.set_status("Кнопка «%s»: путь или ссылка пусты."
                                % self.caption(index), COLOR_STATUS_NEUTRAL)
        else:
            value = " ".join(raw.split())
            if not value:
                value = "кнопка %d" % (index + 1)
            self.cfg["buttons"][index]["text"] = value
            self.buttons[index].configure(text=value)
            self.set_status("Кнопка переименована: «%s»" % value, COLOR_STATUS_NEUTRAL)
        self.save()
        return True

    def _commit_edit_event(self, event=None):
        self.finish_edit(commit=True)
        return "break"

    def _cancel_edit_event(self, event=None):
        self.finish_edit(commit=False)
        return "break"

    def copy_path(self, index):
        value = self.path_vars[index].get().strip()
        if not value:
            self.set_status("Кнопка «%s»: путь пуст — копировать нечего."
                            % self.caption(index), COLOR_STATUS_FAIL)
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        self.set_status("Путь скопирован: %s" % value, COLOR_STATUS_NEUTRAL)

    def clear_path(self, index):
        self.path_vars[index].set("")
        self.set_status("Кнопка «%s»: путь очищен."
                        % self.caption(index), COLOR_STATUS_NEUTRAL)
        self.save()

    def schedule_hint(self, index):
        self.hide_hint()
        self.hint_job = self.after(450, lambda: self.show_hint(index))

    def show_hint(self, index):
        self.hint_job = None
        if self.editor is not None:
            return
        path = self.path_vars[index].get().strip()
        text = path if path else "Путь или ссылка не заданы — правый клик по кнопке"
        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        try:
            tip.attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(
            tip, text=text, font=self.font("font_status"),
            bg="#FFFFE1", fg="#000000", relief="solid", borderwidth=1,
            padx=self.px(6), pady=self.px(4), justify="left",
            wraplength=self.px(360),
        ).pack()
        button = self.buttons[index]
        tip.wm_geometry("+%d+%d" % (
            button.winfo_rootx() + button.winfo_width() + self.px(12),
            button.winfo_rooty() + button.winfo_height() // 2 - self.px(14),
        ))
        self.hint = tip

    def hide_hint(self):
        if self.hint_job is not None:
            self.after_cancel(self.hint_job)
            self.hint_job = None
        if self.hint is not None:
            try:
                self.hint.destroy()
            except tk.TclError:
                pass
            self.hint = None

    @staticmethod
    def _on_entry_hotkey(event):
        widget = event.widget
        char = event.char

        if char == "\x01":
            widget.select_range(0, "end")
            widget.icursor("end")
            return "break"

        if char == "\x03":
            LaunchApp._clipboard(widget, copy=True)
            return "break"

        if char == "\x18":
            LaunchApp._clipboard(widget, cut=True)
            return "break"

        if char == "\x16":
            LaunchApp._paste(widget)
            return "break"

        return None

    @staticmethod
    def _selection(widget):
        try:
            return widget.index("sel.first"), widget.index("sel.last")
        except tk.TclError:
            return None

    @staticmethod
    def _clipboard(widget, copy=False, cut=False):
        sel = LaunchApp._selection(widget)
        if sel:
            text = widget.get()[sel[0]:sel[1]]
            widget.clipboard_clear()
            widget.clipboard_append(text)
            if cut:
                widget.delete(sel[0], sel[1])
        return "break"

    @staticmethod
    def _paste(widget):
        try:
            text = widget.clipboard_get()
        except tk.TclError:
            return "break"
        text = str(text).replace("\r", "").replace("\n", "").strip()
        if text.startswith("file:///"):
            text = text[len("file:///"):]
        text = text.strip('"').strip("'").strip()

        sel = LaunchApp._selection(widget)
        if sel:
            widget.delete(sel[0], sel[1])
            widget.insert(sel[0], text)
            widget.icursor(sel[0] + len(text))
        else:
            pos = widget.index("insert")
            widget.insert(pos, text)
            widget.icursor(pos + len(text))
        return "break"

    def set_status(self, text, color):
        self.status_text.set(text)
        self.status_label.configure(fg=color)

    def paint(self, index, ok):
        self.buttons[index].configure(
            bg=COLOR_OK if ok else COLOR_FAIL,
            activebackground=COLOR_OK if ok else COLOR_FAIL,
        )

    def choose_file(self, index):
        current = self.path_vars[index].get().strip().strip('"')
        initial = os.path.dirname(current) if os.path.isdir(os.path.dirname(current)) else None
        chosen = filedialog.askopenfilename(
            parent=self,
            title="Выберите файл для запуска",
            initialdir=initial,
            filetypes=[
                ("Программы и файлы",
                 "*.exe *.bat *.cmd *.com *.lnk *.txt *.doc *.docx *.pdf"),
                ("Все файлы", "*.*"),
            ],
        )
        if chosen:
            self.path_vars[index].set(os.path.normpath(chosen))
            self.set_status("Путь выбран: %s" % chosen, COLOR_STATUS_NEUTRAL)
            self.save()

    def _clean_path(self, raw):
        return raw.strip().strip('"').strip("'").strip()

    def launch(self, index):
        raw = self._clean_path(self.path_vars[index].get())
        caption = self.buttons[index].cget("text")

        if not raw:
            self.paint(index, False)
            self.set_status("Кнопка «%s»: путь или ссылка не заданы." % caption,
                            COLOR_STATUS_FAIL)
            self.save()
            return

        if os.path.exists(raw):
            self._run_file(index, raw)
            return

        url = self._target_url(raw)
        if url:
            self._run_url(index, url)
            return

        self.paint(index, False)
        self.set_status("Кнопка «%s»: файл не найден — %s" % (caption, raw),
                        COLOR_STATUS_FAIL)
        self.save()

    def _run_file(self, index, path):
        caption = self.buttons[index].cget("text")
        try:
            os.startfile(path)
        except OSError:
            try:
                subprocess.Popen([path], shell=False)
            except Exception as exc:
                self.paint(index, False)
                self.set_status("Кнопка «%s»: запустить не удалось — %s (%s)"
                                % (caption, path, exc), COLOR_STATUS_FAIL)
                self.save()
                return
        self.paint(index, True)
        self.set_status("Кнопка «%s»: запущено — %s" % (caption, path), COLOR_STATUS_OK)
        self.save()

    def _run_url(self, index, url):
        caption = self.buttons[index].cget("text")
        try:
            os.startfile(url)
        except OSError:
            try:
                if not webbrowser.open(url, new=2):
                    raise RuntimeError("система не открыла браузер")
            except Exception as exc:
                self.paint(index, False)
                self.set_status("Кнопка «%s»: ссылку открыть не удалось — %s (%s)"
                                % (caption, url, exc), COLOR_STATUS_FAIL)
                self.save()
                return
        self.paint(index, True)
        self.set_status("Кнопка «%s»: открыто в браузере — %s" % (caption, url),
                        COLOR_STATUS_OK)
        self.save()

    @staticmethod
    def _target_url(value):
        low = value.lower()
        if low.startswith(("http://", "https://")):
            return value
        if low.startswith("www."):
            return "http://" + value
        if " " in value or "\\" in value:
            return None
        host = low.split("/")[0]
        if ":" in host or "." not in host:
            return None
        tail = host.rsplit(".", 1)[1]
        if len(tail) < 2 or not tail.isalpha():
            return None
        if tail in FILE_EXTENSIONS:
            return None
        return "https://" + value

    def _bind_drag(self):
        self.bind("<B1-Motion>", self.drag_motion)
        self.bind("<ButtonRelease-1>", self.end_drag)
        self.bind("<B2-Motion>", self.drag_motion)
        self.bind("<ButtonRelease-2>", self.end_drag)

    @staticmethod
    def _saved_position(spec):
        try:
            return float(spec["x"]), float(spec["y"])
        except (KeyError, TypeError, ValueError):
            return None

    def begin_drag(self, event, index):
        self.hide_hint()
        if self.editor is not None:
            self.finish_edit(commit=True)
        button = self.buttons[index]
        self.drag = {
            "index": index,
            "dx": event.x_root - button.winfo_rootx(),
            "dy": event.y_root - button.winfo_rooty(),
        }
        self.configure(cursor="fleur")
        return "break"

    def drag_motion(self, event):
        if self.drag is None:
            return
        index = self.drag["index"]
        button = self.buttons[index]
        x = event.x_root - self.drag["dx"] - self.winfo_rootx()
        y = event.y_root - self.drag["dy"] - self.winfo_rooty()
        x, y = self._clamp_position(button, x, y)
        button.place_configure(x=x, y=y)
        self.positions[index] = [x, y]

    def end_drag(self, event=None):
        if self.drag is None:
            return
        index = self.drag["index"]
        self.drag = None
        self.configure(cursor="")
        self.exit_move_mode()
        self.set_status("Кнопка «%s» перемещена." % self.caption(index),
                        COLOR_STATUS_NEUTRAL)
        self.save()

    def _clamp_position(self, button, x, y):
        max_x = max(0, self.winfo_width() - button.winfo_width())
        max_y = max(0, self.winfo_height() - button.winfo_height())
        return int(max(0, min(x, max_x))), int(max(0, min(y, max_y)))

    def enter_move_mode(self, index):
        self.exit_move_mode()
        self.finish_edit(commit=True)
        self.hide_hint()
        self.move_index = index
        button = self.buttons[index]
        button.configure(cursor="fleur", command=lambda: None)
        button.bind("<Button-1>", lambda event, i=index: self.begin_drag(event, i))
        self.set_status("Кнопка «%s»: тяните её мышью, чтобы переместить."
                        % self.caption(index), COLOR_STATUS_NEUTRAL)

    def exit_move_mode(self):
        index = self.move_index
        if index is None:
            return
        self.move_index = None
        button = self.buttons[index]
        button.unbind("<Button-1>")
        button.configure(cursor="hand2", command=lambda i=index: self.launch(i))

    def collect(self):
        cfg = {"settings": dict(self.s), "buttons": []}
        for index, spec in enumerate(self.cfg["buttons"]):
            x, y = self.positions[index]
            cfg["buttons"].append({
                "text": spec.get("text") or ("кнопка %d" % (index + 1)),
                "label": spec.get("label") or ("ред. %d" % (index + 1)),
                "path": self.path_vars[index].get().strip(),
                "x": int(round(x / self.scale)),
                "y": int(round(y / self.scale)),
            })
        return cfg

    def save(self, force=False):
        self._remember_window()
        cfg = self.collect()
        try:
            save_config(self.config_path, cfg)
            return True
        except OSError as exc:
            if not self.used_fallback or force:
                fb = os.path.join(fallback_dir(), CONFIG_NAME)
                try:
                    save_config(fb, cfg)
                    self.config_path = fb
                    self.used_fallback = True
                    self.set_status("Папка программы недоступна для записи, "
                                    "настройки сохраняются в %s" % fb, COLOR_STATUS_NEUTRAL)
                    return True
                except OSError:
                    pass
            self.set_status("Не удалось сохранить настройки: %s" % exc, COLOR_STATUS_FAIL)
            return False

    def on_close(self):
        self.hide_hint()
        self.save(force=True)
        self.destroy()


def main():
    try:
        LaunchApp().mainloop()
    except Exception:
        import traceback
        try:
            import tkinter.messagebox as mb
            mb.showerror(APP_TITLE, "Неожиданная ошибка:\n\n%s" % traceback.format_exc())
        except Exception:
            sys.stderr.write(traceback.format_exc())
        raise


if __name__ == "__main__":
    main()