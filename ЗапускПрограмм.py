import json
import os
import subprocess
import sys
import tkinter as tk
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

DEFAULTS = {
    "settings": {
        "title": "Запуск панели",
        "window_width": 950,
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
                    cfg["buttons"].append({
                        "text": str(item.get("text", "")),
                        "label": str(item.get("label", "")),
                        "path": str(item.get("path", "")),
                    })
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

        self._build_window()
        self._build_header()
        self._build_rows()
        self._build_status()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.load_note:
            self.set_status(self.load_note, COLOR_STATUS_FAIL)
        elif self.used_fallback:
            self.set_status(
                "Папка программы недоступна для записи — настройки сохраняются в %APPDATA%.",
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
        self.resizable(False, False)

    def _window_height(self, rows):
        needed = self.s["first_row_y"] + rows * self.s["row_pitch"] + self.s["bottom_space"]
        return self.px(max(self.s["min_height"], needed))

    def _build_header(self):
        rows = len(self.cfg["buttons"])
        self.geometry("%dx%d" % (self.px(self.s["window_width"]), self._window_height(rows)))
        tk.Label(
            self,
            text=self.s["title"] or APP_TITLE,
            font=self.font("font_title"),
            bg=COLOR_BG,
            fg="#000000",
        ).place(relx=0.5, y=self.px(30), anchor="n")

    def _entry_x(self):
        return (self.s["margin_left"] + self.s["button_width"]
                + self.s["gap_button_label"] + self.s["label_width"]
                + self.s["gap_label_entry"])

    def _entry_width(self):
        return (self.s["window_width"] - self._entry_x()
                - self.s["margin_right"] - self.s["browse_width"] - self.s["browse_gap"])

    def _build_rows(self):
        btn_w = self.px(self.s["button_width"])
        btn_h = self.px(self.s["button_height"])
        pitch = self.px(self.s["row_pitch"])
        first_y = self.px(self.s["first_row_y"])
        left = self.px(self.s["margin_left"])
        label_w = self.px(self.s["label_width"])
        label_x = self.px(self.s["margin_left"] + self.s["button_width"] + self.s["gap_button_label"])
        entry_x = self.px(self._entry_x())
        entry_w = self.px(self._entry_width())
        browse_w = self.px(self.s["browse_width"])
        browse_x = entry_x + entry_w + self.px(self.s["browse_gap"])
        entry_h = self.px(34)
        browse_h = self.px(32)

        for index, spec in enumerate(self.cfg["buttons"]):
            row_y = first_y + index * pitch

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
                command=lambda i=index: self.launch(i),
            )
            button.place(x=left, y=row_y, width=btn_w, height=btn_h)

            canvas = tk.Canvas(
                self, width=label_w, height=btn_h,
                bg=COLOR_BG, highlightthickness=0, bd=0,
            )
            canvas.place(x=label_x, y=row_y)
            canvas.create_text(
                label_w / 2, btn_h / 2,
                text=spec.get("label") or ("ред. %d" % (index + 1)),
                angle=90,
                font=self.font("font_label"),
                fill="#000000",
            )

            var = tk.StringVar(value=spec.get("path", ""))
            entry = tk.Entry(
                self, textvariable=var, font=self.font("font_entry"),
                relief="solid", borderwidth=1, bg="#FFFFFF", fg="#000000",
            )
            entry.bind("<Control-KeyPress>", self._on_entry_hotkey)
            entry.place(x=entry_x, y=row_y + (btn_h - entry_h) // 2,
                        width=entry_w, height=entry_h)

            browse = tk.Button(
                self, text="…", font=self.font("font_entry"),
                bg="#E8E8E8", fg="#000000", relief="flat", borderwidth=0,
                highlightthickness=0, cursor="hand2",
                command=lambda i=index: self.choose_file(i),
            )
            browse.place(x=browse_x, y=row_y + (btn_h - browse_h) // 2,
                         width=browse_w, height=browse_h)

            self.buttons.append(button)
            self.path_vars.append(var)

    def _build_status(self):
        self.status_label = tk.Label(
            self, textvariable=self.status_text, font=self.font("font_status"),
            bg=COLOR_BG, fg=COLOR_STATUS_NEUTRAL, anchor="w", justify="left",
        )
        self.status_label.place(
            x=self.px(self.s["margin_left"]), rely=1.0, y=-self.px(10),
            width=self.px(self.s["window_width"] - self.s["margin_left"] - self.s["margin_right"]),
            anchor="sw")


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
        path = self._clean_path(self.path_vars[index].get())

        if not path:
            self.paint(index, False)
            self.set_status("Кнопка «%s»: путь не указан."
                            % self.buttons[index].cget("text"), COLOR_STATUS_FAIL)
            self.save()
            return

        if not os.path.exists(path):
            self.paint(index, False)
            self.set_status("Кнопка «%s»: файл не найден — %s"
                            % (self.buttons[index].cget("text"), path), COLOR_STATUS_FAIL)
            self.save()
            return

        try:
            os.startfile(path)
            self.paint(index, True)
            self.set_status("Кнопка «%s»: запущено — %s"
                            % (self.buttons[index].cget("text"), path), COLOR_STATUS_OK)
            self.save()
            return
        except OSError as first_error:
            try:
                subprocess.Popen([path], shell=False)
                self.paint(index, True)
                self.set_status("Кнопка «%s»: запущено — %s"
                                % (self.buttons[index].cget("text"), path), COLOR_STATUS_OK)
                self.save()
                return
            except Exception as second_error:
                self.paint(index, False)
                self.set_status("Кнопка «%s»: запустить не удалось — %s (%s)"
                                % (self.buttons[index].cget("text"), path, second_error),
                               COLOR_STATUS_FAIL)
                self.save()


    def collect(self):
        cfg = {"settings": dict(self.s), "buttons": []}
        for index, spec in enumerate(self.cfg["buttons"]):
            cfg["buttons"].append({
                "text": spec.get("text") or ("кнопка %d" % (index + 1)),
                "label": spec.get("label") or ("ред. %d" % (index + 1)),
                "path": self.path_vars[index].get().strip(),
            })
        return cfg

    def save(self, force=False):
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
