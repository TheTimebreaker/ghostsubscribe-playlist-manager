import logging
import tkinter as tk
from tkinter import font, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, get_args

from colors import colors


def ttk_styles(root: tk.Tk) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "TButton",
        background=colors["bg-6"],
        foreground=colors["fg"],
    )
    style.map(
        "TButton",
        background=[("active", colors["bg-8"]), ("pressed", colors["bg-7"]), ("disabled", colors["bg-3"])],
        foreground=[("active", colors["fg"]), ("pressed", colors["fg"]), ("disabled", colors["fg-disabled"])],
    )
    style.configure(
        "Confirm.TButton",
        background=colors["bg-6"],
        foreground=colors["fg"],
    )
    style.map(
        "Confirm.TButton",
        background=[("active", colors["green-2"]), ("pressed", colors["green-4"])],
        foreground=[("active", colors["fg"]), ("pressed", colors["fg"])],
    )
    style.configure(
        "Exit.TButton",
        background=colors["bg-6"],
        foreground=colors["fg"],
    )
    style.map(
        "Exit.TButton",
        background=[("active", colors["red-3"]), ("pressed", colors["red-4"])],
        foreground=[("active", colors["fg"]), ("pressed", colors["fg"])],
    )
    style.configure(
        "Working.TButton",
        background=colors["blue-3"],
        foreground=colors["fg"],
    )
    style.map(
        "Working.TButton",
        background=[("active", colors["blue-4"]), ("pressed", colors["blue-4"]), ("disabled", colors["blue-4"])],
        foreground=[("active", colors["fg"]), ("pressed", colors["fg"]), ("disabled", colors["fg-disabled"])],
    )
    style.configure(
        "Success.TButton",
        background=colors["green-3"],
        foreground=colors["fg"],
    )
    style.map(
        "Success.TButton",
        background=[("active", colors["green-4"]), ("pressed", colors["green-4"]), ("disabled", colors["green-2"])],
        foreground=[("active", colors["fg"]), ("pressed", colors["fg"]), ("disabled", colors["fg-disabled"])],
    )
    style.configure(
        "Failure.TButton",
        background=colors["red-3"],
        foreground=colors["fg"],
    )
    style.map(
        "Failure.TButton",
        background=[("active", colors["red-4"]), ("pressed", colors["red-4"]), ("disabled", colors["red-2"])],
        foreground=[("active", colors["fg"]), ("pressed", colors["fg"]), ("disabled", colors["fg-disabled"])],
    )

    media_font = font.Font(family="Times New Roman", size=100, weight="bold")
    style.configure("Media.TButton", background=colors["bg-6"], foreground=colors["fg"], font=media_font)
    style.configure("Success.Media.TButton", background=colors["green-3"], foreground=colors["fg"], font=media_font)
    style.configure("Failure.Media.TButton", background=colors["red-3"], foreground=colors["fg"], font=media_font)

    # Label
    style.configure(
        "TLabel",
        background=colors["bg-3"],
        foreground=colors["fg"],
    )
    style.configure(
        "Warning.TLabel",
        background=colors["bg-3"],
        foreground=colors["red-4"],
    )
    style.configure(
        "Selected.TLabel",
        background=colors["blue-5"],
        foreground=colors["fg"],
    )

    # Radiobutton
    style.configure("TRadiobutton", background=colors["bg-3"], foreground=colors["fg"], indicatorcolor=colors["bg-3"], focuscolor="")
    style.map(
        "TRadiobutton",
        background=[("active", colors["bg-3"]), ("pressed", colors["bg-3"])],
        foreground=[("active", colors["fg"]), ("pressed", colors["fg"])],
    )

    # Frame
    style.configure(
        "TFrame",
        background=colors["bg-3"],
        foreground=colors["fg"],
    )
    style.configure(
        "Titlebar.TFrame",
        background=colors["bg-3"],
        foreground=colors["fg"],
    )

    # Entry
    style.configure(
        "TEntry",
        foreground=colors["fg"],
        fieldbackground=colors["bg-6"],
    )
    style.map("TEntry", fieldbackground=[("focus", colors["bg-6"]), ("disabled", colors["bg-3"])], foreground=[("focus", colors["fg"])])

    # OptionMenu
    style.configure(
        "TMenubutton",
        foreground=colors["fg"],
        background=colors["bg-6"],
    )
    style.map("TMenubutton", background=[("active", colors["bg-8"]), ("disabled", colors["bg-3"])], foreground=[("active", colors["fg"])])

    # Progressbar
    tmp_color = colors["green-2"]
    style.configure(
        "TProgressbar",
        throughcolor=tmp_color,
        lightcolor=tmp_color,
        darkcolor=tmp_color,
        background=tmp_color,
    )

    # Spinbox
    style.configure(
        "TSpinbox",
        foreground=colors["fg"],
        fieldbackground=colors["bg-6"],
    )
    style.map(
        "TSpinbox",
        fieldbackground=[("focus", colors["bg-6"]), ("disabled", colors["bg-3"])],
        foreground=[("focus", colors["fg"])],
    )


def tk_styles(element: tk.Menu) -> dict[str, str]:
    if isinstance(element, tk.Menu):
        return {"background": colors["bg-3"], "foreground": colors["fg"], "activebackground": colors["blue-2"], "relief": "flat"}
    raise TypeError("Styling for this class is not defined.")


def tk_root_styles(root: tk.Tk | tk.Toplevel) -> None:
    root.config(bg=colors["bg-3"])


def is_valid_literal(val: str, literal_type: Any) -> bool:
    return val in get_args(literal_type)


class SubWindow:
    window: tk.Toplevel
    root: tk.Tk
    log_level: int
    log_visible: bool
    log_display: ScrolledText
    btn_width: int = 50
    padx = 5
    pady = 5

    def setup_logging(self) -> None:
        root_logger = logging.getLogger()
        self.log_level = logging.ERROR
        root_logger.setLevel(self.log_level)
        handler = TkinterLogHandler(app=self, log_level=self.log_level)
        root_logger.addHandler(handler)
        # Avoid adding duplicate handlers
        if not any(isinstance(h, TkinterLogHandler) for h in root_logger.handlers):
            root_logger.addHandler(handler)

    def on_close(self) -> None:
        self.window.destroy()
        self.root.destroy()

    def show_log_if_needed(self, levelno: int, msg: str) -> None:
        # Only show if severity is high enough and not already visible
        if not self.log_visible and levelno >= self.log_level:
            self.log_display.pack(padx=10, pady=10)
            self.log_visible = True

        # Append the log message
        self.log_display.insert(tk.END, msg + "\n")
        self.log_display.see(tk.END)


class TkinterLogHandler(logging.Handler):
    def __init__(self, app: SubWindow, log_level: int = logging.ERROR) -> None:
        super().__init__()
        self.app = app  # Reference to main app (which holds the widget)
        self.level_threshold = log_level

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        self.app.log_display.after(0, self.app.show_log_if_needed, record.levelno, msg)


class ToolTip:
    def __init__(self, widget: Any, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None

        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, _: Any = None) -> None:
        if self.tip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 20

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # No window decorations
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            # background="#ffffe0", relief='solid', borderwidth=1,
            background=colors["yellow-1"],
            relief="solid",
            borderwidth=1,
            font=("tahoma", 8, "normal"),
            foreground=colors["fg"],
        )
        label.pack(ipadx=4, ipady=2)

    def hide_tip(self, _: Any = None) -> None:
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
