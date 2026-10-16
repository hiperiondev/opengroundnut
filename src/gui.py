# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""PEANUT client graphical user interface.

This is the only module of the application that draws anything: it owns
every window, widget, dialog, image and font. The application core (network,
audio, database, callsign, settings and core modules) knows nothing about it.

opengroundnut.py executes this module inside the shared application namespace
after the core, and calls start_gui() and run_gui(). The two sides meet in two
directions only:

* Core to GUI: the core publishes events with emit_event() (see events.py).
  start_gui() subscribes _gui_on_event(), which routes every event to a
  handler of the "Core event handlers" section.
* GUI to core: user actions call the plain core functions, for example
  toggle_connection(), toggle_transmit(), enter_room(), start_recording(),
  set_scan_rooms() or save_setup(). The GUI may also read the core state
  (active_room, session_active, room_list, ...) to draw it.

How the GUI is organized:

* A soft light theme built with CustomTkinter for buttons, entries, switches
  and cards, plus styled ttk widgets where Tk offers no CustomTkinter
  equivalent (tables and long drop-down lists).
* A thread-safe bridge. Tk may only be touched from the main thread, but the
  core publishes events from its audio, network and lookup threads. Event
  handlers hand their work to the main thread through a queue that a short
  timer drains.
* A registry of named widgets and values, so a widget can be found by a fixed
  name such as "transmit_button" or "form_server".
* Themed message boxes and yes/no questions (gui_message, gui_ask_yes_no)
  instead of the operating system ones, so every message keeps the colors
  and fonts of the main window.
"""

import functools
import threading
import tkinter as tk
import traceback
import tkinter.font as tkfont
from pathlib import Path as _Path
from tkinter import filedialog, ttk

import customtkinter as ctk
from PIL import Image as _PILImage
from PIL import ImageChops as _PILImageChops
from PIL import ImageDraw as _PILImageDraw


# ---------------------------------------------------------------------------
# Application name and version shown to the user
# ---------------------------------------------------------------------------

# Display name and version of this client (defined in bootstrap.py). The
# protocol version sent to the Peanut server in the INFO message is
# PROTOCOL_VERSION, which the server checks, so it is kept separate.
GUI_APP_NAME = APP_NAME
GUI_APP_VERSION = APP_DISPLAY_VERSION


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

# Soft, low-contrast light palette with a few saturated accents.
GUI_COLORS = {
    "window": "#E7EAF1",
    "card": "#F2F4F9",
    "card_border": "#DCE1EA",
    "field": "#FBFCFE",
    "field_border": "#D2D8E3",
    "table": "#FBFCFE",
    "table_alt": "#F2F4F9",
    "table_head": "#E6E9F2",
    "text": "#2F3A4F",
    "muted": "#7D879A",
    "disabled": "#A9B0BE",
    "neutral": "#E3E7EF",
    "neutral_hover": "#D7DCE7",
    "accent": "#6C63E8",
    "accent_hover": "#5A51D6",
    "accent_soft": "#E4E2FB",
    "info": "#4D8DF0",
    "info_hover": "#3E7BDC",
    "success": "#34B987",
    "success_hover": "#2BA176",
    "success_soft": "#DDF4EB",
    "danger": "#E5566F",
    "danger_hover": "#CF465F",
    "danger_soft": "#FBE3E8",
    "warning": "#F2B94B",
    "teal": "#2EC4D3",
}

# Button roles: (background, hover background, text color, disabled text color)
GUI_BUTTON_ROLES = {
    "neutral": ("neutral", "neutral_hover", "text", "disabled"),
    "accent": ("accent", "accent_hover", "#FFFFFF", "#ECEBFF"),
    "info": ("info", "info_hover", "#FFFFFF", "#FFFFFF"),
    "success": ("success", "success_hover", "#FFFFFF", "#E8FFF6"),
    "danger": ("danger", "danger_hover", "#FFFFFF", "#FFFFFF"),
    "danger_soft": ("danger_soft", "#F6CED6", "danger", "disabled"),
    "ghost": ("card", "neutral", "text", "disabled"),
}

# Role of the push-to-talk button for each link state (0 idle, 1 receiving,
# 2 transmitting).
GUI_PTT_ROLES = {0: "neutral", 1: "info", 2: "danger"}


def _gui_color(name):
    """Return a palette color by name, or the value itself when it is a literal color."""
    return GUI_COLORS.get(name, name)


# ---------------------------------------------------------------------------
# Shared GUI state
# ---------------------------------------------------------------------------

root = None
photo_label = None
flag_label = None
monitor_frame = None
monitor_filter = None
last_heard_tree = None
toast_frame = None

# Widget scaling in use (user scale times the automatic fit to the screen).
ui_scale = 1


_gui_alive = False
_gui_main_thread_id = threading.get_ident()
_gui_queue = None
_gui_pending_values = {}
_gui_pending_lock = threading.Lock()
_gui_registry = {}
_gui_registry_pages = {}
_gui_fonts = {}
_gui_images = {}
_gui_widgets = {}
_gui_tables = []
_gui_combos = []
_gui_toast_job = None
_gui_monitor_rows = None
_gui_timer_seconds = 0
_gui_timer_status = 0
_gui_window_icon = None


# ---------------------------------------------------------------------------
# Thread-safe bridge between worker threads and the Tk main thread
# ---------------------------------------------------------------------------

def _gui_is_main_thread():
    """True when the caller runs on the thread that created the Tk window."""
    return threading.get_ident() == _gui_main_thread_id


def _gui_run_safely(func, *args, **kwargs):
    """Run a GUI job and report, without crashing the GUI, any error it raises."""
    try:
        return func(*args, **kwargs)
    except tk.TclError:
        # The widget was destroyed while the job waited in the queue.
        return None
    except Exception:
        log.exception("GUI job %s failed", getattr(func, "__name__", func))
        return None


def _gui_post(func, *args, **kwargs):
    """Run func on the main thread: right now if already there, otherwise queued."""
    if _gui_is_main_thread():
        return _gui_run_safely(func, *args, **kwargs)
    if _gui_alive and _gui_queue is not None:
        _gui_queue.put(lambda: _gui_run_safely(func, *args, **kwargs))
    return None


def _gui_call_sync(func, *args, default=None, timeout=None, **kwargs):
    """Run func on the main thread and wait for its result.

    Worker threads use this when they need an answer (a value, a dialog reply
    or a timer handle). The wait gives up and returns `default` when the
    window closes, or when `timeout` seconds pass.
    """
    if _gui_is_main_thread():
        return _gui_run_safely(func, *args, **kwargs)
    if not _gui_alive or _gui_queue is None:
        return default

    finished = threading.Event()
    result = {"value": default}

    def job():
        try:
            result["value"] = _gui_run_safely(func, *args, **kwargs)
        finally:
            finished.set()

    _gui_queue.put(job)
    waited = 0.0
    while not finished.wait(0.1):
        waited += 0.1
        if not _gui_alive:
            return default
        if timeout is not None and waited >= timeout:
            return default
    return result["value"]


def _gui_on_main_thread(wait=False, default=None):
    """Decorator that makes a GUI function safe to call from any thread.

    With wait=False the call is queued and returns immediately (fire and
    forget). With wait=True the caller blocks until the main thread finished
    the call and gets its return value.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if _gui_is_main_thread():
                return func(*args, **kwargs)
            if wait:
                return _gui_call_sync(func, *args, default=default, **kwargs)
            _gui_post(func, *args, **kwargs)
            return default

        return wrapper

    return decorator


def _gui_pump():
    """Drain the cross-thread queue and apply the values set from worker threads.

    Runs every few milliseconds on the main thread for the whole life of the
    window. The next run is booked first: a job that opens a window and waits
    for it (a message box, for example) then cannot stop the queue, because Tk
    keeps running timers while it waits.
    """
    if not _gui_alive:
        return
    root.after(15, _gui_pump)

    # Run the queued jobs, but never more than a batch at a time so a burst of
    # events from the audio threads cannot freeze the window.
    for _ in range(200):
        try:
            job = _gui_queue.get_nowait()
        except Exception:
            break
        job()

    # Apply only the newest value of each variable set from a worker thread.
    # The audio meter, for example, is updated 50 times per second.
    with _gui_pending_lock:
        pending = dict(_gui_pending_values)
        _gui_pending_values.clear()
    for name, value in pending.items():
        _gui_run_safely(_gui_write_value, name, value)


# ---------------------------------------------------------------------------
# Scaling, fonts and images
# ---------------------------------------------------------------------------

def _gui_px(value):
    """Convert a base pixel size into real pixels for ttk and Tk widgets.

    CustomTkinter widgets scale themselves; ttk widgets, Tk listboxes and
    menus need explicit pixel values, which this helper computes from the same
    scaling CustomTkinter uses (configured UI scale times screen DPI).
    """
    return int(round(value * _gui_total_scale()))


def _gui_total_scale():
    """Combined widget scaling (user scale times screen DPI scaling)."""
    try:
        return float(ctk.ScalingTracker.get_widget_scaling(root))
    except Exception:
        return float(globals().get("ui_scale", 1.0) or 1.0)


def _gui_window_scale():
    """Scaling CustomTkinter applies to window geometry values."""
    try:
        return float(ctk.ScalingTracker.get_window_scaling(root))
    except Exception:
        return 1.0


# Orbitron fonts shipped with the project, registered for this process only.
_GUI_FONT_DIR = _Path(resource_path("fonts")) / "orbitron"


def _gui_register_bundled_fonts():
    """Make the bundled Orbitron fonts available to Tk for this process only.

    Nothing is installed system-wide. Returns True when the fonts were
    registered, False when they are missing or the platform refused them.
    """
    if not _GUI_FONT_DIR.is_dir():
        return False
    ttf_files = list(_GUI_FONT_DIR.glob("*.ttf"))
    if not ttf_files:
        return False
    try:
        import ctypes as _ctypes
        from ctypes.util import find_library as _find_library

        if sys.platform.startswith("win"):
            FR_PRIVATE = 0x10
            for font in ttf_files:
                _ctypes.windll.gdi32.AddFontResourceExW(str(font), FR_PRIVATE, 0)
        elif sys.platform == "darwin":
            # CoreText registration is per-process and does not install fonts globally.
            coretext = _ctypes.CDLL(_find_library("CoreText"))
            corefoundation = _ctypes.CDLL(_find_library("CoreFoundation"))
            corefoundation.CFURLCreateFromFileSystemRepresentation.restype = _ctypes.c_void_p
            corefoundation.CFURLCreateFromFileSystemRepresentation.argtypes = [
                _ctypes.c_void_p, _ctypes.c_char_p, _ctypes.c_long, _ctypes.c_bool
            ]
            coretext.CTFontManagerRegisterFontsForURL.argtypes = [
                _ctypes.c_void_p, _ctypes.c_int, _ctypes.POINTER(_ctypes.c_void_p)
            ]
            for font in ttf_files:
                url = corefoundation.CFURLCreateFromFileSystemRepresentation(
                    None, str(font).encode(), len(str(font).encode()), False
                )
                if url:
                    coretext.CTFontManagerRegisterFontsForURL(url, 1, None)
        else:
            # Fontconfig's application-font API makes these files available to
            # Tk/Xft in this process without copying them into system folders.
            libname = _find_library("fontconfig")
            if not libname:
                return False
            fc = _ctypes.CDLL(libname)
            fc.FcConfigGetCurrent.restype = _ctypes.c_void_p
            fc.FcConfigAppFontAddDir.argtypes = [_ctypes.c_void_p, _ctypes.c_char_p]
            fc.FcConfigBuildFonts.argtypes = [_ctypes.c_void_p]
            font_config = fc.FcConfigGetCurrent()
            if not font_config or not fc.FcConfigAppFontAddDir(font_config, os.fsencode(_GUI_FONT_DIR)):
                return False
            fc.FcConfigBuildFonts(font_config)
        return True
    except Exception:
        return False


def _gui_pick_family(candidates, fallback):
    """Return the first installed font family among the candidates."""
    try:
        installed = {name.lower(): name for name in tkfont.families(root)}
    except Exception:
        installed = {}
    for family in candidates:
        if family.lower() in installed:
            return installed[family.lower()]
    return fallback


def _gui_build_fonts():
    """Create the fonts used across the window.

    Orbitron, bundled with the project, is used for headings, the callsign and
    the clocks. Body text and tables use the operating system's sans-serif
    font, which is far easier to read at small sizes.
    """
    default_family = tkfont.nametofont("TkDefaultFont", root).actual("family")
    body = _gui_pick_family(
        ("Segoe UI", "Inter", "Noto Sans", "Ubuntu", "Cantarell", "DejaVu Sans", "Helvetica Neue", "Helvetica", "Arial"),
        default_family,
    )
    display = _gui_pick_family(("Orbitron",), body)
    _gui_fonts.update(
        {
            "body_family": body,
            "display_family": display,
            "body": ctk.CTkFont(family=body, size=13),
            "body_bold": ctk.CTkFont(family=body, size=13, weight="bold"),
            "small": ctk.CTkFont(family=body, size=11),
            "caption": ctk.CTkFont(family=body, size=12),
            "card_title": ctk.CTkFont(family=display, size=13, weight="bold"),
            "button": ctk.CTkFont(family=body, size=13, weight="bold"),
            "button_big": ctk.CTkFont(family=display, size=16, weight="bold"),
            "ptt": ctk.CTkFont(family=display, size=20, weight="bold"),
            "callsign": ctk.CTkFont(family=display, size=26, weight="bold"),
            "identity": ctk.CTkFont(family=display, size=15, weight="bold"),
            "brand": ctk.CTkFont(family=display, size=20, weight="bold"),
            "clock": ctk.CTkFont(family=display, size=14, weight="bold"),
            "timer": ctk.CTkFont(family=display, size=22, weight="bold"),
            "tab": ctk.CTkFont(family=body, size=13, weight="bold"),
            # Pixel-sized Tk fonts for ttk tables, drop-down lists and menus.
            "tk_body": tkfont.Font(root, family=body, size=-_gui_px(13)),
            "tk_bold": tkfont.Font(root, family=body, size=-_gui_px(13), weight="bold"),
        }
    )


def _gui_load_image(path, size, knockout_white=False):
    """Load an icon from disk as a CTkImage of the given logical size.

    knockout_white turns a plain white background into transparency, which
    lets the opaque speaker icons sit nicely on the themed buttons.
    """
    key = (path, size, knockout_white)
    if key in _gui_images:
        return _gui_images[key]
    try:
        with _PILImage.open(path) as source:
            image = source.convert("RGBA")
        if knockout_white:
            # A pixel is "white" when even its darkest channel is very bright.
            red, green, blue, alpha = image.split()
            darkest = _PILImageChops.darker(_PILImageChops.darker(red, green), blue)
            keep = darkest.point(lambda value: 0 if value > 235 else 255)
            image.putalpha(_PILImageChops.multiply(alpha, keep))
        image = _gui_fit_image(image, size)
        result = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
    except Exception as exc:
        log.warning("Unable to load image %s: %r", path, exc)
        result = None
    _gui_images[key] = result
    return result


def _gui_fit_image(image, size):
    """Scale a PIL image to fit inside a (width, height) box, keeping its shape."""
    box_w, box_h = size
    scale = min(box_w / float(image.width), box_h / float(image.height))
    new_size = (max(1, int(round(image.width * scale))), max(1, int(round(image.height * scale))))
    if new_size != image.size:
        image = image.resize(new_size, _PILImage.LANCZOS)
    return image


def _gui_rounded(image, radius):
    """Return a copy of a PIL image with rounded corners."""
    image = image.convert("RGBA")
    mask = _PILImage.new("L", image.size, 0)
    _PILImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=radius, fill=255)
    result = image.copy()
    result.putalpha(mask)
    return result


def _gui_blank_image(size):
    """Transparent CTkImage used when a label must show "no picture"."""
    key = ("blank", size)
    if key not in _gui_images:
        blank = _PILImage.new("RGBA", size, (0, 0, 0, 0))
        _gui_images[key] = ctk.CTkImage(light_image=blank, dark_image=blank, size=size)
    return _gui_images[key]


def _gui_circle_image(color, diameter):
    """Smooth filled circle as a CTkImage, used as the badge behind a symbol.

    The circle is drawn four times larger and then scaled down, which gives
    soft edges on every platform.
    """
    key = ("circle", color, diameter)
    if key not in _gui_images:
        big = diameter * 4
        image = _PILImage.new("RGBA", (big, big), (0, 0, 0, 0))
        _PILImageDraw.Draw(image).ellipse((0, 0, big - 1, big - 1), fill=color)
        image = image.resize((diameter * 2, diameter * 2), _PILImage.LANCZOS)
        _gui_images[key] = ctk.CTkImage(light_image=image, dark_image=image, size=(diameter, diameter))
    return _gui_images[key]


def gui_photo_image(pil_image):
    """Convert a PIL image into an image that CustomTkinter labels can show."""
    if pil_image is None or not hasattr(pil_image, "size"):
        return None
    image = pil_image.copy()
    return ctk.CTkImage(light_image=image, dark_image=image, size=image.size)


def _gui_open_picture(path):
    """Load a picture file as an RGBA PIL image, or None when it cannot be read."""
    if not path:
        return None
    try:
        with _PILImage.open(path) as source:
            return source.convert("RGBA")
    except Exception:
        return None



# ---------------------------------------------------------------------------
# Registry of named widgets and values
# ---------------------------------------------------------------------------

def _gui_register(name, obj, page=None):
    """Publish a widget or value under a fixed name.

    page optionally records the settings section that holds the widget, so
    ui_focus_widget() can bring that section into view first.
    """
    _gui_registry[name] = obj
    if page is not None:
        _gui_registry_pages[name] = page
    return obj


def _gui_lookup(name):
    """Find a named widget or value in the GUI registry."""
    return _gui_registry.get(name)


def _gui_write_value(name, value):
    """Write a named value on the main thread."""
    target = _gui_lookup(name)
    if target is not None and hasattr(target, "set"):
        target.set(value)


# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------

class _GuiCard(ctk.CTkFrame):
    """Rounded panel with an optional title row.

    Content goes into self.body; extra controls can be packed into
    self.title_tools, which sits at the right end of the title row.
    """

    def __init__(self, master, title=None, padding=14, **kwargs):
        super().__init__(
            master,
            fg_color=GUI_COLORS["card"],
            corner_radius=18,
            border_width=1,
            border_color=GUI_COLORS["card_border"],
            **kwargs
        )
        self.grid_columnconfigure(0, weight=1)
        row = 0
        self.title_label = None
        self.title_tools = None
        if title is not None:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.grid(row=0, column=0, sticky="ew", padx=padding, pady=(padding - 4, 4))
            header.grid_columnconfigure(0, weight=1)
            self.title_label = ctk.CTkLabel(
                header, text=title, font=_gui_fonts["card_title"], text_color=GUI_COLORS["text"], anchor="w"
            )
            self.title_label.grid(row=0, column=0, sticky="w")
            # An empty CustomTkinter frame asks for 200x200 pixels, so the tool
            # area starts at 1x1 and grows with the buttons placed in it.
            self.title_tools = ctk.CTkFrame(header, fg_color="transparent", width=1, height=1)
            self.title_tools.grid(row=0, column=1, sticky="e")
            row = 1
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=row, column=0, sticky="nsew", padx=padding, pady=(0 if title else padding, padding))
        self.grid_rowconfigure(row, weight=1)

    def set_title(self, text):
        if self.title_label is not None:
            self.title_label.configure(text=text)


class _GuiButton(ctk.CTkButton):
    """Themed button whose colors come from one of the GUI_BUTTON_ROLES."""

    def __init__(self, master, role="neutral", **kwargs):
        kwargs.setdefault("font", _gui_fonts["button"])
        kwargs.setdefault("corner_radius", 14)
        kwargs.setdefault("height", 34)
        super().__init__(master, **kwargs)
        self.role = None
        self.set_role(role)

    def set_role(self, role):
        background, hover, text, disabled = GUI_BUTTON_ROLES.get(role, GUI_BUTTON_ROLES["neutral"])
        self.role = role
        super().configure(
            fg_color=_gui_color(background),
            hover_color=_gui_color(hover),
            text_color=_gui_color(text),
            text_color_disabled=_gui_color(disabled),
        )

    def update_look(self, role=None, text=None, enabled=None):
        """Change the role, the caption and whether the button can be pressed (None keeps each one)."""
        if role is not None:
            self.set_role(role)
        options = {}
        if text is not None:
            options["text"] = text
        if enabled is not None:
            options["state"] = "normal" if enabled else "disabled"
        if options:
            super().configure(**options)


class _GuiCombo(ttk.Combobox):
    """Themed drop-down list (ttk), comfortable with very long lists of rooms."""

    def __init__(self, master, values=(), variable=None, readonly=True, width=18, command=None, **kwargs):
        self.variable = variable if variable is not None else tk.StringVar(master=root)
        super().__init__(
            master,
            textvariable=self.variable,
            values=list(values),
            state="readonly" if readonly else "normal",
            width=width,
            style="Gui.TCombobox",
            font=_gui_fonts["tk_body"],
            **kwargs
        )
        self._is_readonly = readonly
        _gui_combos.append(self)
        if command is not None:
            self.bind("<<ComboboxSelected>>", command)

    def set_values(self, values):
        self.configure(values=list(values))

    def set_enabled(self, enabled):
        """Let the user change the choice (True) or lock it (False)."""
        self.configure(state=("readonly" if self._is_readonly else "normal") if enabled else "disabled")


class _GuiSpin(ctk.CTkFrame):
    """Integer input with - and + buttons, clamped to a range.

    It exposes get(), set() and the IntVar it edits, so it can be used as a
    named value.
    """

    def __init__(self, master, minimum, maximum, variable=None, step=1, width=70):
        super().__init__(master, fg_color="transparent")
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.variable = variable if variable is not None else tk.IntVar(master=root, value=minimum)
        self._text = tk.StringVar(master=root, value=str(self._safe_value()))
        self.minus = _GuiButton(self, text="\u2212", width=30, height=30, corner_radius=10, command=lambda: self._bump(-1))
        self.minus.grid(row=0, column=0)
        self.entry = ctk.CTkEntry(
            self,
            textvariable=self._text,
            width=width,
            height=30,
            justify="center",
            font=_gui_fonts["body"],
            fg_color=GUI_COLORS["field"],
            border_color=GUI_COLORS["field_border"],
            text_color=GUI_COLORS["text"],
            corner_radius=10,
        )
        self.entry.grid(row=0, column=1, padx=4)
        self.plus = _GuiButton(self, text="+", width=30, height=30, corner_radius=10, command=lambda: self._bump(1))
        self.plus.grid(row=0, column=2)
        self.entry.bind("<FocusOut>", lambda _event: self._commit())
        self.entry.bind("<Return>", lambda _event: self._commit())
        for widget in (self.entry, self.minus, self.plus):
            widget.bind("<MouseWheel>", self._on_wheel)
            widget.bind("<Button-4>", lambda _event: self._bump(1))
            widget.bind("<Button-5>", lambda _event: self._bump(-1))
        self.variable.trace_add("write", lambda *_args: self._text.set(str(self._safe_value())))

    def _safe_value(self):
        try:
            return int(self.variable.get())
        except (tk.TclError, ValueError):
            return self.minimum

    def _clamp(self, value):
        return max(self.minimum, min(self.maximum, value))

    def _bump(self, direction):
        self._commit()
        self.variable.set(self._clamp(self._safe_value() + direction * self.step))

    def _on_wheel(self, event):
        self._bump(1 if event.delta > 0 else -1)

    def _commit(self):
        """Copy the typed text into the variable, clamped to the valid range."""
        try:
            value = self._clamp(int(str(self._text.get()).strip()))
        except ValueError:
            value = self._safe_value()
        self.variable.set(value)
        self._text.set(str(value))

    def get(self):
        self._commit()
        return self._safe_value()

    def set(self, value):
        try:
            self.variable.set(self._clamp(int(value)))
        except (TypeError, ValueError):
            pass

    def set_enabled(self, enabled):
        """Let the user change the value (True) or lock it (False)."""
        state = "normal" if enabled else "disabled"
        for widget in (self.entry, self.minus, self.plus):
            widget.configure(state=state)
        self.entry.configure(text_color=GUI_COLORS["text"] if enabled else GUI_COLORS["disabled"])


class _GuiTable(ctk.CTkFrame):
    """ttk.Treeview with a vertical scrollbar inside a rounded frame.

    The tree itself is available as self.tree; it is what gets registered, and
    it is used through the regular Treeview API (insert, delete, get_children,
    see, ...).
    """

    def __init__(self, master, columns, headings, widths, anchors=None, display=None, height=8):
        super().__init__(master, fg_color=GUI_COLORS["table"], corner_radius=14, border_width=1, border_color=GUI_COLORS["card_border"])
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show="headings",
            height=height,
            style="Gui.Treeview",
            selectmode="browse",
        )
        if display is not None:
            self.tree["displaycolumns"] = display
        anchors = anchors or ["w"] * len(columns)
        self.base_widths = dict(zip(columns, widths))
        for column, heading, anchor in zip(columns, headings, anchors):
            self.tree.heading(column, text=heading, anchor=anchor)
            self.tree.column(column, anchor=anchor, stretch=True)
        self.apply_column_widths()
        _gui_tables.append(self)
        self.tree.tag_configure("odd", background=GUI_COLORS["table_alt"])
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview, width=12, button_color=GUI_COLORS["neutral_hover"])
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 4), pady=8)
        self.tree.configure(yscrollcommand=self.scrollbar.set)

    def apply_column_widths(self):
        """Size the columns for the current UI scale."""
        for column, width in self.base_widths.items():
            self.tree.column(column, width=_gui_px(width), minwidth=_gui_px(30))


class _GuiTooltip:
    """Small hint shown when the pointer rests on a widget."""

    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        self.job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self.job = self.widget.after(600, self._show)

    def _cancel(self):
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def _show(self):
        self.job = None
        if not self.text or self.window is not None:
            return
        try:
            x = self.widget.winfo_rootx() + _gui_px(10)
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + _gui_px(6)
        except tk.TclError:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.configure(background=GUI_COLORS["text"])
        tk.Label(
            self.window,
            text=self.text,
            background=GUI_COLORS["text"],
            foreground="#FFFFFF",
            font=_gui_fonts["tk_body"],
            padx=_gui_px(8),
            pady=_gui_px(4),
        ).pack()
        self.window.wm_geometry("+{}+{}".format(x, y))

    def _hide(self, _event=None):
        self._cancel()
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None


class _GuiGroupFilter(_GuiButton):
    """Multi-choice room group filter of the Monitor tab.

    Pressing the button opens a small checklist of the room groups; every
    click ticks or unticks one group. With no group ticked, every room is
    shown. on_change is called after every change.
    """

    def __init__(self, master, on_change=None):
        super().__init__(master, role="neutral", text="", width=190, anchor="w", command=self._open)
        self.groups = []
        self.ticked = set()
        self.on_change = on_change
        self.popup = None
        self.listbox = None
        self._refresh_caption()

    def set_groups(self, groups):
        """Offer a new list of groups; ticked groups that still exist stay ticked."""
        self.groups = [str(group) for group in groups]
        self.ticked &= set(self.groups)
        self._refresh_caption()
        self._sync_popup()

    def ticked_groups(self):
        """Ticked group names, in list order."""
        return [group for group in self.groups if group in self.ticked]

    def _refresh_caption(self):
        names = self.ticked_groups()
        if not names or "ALL" in names:
            summary = tr("monitor.filter_all")
        elif len(names) <= 2:
            summary = ", ".join(names)
        else:
            summary = "{}, {} +{}".format(names[0], names[1], len(names) - 2)
        super().configure(text="{}: {}  \u25be".format(tr("monitor.filter"), summary))

    def _open(self):
        if self.popup is not None:
            self._close()
            return
        self.popup = tk.Toplevel(root)
        self.popup.wm_overrideredirect(True)
        self.popup.configure(background=GUI_COLORS["card_border"])
        frame = tk.Frame(self.popup, background=GUI_COLORS["field"])
        frame.pack(fill="both", expand=True, padx=1, pady=1)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", style="Gui.Vertical.TScrollbar")
        self.listbox = tk.Listbox(
            frame,
            selectmode="multiple",
            exportselection=False,
            activestyle="none",
            height=min(14, max(4, len(self.groups))),
            width=24,
            font=_gui_fonts["tk_body"],
            background=GUI_COLORS["field"],
            foreground=GUI_COLORS["text"],
            selectbackground=GUI_COLORS["accent_soft"],
            selectforeground=GUI_COLORS["accent"],
            highlightthickness=0,
            borderwidth=0,
            yscrollcommand=scrollbar.set,
        )
        scrollbar.configure(command=self.listbox.yview)
        self.listbox.pack(side="left", fill="both", expand=True, padx=_gui_px(6), pady=_gui_px(6))
        scrollbar.pack(side="right", fill="y")
        self._sync_popup()
        self.listbox.bind("<<ListboxSelect>>", self._on_toggle)
        self.listbox.bind("<Escape>", lambda _event: self._close())
        self.popup.bind("<FocusOut>", lambda _event: self.after(150, self._close_if_unfocused))
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + _gui_px(4)
        self.popup.wm_geometry("+{}+{}".format(x, y))
        self.popup.after(10, self.listbox.focus_force)

    def _close_if_unfocused(self):
        try:
            focused = root.focus_get()
        except (KeyError, tk.TclError):
            focused = None
        if self.popup is not None and (focused is None or not str(focused).startswith(str(self.popup))):
            self._close()

    def _close(self):
        if self.popup is not None:
            try:
                self.popup.destroy()
            except tk.TclError:
                pass
        self.popup = None
        self.listbox = None

    def _sync_popup(self):
        """Show the groups, with a check mark on the ticked ones, in the open checklist."""
        if self.listbox is None:
            return
        first_visible = self.listbox.yview()[0]
        self.listbox.delete(0, "end")
        for index, group in enumerate(self.groups):
            ticked = group in self.ticked
            self.listbox.insert("end", "{}  {}".format("\u2713" if ticked else "  ", group))
            if ticked:
                self.listbox.selection_set(index)
        self.listbox.yview_moveto(first_visible)

    def _on_toggle(self, _event=None):
        ticked_now = {self.groups[index] for index in self.listbox.curselection() if index < len(self.groups)}
        if ticked_now == self.ticked:
            return
        self.ticked = ticked_now
        self._refresh_caption()
        self._sync_popup()
        if self.on_change is not None:
            self.on_change()


def _gui_alarm_state_text(state):
    """Readable text for an alarm state ("on" or "off") in the user's language."""
    state = str(state).strip().lower()
    if state == "on":
        return tr("alarms.online")
    if state == "off":
        return tr("alarms.offline")
    return state


class _GuiAlarmLog(ctk.CTkFrame):
    """Alarm report table fed with the tab separated rows of the "alarms_updated" event."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        columns = ("callsign", "state", "time", "room")
        headings = (
            tr("field.callsign"),
            tr("alarms.state"),
            tr("alarms.time_utc"),
            tr("field.room"),
        )
        self.table = _GuiTable(self, columns, headings, (140, 90, 170, 140), height=12)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.table.tree.tag_configure("on", foreground=GUI_COLORS["success"])
        self.table.tree.tag_configure("off", foreground=GUI_COLORS["muted"])

    def gui_append(self, text, replace=False):
        tree = self.table.tree
        if replace:
            tree.delete(*tree.get_children())
        for line in str(text).splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            fields = (fields + ["", "", "", ""])[:4]
            state = fields[1].strip().lower()
            tags = (state,) if state in ("on", "off") else ()
            fields[1] = _gui_alarm_state_text(state)
            tree.insert("", "end", values=[field.strip() for field in fields], tags=tags)

    def clear(self):
        tree = self.table.tree
        tree.delete(*tree.get_children())


def _gui_label(master, text="", font="body", color="text", **kwargs):
    """Plain themed label."""
    return ctk.CTkLabel(master, text=text, font=_gui_fonts[font], text_color=_gui_color(color), **kwargs)


def _gui_entry(master, variable, width=200, show=None, **kwargs):
    """Themed single-line text entry bound to a Tk variable."""
    return ctk.CTkEntry(
        master,
        textvariable=variable,
        width=width,
        height=32,
        show=show,
        font=_gui_fonts["body"],
        fg_color=GUI_COLORS["field"],
        border_color=GUI_COLORS["field_border"],
        text_color=GUI_COLORS["text"],
        corner_radius=10,
        **kwargs
    )


def _gui_switch(master, text, variable):
    """Themed on/off switch bound to an IntVar (1 = on, 0 = off)."""
    return ctk.CTkSwitch(
        master,
        text=text,
        variable=variable,
        onvalue=1,
        offvalue=0,
        font=_gui_fonts["body"],
        text_color=GUI_COLORS["text"],
        progress_color=GUI_COLORS["accent"],
        fg_color=GUI_COLORS["neutral_hover"],
        button_color="#FFFFFF",
        button_hover_color="#F4F4FF",
    )


def _gui_uppercase(variable):
    """Keep the text of a StringVar in upper case while the user types."""

    def to_upper(*_args):
        value = variable.get()
        if value != value.upper():
            variable.set(value.upper())

    variable.trace_add("write", to_upper)
    return variable


def _gui_context_menu():
    """Themed right-click menu."""
    return tk.Menu(
        root,
        tearoff=0,
        background=GUI_COLORS["field"],
        foreground=GUI_COLORS["text"],
        activebackground=GUI_COLORS["accent_soft"],
        activeforeground=GUI_COLORS["accent"],
        borderwidth=1,
        relief="flat",
        font=_gui_fonts["tk_body"],
    )


def _gui_show_menu(menu, event):
    """Open a context menu at the pointer; it closes itself on the next click."""
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()


def _gui_bind_right_click(widget, handler):
    """Bind the context-menu mouse buttons of every platform."""
    widget.bind("<Button-3>", handler)
    if root.tk.call("tk", "windowingsystem") == "aqua":
        widget.bind("<Button-2>", handler)
        widget.bind("<Control-Button-1>", handler)


class _GuiTabBar(ctk.CTkFrame):
    """Row of pill-shaped tab buttons that switches between stacked pages.

    Tabs are addressed by index: 0 Main, 1 Monitor, 2 Logbook, 3 Alarm log and
    4 Settings. A tab can be disabled, which is how the Settings page is
    locked while connected.
    """

    def __init__(self, master, page_holder, on_change):
        super().__init__(master, fg_color=GUI_COLORS["neutral"], corner_radius=18)
        self.page_holder = page_holder
        self.on_change = on_change
        self.buttons = []
        self.pages = []
        self.states = []
        self.titles = []
        self.badges = []
        self.current = None

    def add(self, page, title):
        index = len(self.pages)
        self.titles.append(title)
        self.badges.append(False)
        button = ctk.CTkButton(
            self,
            text=title,
            font=_gui_fonts["tab"],
            corner_radius=14,
            height=32,
            width=110,
            command=lambda: self.select(index),
        )
        button.grid(row=0, column=index, padx=(4 if index == 0 else 2, 2), pady=4)
        page.grid(row=0, column=0, sticky="nsew")
        self.buttons.append(button)
        self.pages.append(page)
        self.states.append("normal")
        self._paint()

    def index(self):
        return self.current

    def select(self, index):
        if index is None or not 0 <= index < len(self.pages) or self.states[index] == "disabled":
            return
        changed = index != self.current
        self.current = index
        self.badges[index] = False
        self.pages[index].tkraise()
        self._paint()
        if changed and self.on_change is not None:
            self.on_change()

    def set_badge(self, index, visible=True):
        """Mark a tab with a dot, to say something new happened there."""
        if 0 <= index < len(self.pages) and index != self.current:
            self.badges[index] = bool(visible)
            self._paint()

    def set_state(self, index, state):
        if not 0 <= index < len(self.pages):
            return
        self.states[index] = "disabled" if str(state).startswith("disable") else "normal"
        if self.states[index] == "disabled" and self.current == index:
            self.select(0)
        self._paint()

    def _paint(self):
        for index, button in enumerate(self.buttons):
            button.configure(text=self.titles[index] + ("  \u25cf" if self.badges[index] else ""))
            if index == self.current:
                button.configure(
                    fg_color=GUI_COLORS["card"],
                    hover_color=GUI_COLORS["card"],
                    text_color=GUI_COLORS["accent"],
                    state="normal",
                )
            else:
                button.configure(
                    fg_color=GUI_COLORS["neutral"],
                    hover_color=GUI_COLORS["neutral_hover"],
                    text_color=GUI_COLORS["muted"],
                    text_color_disabled=GUI_COLORS["disabled"],
                    state=self.states[index],
                )


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

def create_main_window():
    """Create the application's root window.

    The bundled Orbitron fonts are registered for this process first, then
    the light CustomTkinter appearance is selected and the cross-thread pump
    is started.
    """
    global root, _gui_alive, _gui_queue, _gui_main_thread_id
    import queue as _queue_module

    _gui_register_bundled_fonts()
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    _gui_main_thread_id = threading.get_ident()
    _gui_queue = _queue_module.Queue()
    root = ctk.CTk(fg_color=GUI_COLORS["window"])
    root.withdraw()
    root.report_callback_exception = _gui_report_callback_exception
    _gui_alive = True
    root.after(15, _gui_pump)
    return root


def _gui_report_callback_exception(exc_type, exc_value, exc_traceback):
    """An error in a button, menu or timer of the window: log it and tell the user.

    Tk would otherwise print it to a console that often does not exist.
    """
    log.error(
        "Error in the window:\n%s", "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    )
    try:
        gui_message(GUI_APP_NAME, "{}: {}".format(exc_type.__name__, exc_value), "error", wait=False)
    except Exception:
        pass


def apply_ui_scale():
    """Apply the UI scale chosen in the settings (or the PEANUT_UI_SCALE variable).

    The saved value is a whole number between SCALE_MIN and SCALE_MAX
    (1 = normal size); the environment variable also accepts fractions such
    as 1.25. The result is handed to CustomTkinter, which scales every themed
    widget; ttk tables and lists follow through _gui_px().
    """
    global ui_scale
    try:
        requested = float(os.environ.get("PEANUT_UI_SCALE", ui_scale_setting))
    except (TypeError, ValueError):
        requested = float(globals().get("ui_scale_setting", 1) or 1)
    ui_scale = min(float(SCALE_MAX), max(0.65, requested))
    ctk.set_widget_scaling(ui_scale)


def gui_set_window_icon(image_path):
    """Set the window icon from an .ico or image file."""
    global _gui_window_icon
    try:
        from PIL import ImageTk as _ImageTk

        with _PILImage.open(image_path) as source:
            icon = source.convert("RGBA")
        _gui_window_icon = _ImageTk.PhotoImage(icon, master=root)
        root.iconphoto(True, _gui_window_icon)
        if platform.system() == "Windows":
            root.iconbitmap(image_path)
        return True
    except Exception as exc:
        # The icon is cosmetic: startup goes on without it.
        log.warning("Unable to set the application icon: %s", exc)
        return False


# Share of the screen the main window may use. Desktops reserve part of the
# screen for panels, task bars and docks, and the window manager adds a title
# bar; staying well inside these limits keeps the title bar (and its close
# button) on screen with any desktop layout.
GUI_SCREEN_WIDTH_SHARE = 0.94
GUI_SCREEN_HEIGHT_SHARE = 0.80

# The minimum size is this share of the opening size, so the window manager
# can always shrink the window into the free area of the desktop.
GUI_MIN_SIZE_SHARE = 0.75


def grow_to_content(window):
    """Give a window a size that shows its content and fits on the screen, then center it.

    When the content is larger than the usable share of the screen (for
    example with a large UI scale) the UI scale is reduced for this session
    until it fits.
    """
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()
    max_w = int(screen_w * GUI_SCREEN_WIDTH_SHARE)
    max_h = int(screen_h * GUI_SCREEN_HEIGHT_SHARE)
    fit = min(max_w / max(1, window.winfo_reqwidth()), max_h / max(1, window.winfo_reqheight()))
    if fit < 1.0 and window is root:
        _gui_set_scale(ui_scale * fit)
        window.update_idletasks()
    width = min(window.winfo_reqwidth(), max_w)
    height = min(window.winfo_reqheight(), max_h)
    scale = _gui_window_scale()
    # Applying a UI scale makes CustomTkinter pin the minimum and maximum size
    # to the current size and, a second later, restore only the limits set
    # through its own minsize()/maxsize(). Both limits are therefore always
    # set here; otherwise the window manager sees a fixed-size window and may
    # draw its title bar without the close button.
    window.minsize(int(width * GUI_MIN_SIZE_SHARE / scale), int(height * GUI_MIN_SIZE_SHARE / scale))
    window.maxsize(int(screen_w * 2 / scale), int(screen_h * 2 / scale))
    x = max(0, (screen_w - width) // 2)
    y = max(0, (screen_h - height) // 3)
    window.geometry("{}x{}+{}+{}".format(int(width / scale), int(height / scale), x, y))
    # Let Tk apply the final size while the window is still hidden, so the
    # window manager decorates it once, already at its definitive size.
    window.update_idletasks()
    window.deiconify()


def _gui_set_scale(new_scale):
    """Change the UI scale of the running window (used to fit small screens)."""
    global ui_scale
    ui_scale = max(0.65, float(new_scale))
    ctk.set_widget_scaling(ui_scale)
    _gui_fonts["tk_body"].configure(size=-_gui_px(13))
    _gui_fonts["tk_bold"].configure(size=-_gui_px(13))
    _gui_apply_ttk_theme()
    for table in _gui_tables:
        table.apply_column_widths()
    _gui_refresh_combo_geometry()


def _gui_refresh_combo_geometry():
    """Make every drop-down list measure itself again for the current scale.

    A ttk widget that is already on screen keeps the height it calculated
    when it was created; after a change of scale its text would be cut. A
    theme-change notice makes each one recalculate its size from the new
    font and padding.
    """
    for combo in list(_gui_combos):
        try:
            if combo.winfo_exists():
                combo.configure(font=_gui_fonts["tk_body"])
                combo.event_generate("<<ThemeChanged>>")
        except tk.TclError:
            continue


def _gui_apply_ttk_theme():
    """Style the ttk widgets (tables, drop-down lists, scrollbars) to match."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    colors = GUI_COLORS
    body = _gui_fonts["tk_body"]
    bold = _gui_fonts["tk_bold"]

    style.configure(
        "Gui.Treeview",
        background=colors["table"],
        fieldbackground=colors["table"],
        foreground=colors["text"],
        bordercolor=colors["table"],
        lightcolor=colors["table"],
        darkcolor=colors["table"],
        borderwidth=0,
        rowheight=_gui_px(28),
        font=body,
    )
    style.map(
        "Gui.Treeview",
        background=[("selected", colors["accent_soft"])],
        foreground=[("selected", colors["accent"])],
    )
    style.layout("Gui.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure(
        "Gui.Treeview.Heading",
        background=colors["table_head"],
        foreground=colors["muted"],
        bordercolor=colors["table_head"],
        lightcolor=colors["table_head"],
        darkcolor=colors["table_head"],
        relief="flat",
        padding=(_gui_px(8), _gui_px(6)),
        font=bold,
    )
    style.map("Gui.Treeview.Heading", background=[("active", colors["neutral_hover"])])

    style.configure(
        "Gui.TCombobox",
        fieldbackground=colors["field"],
        background=colors["field"],
        foreground=colors["text"],
        bordercolor=colors["field_border"],
        lightcolor=colors["field"],
        darkcolor=colors["field"],
        arrowcolor=colors["muted"],
        arrowsize=_gui_px(15),
        padding=(_gui_px(8), _gui_px(5), _gui_px(4), _gui_px(5)),
        selectbackground=colors["field"],
        selectforeground=colors["text"],
    )
    style.map(
        "Gui.TCombobox",
        fieldbackground=[("readonly", colors["field"]), ("disabled", colors["neutral"])],
        foreground=[("disabled", colors["disabled"]), ("readonly", colors["text"])],
        bordercolor=[("focus", colors["accent"]), ("hover", colors["accent"])],
        arrowcolor=[("disabled", colors["disabled"]), ("hover", colors["accent"])],
        selectbackground=[("readonly", colors["field"])],
        selectforeground=[("readonly", colors["text"])],
    )
    style.configure(
        "Gui.Vertical.TScrollbar",
        background=colors["neutral"],
        troughcolor=colors["field"],
        bordercolor=colors["field"],
        arrowcolor=colors["muted"],
        lightcolor=colors["neutral"],
        darkcolor=colors["neutral"],
    )

    # Drop-down list of every combobox.
    root.option_add("*TCombobox*Listbox.font", body)
    root.option_add("*TCombobox*Listbox.background", colors["field"])
    root.option_add("*TCombobox*Listbox.foreground", colors["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", colors["accent_soft"])
    root.option_add("*TCombobox*Listbox.selectForeground", colors["accent"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)


def create_main_interface():
    """Build every page of the main window.

    Called once at startup, after the settings and the interface texts are
    loaded. Tab order: 0 Main, 1 Monitor, 2 Logbook, 3 Alarm log, 4 Settings.
    """
    global current_call, current_id, current_name, current_location, current_country, current_timer
    global audio_level, vox_threshold, vox_delay, vox_return, tab_bar

    _gui_build_fonts()
    _gui_apply_ttk_theme()

    current_call = tk.StringVar(master=root, value=str(globals().get("my_call") or ""))
    current_id = tk.StringVar(master=root, value="")
    current_name = tk.StringVar(master=root, value="")
    current_location = tk.StringVar(master=root, value="")
    current_country = tk.StringVar(master=root, value="")
    current_timer = tk.StringVar(master=root, value="000")
    audio_level = _gui_register("audio_level", tk.IntVar(master=root, value=0))
    vox_threshold = tk.IntVar(master=root, value=200)
    vox_delay = tk.IntVar(master=root, value=50)
    vox_return = tk.IntVar(master=root, value=5)

    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(2, weight=1)

    _gui_build_header(root).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

    pages = ctk.CTkFrame(root, fg_color="transparent")
    pages.grid_columnconfigure(0, weight=1)
    pages.grid_rowconfigure(0, weight=1)
    tab_bar = _GuiTabBar(root, pages, on_tab_change)
    tab_bar.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))
    pages.grid(row=2, column=0, sticky="nsew", padx=16)

    tab_bar.add(_gui_build_main_page(pages), tr("tab.main"))
    tab_bar.add(_gui_build_monitor_page(pages), tr("tab.monitor"))
    tab_bar.add(_gui_build_logbook_page(pages), tr("logbook.title"))
    tab_bar.add(_gui_build_alarm_page(pages), tr("alarms.log_title"))
    tab_bar.add(_gui_build_settings_page(pages), tr("tab.settings"))
    tab_bar.select(0)

    _gui_build_transmit_bar(root).grid(row=3, column=0, sticky="ew", padx=16, pady=(10, 14))

    root.bind_all("<Control-q>", lambda _event: on_closing())
    _gui_tick_clock()
    try:
        initialize_local_station_card()
    except Exception:
        log.exception("Could not initialize the station card")
    root.after_idle(lambda: publish_station_identity(str(globals().get("my_call") or "")))
    return tab_bar


def _gui_fixed_text_width(font, prefix):
    """Width (in CustomTkinter units) that fits prefix plus any HH:MM:SS time.

    Every digit is measured and the widest one is used for all six positions,
    so the result fits whatever time is shown.
    """
    widest = max("0123456789", key=font.measure)
    sample = prefix + "{0}{0}:{0}{0}:{0}{0}".format(widest)
    # CTkFont measures at its unscaled size, which is the unit CTk widths use.
    return font.measure(sample) + 6


def _gui_build_header(parent):
    """Top bar: application name, connection status and the two clocks."""
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.grid_columnconfigure(1, weight=1)

    brand = ctk.CTkFrame(header, fg_color="transparent")
    brand.grid(row=0, column=0, sticky="w")
    _gui_label(brand, GUI_APP_NAME, font="brand", color="accent").grid(row=0, column=0, sticky="w")
    _gui_label(
        brand,
        "{}  v{}".format(tr("app.title"), GUI_APP_VERSION),
        font="small",
        color="muted",
    ).grid(row=1, column=0, sticky="w")

    status = ctk.CTkLabel(
        header,
        text="",
        font=_gui_fonts["body_bold"],
        corner_radius=14,
        height=30,
        width=300,
        fg_color=GUI_COLORS["neutral"],
        text_color=GUI_COLORS["muted"],
    )
    status.grid(row=0, column=1, padx=16)
    _gui_widgets["status"] = status

    clocks = ctk.CTkFrame(header, fg_color=GUI_COLORS["card"], corner_radius=16, border_width=1, border_color=GUI_COLORS["card_border"])
    clocks.grid(row=0, column=2, sticky="e")
    # Orbitron digits have different widths, so each clock gets a fixed width
    # that fits its widest possible time; the header never moves as it ticks.
    utc_width = _gui_fixed_text_width(_gui_fonts["clock"], "UTC ")
    local_width = _gui_fixed_text_width(_gui_fonts["clock"], tr("clock.local") + " ")
    utc = _gui_label(clocks, "", font="clock", color="accent", width=utc_width, anchor="w")
    utc.grid(row=0, column=0, padx=(14, 10), pady=6)
    local = _gui_label(clocks, "", font="clock", color="text", width=local_width, anchor="w")
    local.grid(row=0, column=1, padx=(10, 14), pady=6)
    _gui_widgets["clock_utc"] = utc
    _gui_widgets["clock_local"] = local
    return header


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

GUI_PHOTO_SIZE = (104, 104)
GUI_FLAG_SIZE = (78, 78)


def _gui_build_main_page(parent):
    """Main tab: station card, last heard list, room selection and online list."""
    page = ctk.CTkFrame(parent, fg_color="transparent")
    page.grid_columnconfigure(0, weight=3)
    page.grid_columnconfigure(1, weight=2)
    page.grid_rowconfigure(1, weight=1)

    _gui_build_station_card(page).grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
    _gui_build_room_card(page).grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
    _gui_build_last_heard_card(page).grid(row=1, column=0, sticky="nsew", padx=(0, 8))
    _gui_build_online_card(page).grid(row=1, column=1, sticky="nsew", padx=(8, 0))
    return page


def _gui_build_station_card(parent):
    """Card with the picture, flag and identity of the station being heard."""
    global photo_label, flag_label
    card = _GuiCard(parent, title=tr("main.station_heard"))
    body = card.body
    body.grid_columnconfigure(2, weight=1)

    photo_label = ctk.CTkLabel(body, text="", image=_gui_blank_image(GUI_PHOTO_SIZE), cursor="hand2")
    photo_label.grid(row=0, column=0, rowspan=2, sticky="nw")
    photo_label.callsign = ""
    photo_label.bind("<Button-1>", on_picture_click)
    _GuiTooltip(photo_label, "QRZ.com")

    flag_box = ctk.CTkFrame(body, fg_color="transparent")
    flag_box.grid(row=0, column=1, rowspan=2, sticky="n", padx=(12, 12))
    flag_label = ctk.CTkLabel(flag_box, text="", image=_gui_blank_image(GUI_FLAG_SIZE))
    flag_label.grid(row=0, column=0)
    ctk.CTkLabel(
        flag_box,
        textvariable=current_country,
        font=_gui_fonts["small"],
        text_color=GUI_COLORS["muted"],
        wraplength=110,
    ).grid(row=1, column=0)

    identity = ctk.CTkFrame(body, fg_color="transparent")
    identity.grid(row=0, column=2, sticky="nw")
    call_label = ctk.CTkLabel(
        identity,
        textvariable=current_call,
        font=_gui_fonts["callsign"],
        text_color=GUI_COLORS["accent"],
        cursor="hand2",
        anchor="w",
    )
    call_label.grid(row=0, column=0, sticky="w")
    call_label.bind("<Button-1>", on_callsign_click)
    _GuiTooltip(call_label, tr("logbook.add_title"))
    _gui_label(identity, "", font="identity", color="text", textvariable=current_id, anchor="w").grid(row=1, column=0, sticky="w")

    details = ctk.CTkFrame(body, fg_color="transparent")
    details.grid(row=1, column=2, columnspan=2, sticky="sw", pady=(6, 0))
    _gui_label(details, "", font="body_bold", color="text", textvariable=current_name, anchor="w", wraplength=360, justify="left").grid(row=0, column=0, sticky="w")
    _gui_label(details, "", font="caption", color="muted", textvariable=current_location, anchor="w", wraplength=360, justify="left").grid(row=1, column=0, sticky="w")

    actions = card.title_tools
    bell = _GuiButton(
        actions,
        role="ghost",
        text="",
        width=34,
        height=30,
        image=_gui_load_image(resource_path("data/bell.png"), (18, 18)),
        command=open_alarm_editor,
    )
    bell.grid(row=0, column=0)
    _GuiTooltip(bell, tr("alarms.title"))
    return card


def _gui_build_room_card(parent):
    """Card with the room group filter, the room list and the connect controls."""
    global group_picker, room_picker, group_choice, room_choice
    card = _GuiCard(parent, title=tr("main.my_station"))
    body = card.body
    body.grid_columnconfigure(0, weight=1)
    body.grid_columnconfigure(1, weight=1)

    # Group and room selectors side by side.
    _gui_label(body, tr("rooms.group"), font="small", color="muted").grid(row=0, column=0, sticky="w")
    _gui_label(body, tr("field.room"), font="small", color="muted").grid(row=0, column=1, sticky="w", padx=(8, 0))
    group_choice = tk.StringVar(master=root)
    group_picker = _GuiCombo(body, variable=group_choice, width=12, command=group_changed)
    group_picker.grid(row=1, column=0, sticky="ew", pady=(0, 10))
    _gui_register("group_picker", group_picker)

    room_row = ctk.CTkFrame(body, fg_color="transparent")
    room_row.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))
    room_row.grid_columnconfigure(0, weight=1)
    room_choice = _gui_register("room_choice", tk.StringVar(master=root))
    # The core needs the chosen room to connect, auto-start and list the stations online.
    room_choice.trace_add("write", lambda *_args: set_selected_room(room_choice.get()))
    room_picker = _GuiCombo(room_row, variable=room_choice, width=10, command=room_changed)
    room_picker.grid(row=0, column=0, sticky="ew")
    star = _GuiButton(room_row, role="ghost", text="\u2606", width=34, height=30, font=_gui_fonts["button_big"], command=_gui_toggle_favorite)
    star.grid(row=0, column=1, padx=(6, 0))
    refresh_rooms = _GuiButton(
        room_row, role="ghost", text="\u21bb", width=34, height=30, command=_gui_refresh_room_lists
    )
    refresh_rooms.grid(row=0, column=2, padx=(4, 0))
    _GuiTooltip(refresh_rooms, tr("rooms.reload_tip"))
    _gui_widgets["favorite_star"] = star
    _GuiTooltip(star, "{} / {}".format(tr("rooms.bookmark_add"), tr("rooms.bookmark_remove")))
    room_choice.trace_add("write", lambda *_args: _gui_refresh_star())

    favorites_menu = _gui_context_menu()
    favorites_menu.add_command(label=tr("rooms.bookmark_add"), command=add_bookmark_action)
    favorites_menu.add_command(label=tr("rooms.bookmark_remove"), command=remove_bookmark_action)
    _gui_bind_right_click(room_picker, lambda event: _gui_show_menu(favorites_menu, event) if room_picker.get() else None)

    connect = _GuiButton(
        body,
        role="accent",
        text=tr("main.connect"),
        font=_gui_fonts["button_big"],
        height=44,
        corner_radius=18,
        command=toggle_connection,
    )
    connect.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    _gui_register("connect_button", connect)

    rec = _GuiButton(body, text="REC", command=toggle_recording_button)
    rec.grid(row=3, column=0, sticky="ew", padx=(0, 4))
    _gui_register("rec_button", rec)

    scan_row = ctk.CTkFrame(body, fg_color="transparent")
    scan_row.grid(row=3, column=1, sticky="ew", padx=(4, 0))
    scan_row.grid_columnconfigure(0, weight=1)
    scan = _GuiButton(scan_row, text="SCAN", command=toggle_scan)
    scan.grid(row=0, column=0, sticky="ew")
    _gui_register("scan_button", scan)
    manage = _GuiButton(scan_row, text="\u22ef", width=34, command=open_scan_editor)
    manage.grid(row=0, column=1, padx=(4, 0))
    _GuiTooltip(manage, tr("scan.manage"))
    scan_menu = _gui_context_menu()
    scan_menu.add_command(label=tr("scan.manage"), command=open_scan_editor)
    _gui_bind_right_click(scan, lambda event: _gui_show_menu(scan_menu, event))
    return card


def _gui_build_last_heard_card(parent):
    """Card listing the transmissions heard in the current session."""
    global last_heard_tree
    card = _GuiCard(parent, title=tr("main.last_heard"))
    card.body.grid_columnconfigure(0, weight=1)
    card.body.grid_rowconfigure(0, weight=1)
    columns = ("time", "call", "name", "duration")
    headings = (
        tr("field.time"),
        tr("field.callsign"),
        tr("field.name"),
        tr("field.duration"),
    )
    table = _GuiTable(card.body, columns, headings, (90, 110, 170, 80), anchors=("w", "w", "w", "e"), height=7)
    table.grid(row=0, column=0, sticky="nsew")
    last_heard_tree = _gui_register("last_heard_tree", table.tree)

    menu = _gui_context_menu()
    menu.add_command(label="QRZ.com", command=open_qrz_page)
    menu.add_command(label="aprs.fi", command=open_aprs_fi_page)
    menu.add_command(label="Brandmeister", command=open_brandmeister_page)
    menu.add_command(label="HamData", command=open_hamdata_page)
    menu.add_separator()
    menu.add_command(label=tr("logbook.add_title"), command=add_selected_to_logbook)

    def open_menu(event):
        row = last_heard_tree.identify_row(event.y)
        if row:
            last_heard_tree.selection_set(row)
            _gui_show_menu(menu, event)

    _gui_bind_right_click(last_heard_tree, open_menu)
    last_heard_tree.bind("<Double-1>", lambda _event: open_qrz_page())
    return card


def _gui_build_online_card(parent):
    """Card listing the stations connected to the selected room."""
    global online_tree
    card = _GuiCard(parent, title=tr("main.stations_in_room"))
    _gui_widgets["online_card"] = card
    card.body.grid_columnconfigure(0, weight=1)
    card.body.grid_rowconfigure(0, weight=1)
    table = _GuiTable(card.body, ("call",), (tr("field.callsign"),), (150,), height=7)
    table.grid(row=0, column=0, sticky="nsew")
    online_tree = _gui_register("online_tree", table.tree)
    online_tree.bind("<Double-1>", on_online_double_click)
    return card


def _gui_build_transmit_bar(parent):
    """Bottom bar: audio level meter, push-to-talk button, timer and mute."""
    global timer_label, mute_button, transmit_button
    bar = _GuiCard(parent, padding=12)
    body = bar.body
    body.grid_columnconfigure(0, weight=1)

    meter = ctk.CTkProgressBar(
        body,
        height=10,
        corner_radius=5,
        fg_color=GUI_COLORS["neutral"],
        progress_color=GUI_COLORS["accent"],
    )
    meter.set(0)
    meter.configure(progress_color=GUI_COLORS["neutral"])
    meter.grid(row=0, column=0, sticky="ew", padx=(4, 4), pady=(0, 10))
    _gui_widgets["meter"] = meter
    audio_level.trace_add("write", lambda *_args: _gui_update_meter())

    transmit_button = _GuiButton(
        body,
        role="neutral",
        text=str(globals().get("my_call") or ""),
        font=_gui_fonts["ptt"],
        height=58,
        corner_radius=22,
        state="disabled",
        command=toggle_transmit,
    )
    transmit_button.grid(row=1, column=0, sticky="ew")
    _gui_register("transmit_button", transmit_button)

    side = ctk.CTkFrame(body, fg_color="transparent")
    side.grid(row=0, column=1, rowspan=2, sticky="nse", padx=(14, 0))
    timer_label = ctk.CTkLabel(
        side,
        textvariable=current_timer,
        font=_gui_fonts["timer"],
        text_color=GUI_COLORS["accent"],
        fg_color=GUI_COLORS["neutral"],
        corner_radius=14,
        width=86,
        height=40,
    )
    timer_label.grid(row=0, column=0, pady=(0, 8))
    mute_button = _GuiButton(
        side,
        role="neutral",
        text="",
        width=86,
        height=40,
        image=_gui_load_image(resource_path("data/speaker_on.png"), (26, 26), knockout_white=True),
        command=toggle_mute_button,
    )
    mute_button.grid(row=1, column=0)
    _GuiTooltip(mute_button, tr("main.mute_tip"))
    return bar


def _gui_update_meter():
    """Show the audio level (0-100) on the meter, colored by RX or TX."""
    meter = _gui_widgets.get("meter")
    if meter is None:
        return
    try:
        level = int(audio_level.get())
    except (tk.TclError, ValueError):
        level = 0
    level = max(0, min(100, level))
    meter.set(level / 100.0)
    status = globals().get("link_state", 0)
    if level == 0:
        # The bar keeps a small rounded cap at zero; paint it like the track.
        color = GUI_COLORS["neutral"]
    elif status == 2:
        color = GUI_COLORS["danger"]
    elif status == 1:
        color = GUI_COLORS["info"]
    else:
        color = GUI_COLORS["accent"]
    meter.configure(progress_color=color)


# ---------------------------------------------------------------------------
# Station card
# ---------------------------------------------------------------------------

@_gui_on_main_thread()
def gui_set_station_identity(identity, name, location):
    """Show the DMR ID, name and address of the station on the card."""
    current_id.set(str(identity or ""))
    current_name.set(str(name or ""))
    current_location.set(str(location or ""))


def initialize_local_station_card():
    """Show our own station on the card as soon as the window opens.

    A cached local picture (or the generic placeholder) and the flag derived
    from the callsign prefix appear immediately; a QRZ.com picture found later
    replaces the photo.
    """
    call = str(globals().get("my_call") or "").strip().upper()
    if not call or call == "NOCALL":
        return
    try:
        picture = local_picture_path(call) or person_icon_path()
    except Exception:
        picture = None
    show_station_picture(call, picture, photo_label)
    show_station_flag(call, flag_label)


@_gui_on_main_thread()
def show_station_picture(call, picture, in_label):
    """Show the picture file of a station; the generic person icon when it cannot be read."""
    person_icon = resource_path(os.path.join("data", "station.png"))
    if not picture or os.path.normcase(os.path.abspath(picture)) == os.path.normcase(os.path.abspath(person_icon)):
        # The generic icon is prepared once and reused for every station.
        image = _gui_load_image(person_icon, GUI_PHOTO_SIZE)
    else:
        source = _gui_open_picture(picture)
        if source is not None:
            image = gui_photo_image(_gui_rounded(_gui_fit_image(source, GUI_PHOTO_SIZE), 16))
        else:
            image = _gui_load_image(person_icon, GUI_PHOTO_SIZE)
    in_label.configure(image=image or _gui_blank_image(GUI_PHOTO_SIZE), text="")
    in_label.callsign = str(call or "")
    current_call.set(str(call or ""))


@_gui_on_main_thread()
def show_station_flag(call, in_label):
    """Show the flag and country name that match the callsign prefix."""
    try:
        country = prefix_info(call)
    except Exception:
        country = {}
    image = None
    if country:
        flag = _gui_open_picture(flag_picture_path(country.get("flag", "")))
        if flag is not None:
            image = gui_photo_image(_gui_rounded(_gui_fit_image(flag, GUI_FLAG_SIZE), 10))
    in_label.configure(image=image or _gui_blank_image(GUI_FLAG_SIZE), text="")
    current_country.set(str(country.get("country", "")) if country else "")


def on_picture_click(_event=None):
    """Open the QRZ.com page of the station shown on the card."""
    call = str(getattr(photo_label, "callsign", "") or "")
    if call:
        webbrowser.open_new_tab("https://www.qrz.com/db/" + call)


def on_callsign_click(_event=None):
    """Add the station shown on the card to the logbook (never our own call)."""
    call = str(current_call.get() or "").strip()
    if call and call != str(globals().get("callsign", "")):
        _gui_add_to_logbook(call)


def open_alarm_editor():
    """Open the callsign alarm list editor."""
    dialog = AlarmListDialog(root, tr("alarms.title"))
    root.wait_window(dialog)


def toggle_mute_button():
    """Mute or unmute the received audio."""
    set_mute(not speaker_muted)
    icon = "data/speaker_off.png" if speaker_muted else "data/speaker_on.png"
    mute_button.configure(image=_gui_load_image(resource_path(icon), (26, 26), knockout_white=True))
    mute_button.set_role("danger_soft" if speaker_muted else "neutral")


# ---------------------------------------------------------------------------
# Rooms and favorites
# ---------------------------------------------------------------------------

def _gui_room_names(predicate=None):
    """Sorted, unique, upper-case names of the known rooms that pass a test."""
    names = set()
    for item in room_list or []:
        try:
            if predicate is None or predicate(item):
                name = str(item.get("room", "")).upper().strip()
                if name:
                    names.add(name)
        except AttributeError:
            continue
    return sorted(names)


@_gui_on_main_thread()
def fill_room_list(country, initial_load=False):
    """Fill the room list for the chosen group.

    Groups: ALL (every room), PEANUT (every non-local room), the bookmarks
    entry (rooms saved as favorites on this server) or a country name.
    On the initial load the auto-start room is preselected when it exists.
    """
    country = str(country or "")
    all_rooms = _gui_room_names()

    # The auto-start selector always lists every room.
    auto_combo = _gui_registry.get("form_auto_room")
    if auto_combo is not None:
        auto_values = [""] + all_rooms
        auto_combo.set_values(auto_values)
        if auto_room and auto_room in auto_values:
            auto_combo.set(auto_room)
        elif auto_combo.get() not in auto_values:
            auto_combo.set("")

    if country == "ALL":
        rooms = all_rooms
    elif country == "PEANUT":
        rooms = _gui_room_names(lambda item: item.get("type") != "local")
    elif country == tr("rooms.bookmarks"):
        known = set(all_rooms)
        rooms = sorted({str(row[0]).upper().strip() for row in bookmarked_rooms() if str(row[0]).upper().strip() in known})
        if str(globals().get("my_call", "")) in DEVELOPER_CALLS:
            rooms.extend(sorted(DEVELOPER_ROOMS))
    else:
        wanted = country.strip().lower()
        rooms = _gui_room_names(lambda item: str(item.get("country", "")).strip().lower() == wanted)

    room_picker.set_values(rooms)
    preferred = auto_combo.get() if (initial_load and auto_combo is not None) else ""
    if preferred and preferred in rooms:
        room_picker.set(preferred)
    elif rooms:
        room_picker.set(rooms[0])
    else:
        room_picker.set("")
    _gui_refresh_star()


def _gui_refresh_room_lists():
    """Ask the core to load the server and room lists again right now."""
    refresh_server_lists()
    popup_toast(tr("rooms.reloading"), "accent")


def group_changed(_event=None):
    """A new room group was chosen: show its rooms.

    Browsing groups never moves the station: a room is entered only when the
    user picks one in the room list.
    """
    fill_room_list(group_choice.get())


def enter_selected_room():
    """Make the selected room the active one; the core announces it when connected.

    When the core refuses (our own transmission is on), the list goes back
    to the room in use.
    """
    if not enter_room(room_choice.get()) and active_room:
        room_picker.set(active_room)


def room_changed(_event=None):
    enter_selected_room()


def _gui_is_favorite(room):
    try:
        return bool(find_bookmark(room))
    except Exception:
        return False


def _gui_refresh_star():
    """Draw the star filled when the selected room is a bookmark."""
    star = _gui_widgets.get("favorite_star")
    if star is None:
        return
    room = str(room_choice.get()).strip()
    filled = bool(room) and _gui_is_favorite(room)
    star.configure(text="\u2605" if filled else "\u2606", text_color=GUI_COLORS["warning"] if filled else GUI_COLORS["muted"])


def add_bookmark_action():
    """Bookmark the selected room on the current server."""
    room = str(room_picker.get()).strip()
    if room and room not in DEVELOPER_ROOMS and not _gui_is_favorite(room):
        add_bookmark(room)
        popup_toast(tr("rooms.bookmark_added").format(room), "accent")
    _gui_refresh_star()


def remove_bookmark_action():
    """Remove the selected room from the bookmarks of the current server."""
    room = str(room_picker.get()).strip()
    if room and room not in DEVELOPER_ROOMS and _gui_is_favorite(room):
        remove_bookmark(room)
        popup_toast(tr("rooms.bookmark_removed").format(room), "danger")
        if group_picker.get() == tr("rooms.bookmarks"):
            fill_room_list(tr("rooms.bookmarks"))
    _gui_refresh_star()


def _gui_toggle_favorite():
    room = str(room_picker.get()).strip()
    if not room:
        return
    if _gui_is_favorite(room):
        remove_bookmark_action()
    else:
        add_bookmark_action()


# ---------------------------------------------------------------------------
# Last heard and online lists
# ---------------------------------------------------------------------------

def selected_last_heard_call():
    """Callsign of the selected last heard row as (is_valid, callsign)."""
    selection = last_heard_tree.selection()
    if not selection:
        return (False, "")
    values = last_heard_tree.item(selection[0]).get("values") or []
    call = str(values[1]).strip() if len(values) > 1 else ""
    return (bool(call) and not call.isdigit(), call)


def lookup_call_on_web(url):
    """Open a web page about the selected last heard station (url + callsign)."""
    (is_valid, call) = selected_last_heard_call()
    if is_valid:
        webbrowser.open_new_tab(url + urllib.parse.quote(call, safe="/"))


def open_qrz_page():
    lookup_call_on_web("https://www.qrz.com/db/")


def open_aprs_fi_page():
    lookup_call_on_web("https://aprs.fi/#!call=a%2F")


def open_brandmeister_page():
    lookup_call_on_web("https://brandmeister.network/index.php?page=profile&call=")


def open_hamdata_page():
    lookup_call_on_web("http://hamdata.com/getcall.html?callsign=")


def add_selected_to_logbook():
    """Add the selected last heard station to the logbook."""
    is_valid, call = selected_last_heard_call()
    if is_valid:
        _gui_add_to_logbook(call)


def on_online_double_click(_event=None):
    """Open the QRZ.com page of the double-clicked online station."""
    selection = online_tree.selection()
    if selection:
        values = online_tree.item(selection[0], "values")
        call = str(values[0]).strip() if values else ""
        if len(call) > 3:
            webbrowser.open_new_tab("https://www.qrz.com/db/" + call)


def clear_all_online():
    """Empty the online station list."""
    online_tree.delete(*online_tree.get_children())
    _gui_refresh_online_count()


def _gui_refresh_online_count():
    card = _gui_widgets.get("online_card")
    if card is not None:
        count = len(online_tree.get_children())
        title = tr("main.stations_in_room")
        card.set_title("{}  \u00b7  {}".format(title, count) if count else title)


def _gui_restripe(tree):
    """Give every other row a slightly darker background."""
    for index, item in enumerate(tree.get_children()):
        tags = [tag for tag in tree.item(item, "tags") if tag != "odd"]
        if index % 2:
            tags.append("odd")
        tree.item(item, tags=tags)


# ---------------------------------------------------------------------------
# Room scanner and audio recording buttons
# ---------------------------------------------------------------------------

def open_scan_editor():
    """Open the editor of the rooms visited by the scanner."""
    dialog = ScanRoomsDialog(root, tr("scan.manage"))
    root.wait_window(dialog)


def toggle_recording_button():
    """REC button: start recording, or ask where to save the recording and stop."""
    rec_button = _gui_registry["rec_button"]
    if recording_active:
        if has_recorded_audio():
            file_name = filedialog.asksaveasfilename(
                parent=root, filetypes=[("WAV Audio Files", "*.wav")], defaultextension=".wav"
            )
            if file_name:
                try:
                    save_recording(file_name)
                except (OSError, wave.Error) as exc:
                    gui_show_error("REC", str(exc), parent=root)
                rec_button.update_look(role="neutral")
        else:
            stop_recording()
            rec_button.update_look(role="neutral")
    else:
        start_recording()
        rec_button.update_look(role="danger")


# ---------------------------------------------------------------------------
# Monitor page (active transmissions on the server)
# ---------------------------------------------------------------------------

def _gui_build_monitor_page(parent):
    """Monitor tab: active transmissions, filtered by country."""
    global monitor_frame, monitor_filter, monitor_tree
    page = ctk.CTkFrame(parent, fg_color="transparent")
    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(0, weight=1)
    card = _GuiCard(page, title=tr("tab.monitor"))
    card.grid(row=0, column=0, sticky="nsew")
    monitor_frame = card.body
    monitor_frame.grid_columnconfigure(1, weight=1)
    monitor_frame.grid_rowconfigure(1, weight=1)

    monitor_filter = _gui_register("monitor_filter", _GuiGroupFilter(monitor_frame, on_change=_gui_forget_monitor_rows))
    monitor_filter.grid(row=0, column=0, sticky="w", pady=(0, 8))
    _gui_label(monitor_frame, tr("monitor.double_click_hint"), font="caption", color="muted").grid(
        row=0, column=1, sticky="e", pady=(0, 8)
    )

    columns = ("call", "message", "room", "time")
    headings = (
        tr("field.callsign"),
        tr("field.message"),
        tr("field.room"),
        tr("monitor.started"),
    )
    table = _GuiTable(monitor_frame, columns, headings, (130, 260, 150, 110), height=12)
    table.grid(row=1, column=0, columnspan=2, sticky="nsew")
    monitor_tree = _gui_register("monitor_tree", table.tree)
    monitor_tree.bind("<Double-1>", on_monitor_double_click)
    return page


def _gui_forget_monitor_rows():
    """Make the next Monitor refresh redraw the table (the filter changed)."""
    global _gui_monitor_rows
    _gui_monitor_rows = None


def _gui_monitor_filters():
    """Lower-case names of the groups ticked in the Monitor filter."""
    return [name.strip().lower() for name in monitor_filter.ticked_groups() if name.strip()]


def _gui_room_matches(room, filters):
    """True when a room belongs to one of the ticked groups (no groups = all)."""
    if not filters or "all" in filters:
        return True
    favorites_key = tr("rooms.bookmarks").lower()
    for item in room_list or []:
        if not isinstance(item, dict) or str(item.get("room", "")).strip().upper() != str(room).strip().upper():
            continue
        if str(item.get("country", "")).strip().lower() in filters:
            return True
        if "peanut" in filters and item.get("type") != "local":
            return True
    if favorites_key in filters and _gui_is_favorite(str(room).strip().upper()):
        return True
    return False


# Time of day inside the server's startPTT2 text, whatever date format the
# server uses (servers differ in how they write the date part).
_GUI_CLOCK_PATTERN = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})")


def _gui_transmission_time(raw):
    """The time of day (HH:MM:SS) a transmission started, from the server's startPTT2 text.

    The time is shown as the server writes it (server time). A text without
    a recognizable time is shown unchanged.
    """
    text = str(raw)
    match = _GUI_CLOCK_PATTERN.search(text)
    if match is None:
        return text
    return "{:02d}:{}:{}".format(int(match.group(1)), match.group(2), match.group(3))


def refresh_monitor_table():
    """Refresh the Monitor table once per second from the latest server data."""
    global _gui_monitor_rows
    try:
        filters = _gui_monitor_filters()
        rows = []
        for item in active_transmissions or []:
            if not isinstance(item, dict):
                continue
            room = str(item.get("room", ""))
            if room in DEVELOPER_ROOMS or not _gui_room_matches(room, filters):
                continue
            rows.append((item.get("Call", ""), str(item.get("message", "")).strip(), room, _gui_transmission_time(item.get("startPTT2", ""))))
        rows.reverse()
        if rows != _gui_monitor_rows:
            _gui_monitor_rows = rows
            selected = [monitor_tree.item(i, "values") for i in monitor_tree.selection()]
            monitor_tree.delete(*monitor_tree.get_children())
            for row in rows:
                item = monitor_tree.insert("", "end", values=row)
                if tuple(str(v) for v in row) in [tuple(str(v) for v in s) for s in selected]:
                    monitor_tree.selection_set(item)
            _gui_restripe(monitor_tree)
    except Exception:
        log.debug("Monitor refresh failed", exc_info=True)
    finally:
        if _gui_alive:
            root.after(1000, refresh_monitor_table)


def on_monitor_double_click(_event=None):
    """Select the double-clicked room on the Main tab and enter it when connected."""
    selection = monitor_tree.selection()
    if not selection:
        return
    values = monitor_tree.item(selection[0], "values")
    room = str(values[2]).strip() if len(values) > 2 else ""
    if not room or room in DEVELOPER_ROOMS:
        return
    if ptt_pressed or tx_active:
        # The core explains why the room cannot change now.
        enter_room(room)
        return
    group_picker.set("ALL")
    fill_room_list("ALL")
    room_picker.set(room)
    enter_selected_room()
    popup_toast(tr("rooms.selected").format(room), "accent")


def on_tab_change(*_event):
    """Poll the active transmissions only while the Monitor tab is visible."""
    if tab_bar.index() == 1:
        start_active_qso_monitor()
    else:
        stop_active_qso_monitor()


# ---------------------------------------------------------------------------
# Logbook page
# ---------------------------------------------------------------------------

def _gui_build_logbook_page(parent):
    """Logbook tab: QSO table plus record and export actions."""
    global logbook_tree
    page = ctk.CTkFrame(parent, fg_color="transparent")
    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(0, weight=1)

    card = _GuiCard(page, title=tr("logbook.title"))
    card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    card.body.grid_columnconfigure(0, weight=1)
    card.body.grid_rowconfigure(0, weight=1)
    columns = ("call", "name", "date", "time", "band", "comment", "id")
    headings = (
        tr("field.callsign"),
        tr("field.name"),
        tr("field.date"),
        tr("field.time"),
        tr("field.band"),
        tr("field.comment"),
        "id",
    )
    table = _GuiTable(
        card.body,
        columns,
        headings,
        (120, 200, 100, 70, 70, 160, 40),
        display=("call", "name", "date", "time", "band", "comment"),
        height=12,
    )
    table.grid(row=0, column=0, sticky="nsew")
    logbook_tree = _gui_register("logbook_tree", table.tree)
    logbook_tree.bind("<Double-1>", lambda _event: edit_record_dialog())
    logbook_tree.bind("<Delete>", lambda _event: delete_record_dialog())

    actions = _GuiCard(page, padding=12)
    actions.grid(row=0, column=1, sticky="ns")
    buttons = (
        (tr("common.add"), "accent", lambda: add_record_dialog()),
        (tr("common.edit"), "neutral", lambda: edit_record_dialog()),
        (tr("common.remove"), "neutral", lambda: delete_record_dialog()),
        (tr("logbook.clear"), "danger_soft", lambda: clear_logbook_dialog()),
        None,
        ("ADIF", "success", lambda: export_adif_dialog()),
        ("eQSL", "success", lambda: upload_eqsl_dialog()),
        ("QRZ", "success", lambda: upload_qrz_dialog()),
    )
    row = 0
    for spec in buttons:
        if spec is None:
            ctk.CTkFrame(actions.body, height=2, fg_color=GUI_COLORS["card_border"]).grid(row=row, column=0, sticky="ew", pady=10)
        else:
            text, role, command = spec
            _GuiButton(actions.body, role=role, text=text.replace("\n", " "), width=120, command=command).grid(row=row, column=0, sticky="ew", pady=3)
        row += 1
    return page


def reload_logbook_table():
    """Fill the logbook table with every record of the database."""
    logbook_tree.delete(*logbook_tree.get_children())
    for row in logbook_rows():
        ui_insert_tree_row("logbook_tree", row, parent="", index="end")
    select_logbook_row(0, only_if_none_selected=True)


def select_logbook_row(item, only_if_none_selected=False):
    """Select a logbook row by index; with only_if_none_selected, only when no row is selected yet."""
    children = logbook_tree.get_children()
    if not children:
        return
    try:
        child = children[item]
    except IndexError:
        return
    if only_if_none_selected and logbook_tree.selection():
        return
    logbook_tree.selection_set(child)
    logbook_tree.focus(child)
    logbook_tree.see(child)


def _gui_selected_record():
    """(row index, record id) of the selected logbook row, or (None, None)."""
    selection = logbook_tree.selection()
    if not selection:
        return (None, None)
    values = logbook_tree.item(selection[0], "values")
    record_id = values[6] if len(values) > 6 else None
    return (logbook_tree.index(selection[0]), record_id)


def _gui_logbook_empty():
    if logbook_tree.get_children():
        return False
    gui_show_info(tr("logbook.title"), tr("logbook.empty"), parent=root)
    return True


def _gui_add_to_logbook(call, name=None):
    """Open the record form prefilled with a callsign and save it on Accept."""
    if name is None:
        name = (radioid_cache.get(call) or {}).get("full_name", "")
        if name == tr("station.unknown"):
            name = ""
    dialog = LogbookRecordDialog(root, tr("logbook.add_title"), False, call, name)
    root.wait_window(dialog)
    if dialog.saved:
        reload_logbook_table()
        select_logbook_row(-1)
        popup_toast(tr("logbook.added"), "accent")


def add_record_dialog():
    """Add a new logbook record."""
    dialog = LogbookRecordDialog(root, tr("logbook.add_title"), False)
    root.wait_window(dialog)
    if dialog.saved:
        reload_logbook_table()
        select_logbook_row(-1)
        popup_toast(tr("logbook.added"), "accent")


def edit_record_dialog():
    """Edit the selected logbook record."""
    if _gui_logbook_empty():
        return
    index, record_id = _gui_selected_record()
    if record_id is None:
        gui_show_info(tr("logbook.title"), tr("logbook.select_first"), parent=root)
        return
    dialog = LogbookRecordDialog(root, tr("logbook.edit_title"), record_id)
    root.wait_window(dialog)
    if dialog.saved:
        reload_logbook_table()
        select_logbook_row(index)
        popup_toast(tr("logbook.updated"), "accent")


def delete_record_dialog():
    """Delete the selected logbook record after confirmation."""
    if _gui_logbook_empty():
        return
    index, record_id = _gui_selected_record()
    if record_id is None:
        gui_show_info(tr("logbook.title"), tr("logbook.select_first"), parent=root)
        return
    if not gui_ask_yes_no(tr("logbook.title"), tr("logbook.confirm_delete"), parent=root):
        return
    delete_record(record_id)
    reload_logbook_table()
    count = len(logbook_tree.get_children())
    if count:
        select_logbook_row(min(index, count - 1))
    popup_toast(tr("logbook.deleted"), "danger")


def clear_logbook_dialog():
    """Start a new logbook: delete every record after confirmation."""
    if _gui_logbook_empty():
        return
    if not gui_ask_yes_no(tr("logbook.title"), tr("logbook.confirm_delete_all"), parent=root):
        return
    delete_all_records()
    reload_logbook_table()
    popup_toast(tr("logbook.all_deleted"), "danger")


def export_adif_dialog():
    """Export the whole logbook to an ADIF file."""
    if _gui_logbook_empty():
        return
    file_name = filedialog.asksaveasfilename(
        parent=root,
        defaultextension=".adi",
        filetypes=[("ADIF file", "*.adi"), ("ADIF file", "*.adif"), ("All files", "*.*")],
    )
    if not file_name:
        return
    try:
        with open(file_name, "w", encoding="ascii", errors="replace", newline="\n") as adif_file:
            adif_file.write(export_adif_text())
    except OSError as exc:
        gui_show_error(tr("logbook.title"), str(exc), parent=root)
        return
    popup_toast(tr("logbook.adif_saved").format(file_name), "accent")


def _gui_nothing_to_upload(service):
    """Tell the user when every contact was already uploaded to a service."""
    if count_pending_uploads(service):
        return False
    gui_show_info(
        tr("logbook.title"),
        tr("logbook.nothing_to_upload"),
        parent=root,
    )
    return True


def upload_eqsl_dialog():
    """Upload the contacts not yet sent to eQSL, after confirmation."""
    if len(str(eqsl_user.get())) > 3 and len(str(form_eqsl_password.get())) > 3:
        if _gui_logbook_empty() or _gui_nothing_to_upload("eqsl"):
            return
        if gui_ask_yes_no(tr("logbook.title"), tr("logbook.confirm_eqsl"), parent=root):
            popup_toast(tr("logbook.eqsl_uploading"), "accent")
            upload_to_eqsl(eqsl_user.get(), form_eqsl_password.get(), eqsl_qth.get())
    else:
        gui_show_error(tr("logbook.title"), tr("logbook.eqsl_not_configured"), parent=root)


def upload_qrz_dialog():
    """Upload the contacts not yet sent to the QRZ.com logbook, after confirmation."""
    if len(str(form_qrz_api_key.get())) > 10:
        if _gui_logbook_empty() or _gui_nothing_to_upload("qrz"):
            return
        if gui_ask_yes_no(tr("logbook.title"), tr("logbook.confirm_qrz"), parent=root):
            popup_toast(tr("logbook.qrz_uploading"), "accent")
            start_worker(_send_qrz_worker, str(form_qrz_api_key.get()).strip(), name="qrz-upload")
    else:
        gui_show_error(tr("logbook.title"), tr("logbook.qrz_not_configured"), parent=root)


# ---------------------------------------------------------------------------
# Alarm log page
# ---------------------------------------------------------------------------

def _gui_build_alarm_page(parent):
    """Alarm log tab: when watched callsigns joined or left the network."""
    global alarm_log_view
    page = ctk.CTkFrame(parent, fg_color="transparent")
    page.grid_columnconfigure(0, weight=1)
    page.grid_rowconfigure(0, weight=1)
    card = _GuiCard(page, title=tr("alarms.log_title"))
    card.grid(row=0, column=0, sticky="nsew")
    card.body.grid_columnconfigure(0, weight=1)
    card.body.grid_rowconfigure(0, weight=1)
    alarm_log_view = _gui_register("alarm_log_view", _GuiAlarmLog(card.body))
    alarm_log_view.grid(row=0, column=0, sticky="nsew")

    _GuiButton(card.title_tools, text=tr("alarms.title"), width=110, command=open_alarm_editor).grid(row=0, column=0, padx=(0, 6))
    _GuiButton(card.title_tools, role="danger_soft", text=tr("common.clear"), width=90, command=_gui_clear_alarm_log).grid(row=0, column=1)
    return page


def _gui_clear_alarm_log():
    """Forget the alarm history and empty the table."""
    clear_alarm_log()
    alarm_log_view.clear()


# ---------------------------------------------------------------------------
# Settings page
# ---------------------------------------------------------------------------

GUI_RX_MODES = RX_MODES
GUI_TX_MODES = TX_MODES
GUI_TOT_VALUES = TOT_VALUES
# Interface languages: the code stored in the settings and the name shown
# to the user, always written in the language itself.
GUI_LANGUAGES = language_names()


def _gui_language_name(code):
    """Name shown for a stored language code."""
    return GUI_LANGUAGES.get(code, GUI_LANGUAGES[DEFAULT_LANGUAGE])


def _gui_language_code(shown_name):
    """Stored language code for a name shown in the list."""
    for code, name in GUI_LANGUAGES.items():
        if name == shown_name:
            return code
    return DEFAULT_LANGUAGE


def _gui_form_row(section, row, label, widget, column=0, hint=None):
    """Place a caption and its input on a two-column settings form."""
    _gui_label(section, label, font="caption", color="muted", anchor="w").grid(
        row=row, column=column, sticky="w", padx=(0, 12), pady=5
    )
    widget.grid(row=row, column=column + 1, sticky="w", pady=5)
    if hint:
        _gui_label(section, hint, font="small", color="muted", anchor="w").grid(
            row=row + 1, column=column + 1, sticky="w", pady=(0, 4)
        )
    return widget


def _gui_serial_ports(rescan=False):
    """Serial ports available for PTT and squelch control.

    The list found at startup is reused; rescan=True probes the ports again
    (not under Wine, where probing is unreliable).
    """
    if rescan:
        return rescan_serial_ports()
    return sorted(set(serial_port_list or []))


def _gui_audio_devices(want_input):
    """Audio devices for capture (want_input=True) or playback, as "index:name" texts."""
    try:
        return list(utils.list_audio_devices(want_input, p))
    except Exception as exc:
        log.warning("Unable to list audio devices: %r", exc)
        return []


class _GuiSideMenu(_GuiCard):
    """Vertical list of section buttons shown at the left of a page.

    Clicking an entry highlights it and calls command(title). set(title)
    only moves the highlight, so code that already shows a section can keep
    the menu in step without calling command a second time.
    """

    def __init__(self, master, values, command=None, width=170):
        super().__init__(master, padding=10)
        self._command = command
        self._buttons = {}
        self._current = None
        for row, title in enumerate(values):
            button = _GuiButton(
                self.body,
                role="ghost",
                text=title,
                width=width,
                height=36,
                anchor="w",
                font=_gui_fonts["tab"],
                command=lambda chosen=title: self._on_click(chosen),
            )
            button.grid(row=row, column=0, sticky="ew", pady=(0, 4))
            self._buttons[title] = button

    def _on_click(self, title):
        self.set(title)
        if self._command is not None:
            self._command(title)

    def set(self, title):
        """Highlight the entry called title and dim the others."""
        for name, button in self._buttons.items():
            button.set_role("accent" if name == title else "ghost")
        self._current = title

    def get(self):
        """Title of the highlighted entry, or None before anything is chosen."""
        return self._current


def _gui_build_settings_page(parent):
    """Settings tab: a section menu on the left, the chosen section on the right, and Save."""
    page = ctk.CTkFrame(parent, fg_color="transparent")
    page.grid_columnconfigure(1, weight=1)
    page.grid_rowconfigure(0, weight=1)

    sections = [
        ("general", tr("settings.general"), _gui_build_general_settings),
        ("platforms", tr("settings.platforms"), _gui_build_platform_settings),
        ("rx", tr("settings.rx_control"), _gui_build_rx_settings),
        ("tx", tr("settings.tx_control"), _gui_build_tx_settings),
        ("aprs", "APRS", _gui_build_aprs_settings),
        ("auto", tr("settings.auto"), _gui_build_auto_settings),
    ]

    # Right side: every section is built once, stacked in the same cell, and
    # the chosen one is raised to the top.
    holder = _GuiCard(page, padding=18)
    holder.grid(row=0, column=1, sticky="nsew")
    holder.body.grid_columnconfigure(0, weight=1)
    holder.body.grid_rowconfigure(0, weight=1)
    frames = {}
    titles = {}
    for key, title, builder in sections:
        frame = ctk.CTkFrame(holder.body, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew")
        builder(frame, key)
        frames[key] = frame
        titles[title] = key

    def show(title):
        frames[titles[title]].tkraise()

    # Left side: the section menu, stuck to the top so it does not stretch.
    selector = _GuiSideMenu(page, [title for _key, title, _builder in sections], command=show)
    selector.grid(row=0, column=0, sticky="nw", padx=(0, 12))
    first = sections[0][1]
    selector.set(first)
    show(first)
    _gui_widgets["settings_selector"] = selector
    _gui_widgets["settings_frames"] = frames
    _gui_widgets["settings_titles"] = {key: title for key, title, _builder in sections}

    footer = ctk.CTkFrame(page, fg_color="transparent")
    footer.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    footer.grid_columnconfigure(0, weight=1)
    _gui_label(
        footer,
        tr("settings.restart_hint"),
        font="small",
        color="muted",
    ).grid(row=0, column=0, sticky="w")
    _GuiButton(footer, role="accent", text=tr("common.save"), width=150, height=38, command=save_settings_button).grid(row=0, column=1, sticky="e")
    return page


def _gui_show_settings_section(key):
    """Bring a settings section into view."""
    frames = _gui_widgets.get("settings_frames") or {}
    if key in frames:
        frames[key].tkraise()
        _gui_widgets["settings_selector"].set(_gui_widgets["settings_titles"][key])


def _gui_build_general_settings(frame, page_key):
    global form_callsign, form_message, form_dmr_id, form_access_code, form_server, form_language
    global form_scale_value, form_scale, form_always_on_top, form_roger_beep, update_ids_button, form_input_device, form_output_device
    frame.grid_columnconfigure(1, weight=1)
    frame.grid_columnconfigure(3, weight=1)

    form_callsign = _gui_register("form_callsign", _gui_uppercase(tk.StringVar(master=root, value=str(my_call))), page_key)
    _gui_form_row(frame, 0, tr("field.callsign"), _gui_entry(frame, form_callsign, width=180))

    form_message = _gui_register("form_message", tk.StringVar(master=root, value=str(tx_message)), page_key)
    _gui_form_row(frame, 1, tr("field.message"), _gui_entry(frame, form_message, width=260), hint=tr("settings.message_hint"))

    dmr_row = ctk.CTkFrame(frame, fg_color="transparent")
    # Editable: the ids found on radioid.net are offered, but any id can be typed.
    form_dmr_id = _gui_register("form_dmr_id", _GuiCombo(dmr_row, values=[str(dmr_id)], readonly=False, width=14), page_key)
    form_dmr_id.set(str(dmr_id))
    form_dmr_id.grid(row=0, column=0)
    _GuiButton(dmr_row, text=tr("settings.dmr_lookup"), width=90, command=lambda: query_dmr_ids(form_callsign.get())).grid(row=0, column=1, padx=(6, 0))
    _gui_form_row(frame, 3, tr("settings.dmr_id"), dmr_row)

    code_row = ctk.CTkFrame(frame, fg_color="transparent")
    form_access_code = _gui_register("form_access_code", tk.StringVar(master=root, value=str(access_code)), page_key)
    code_entry = _gui_entry(code_row, form_access_code, width=130, show="\u2022")
    code_entry.grid(row=0, column=0)

    def toggle_code():
        hidden = code_entry.cget("show") != ""
        code_entry.configure(show="" if hidden else "\u2022")
        reveal.configure(text=tr("common.hide") if hidden else tr("common.show"))

    reveal = _GuiButton(code_row, text=tr("common.show"), width=90, command=toggle_code)
    reveal.grid(row=0, column=1, padx=(6, 0))
    _gui_form_row(frame, 4, tr("settings.access_code"), code_row)

    form_server = _gui_register("form_server", _GuiCombo(frame, width=22), page_key)
    _gui_form_row(frame, 5, tr("settings.server"), form_server)

    form_language = _gui_register("form_language", _GuiCombo(frame, values=sorted(GUI_LANGUAGES.values()), width=22), page_key)
    _gui_form_row(frame, 6, tr("settings.language"), form_language)

    form_scale_value = tk.IntVar(master=root, value=min(SCALE_MAX, max(SCALE_MIN, int(ui_scale_setting or 1))))
    form_scale = _gui_register("form_scale", _GuiSpin(frame, SCALE_MIN, SCALE_MAX, variable=form_scale_value), page_key)
    _gui_register("form_scale_value", form_scale)
    _gui_form_row(frame, 7, tr("settings.scale"), form_scale)

    # Right column: audio devices and switches.
    _gui_label(frame, tr("settings.audio"), font="card_title", color="text").grid(
        row=0, column=2, columnspan=2, sticky="w", padx=(28, 0)
    )
    inputs = _gui_audio_devices(True)
    outputs = _gui_audio_devices(False)
    form_input_device = tk.StringVar(master=root, value=str(input_device))
    form_output_device = tk.StringVar(master=root, value=str(output_device))
    if form_input_device.get() and form_input_device.get() not in inputs:
        inputs.insert(0, form_input_device.get())
    if form_output_device.get() and form_output_device.get() not in outputs:
        outputs.insert(0, form_output_device.get())
    input_row = ctk.CTkFrame(frame, fg_color="transparent")
    input_combo = _gui_register(
        "form_input_device", _GuiCombo(input_row, values=inputs, variable=form_input_device, width=34), page_key
    )
    input_combo.grid(row=0, column=0)
    output_combo = _gui_register("form_output_device", _GuiCombo(frame, values=outputs, variable=form_output_device, width=34), page_key)

    def rescan_audio():
        new_inputs, new_outputs = rescan_audio_devices()
        # A saved device that is not plugged in stays in its list, so it is never lost.
        lists = ((input_combo, new_inputs, form_input_device), (output_combo, new_outputs, form_output_device))
        for combo, devices, variable in lists:
            if variable.get() and variable.get() not in devices:
                devices.insert(0, variable.get())
            combo.set_values(devices)

    refresh_audio = _GuiButton(input_row, text="\u21bb", width=34, command=rescan_audio)
    refresh_audio.grid(row=0, column=1, padx=(6, 0))
    _GuiTooltip(refresh_audio, tr("audio.rescan_tip"))
    _gui_label(frame, tr("audio.input"), font="caption", color="muted").grid(row=1, column=2, sticky="w", padx=(28, 12))
    input_row.grid(row=1, column=3, sticky="w", pady=5)
    _gui_label(frame, tr("audio.output"), font="caption", color="muted").grid(row=2, column=2, sticky="w", padx=(28, 12))
    output_combo.grid(row=2, column=3, sticky="w", pady=5)

    form_always_on_top = _gui_register("form_always_on_top", tk.IntVar(master=root, value=int(always_on_top or 0)), page_key)
    _gui_switch(frame, tr("settings.always_on_top"), form_always_on_top).grid(row=3, column=3, sticky="w", pady=5)
    form_roger_beep = _gui_register("form_roger_beep", tk.IntVar(master=root, value=int(roger_beep or 0)), page_key)
    _gui_switch(frame, tr("settings.roger_beep"), form_roger_beep).grid(row=4, column=3, sticky="w", pady=5)

    update_ids_button = _GuiButton(frame, text=tr("settings.update_radioid"), width=200, command=on_update_radioid_list)
    update_ids_button.grid(row=6, column=3, sticky="w", pady=5)
    _gui_register("update_ids_button", update_ids_button)


def _gui_build_platform_settings(frame, page_key):
    global eqsl_user, form_eqsl_password, eqsl_qth, qrz_user, form_qrz_password, form_qrz_api_key
    frame.grid_columnconfigure(0, weight=1, uniform="platforms")
    frame.grid_columnconfigure(1, weight=1, uniform="platforms")

    eqsl = _GuiCard(frame, title=tr("platforms.eqsl").rstrip(":"))
    eqsl.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    eqsl_user = _gui_register("eqsl_user", tk.StringVar(master=root, value=str(eqsl_username)), page_key)
    form_eqsl_password = _gui_register("form_eqsl_password", tk.StringVar(master=root, value=str(eqsl_password)), page_key)
    eqsl_qth = _gui_register("eqsl_qth", tk.StringVar(master=root, value=str(eqsl_qth_name)), page_key)
    _gui_form_row(eqsl.body, 0, tr("platforms.user"), _gui_entry(eqsl.body, eqsl_user, width=190))
    _gui_form_row(eqsl.body, 1, tr("platforms.password"), _gui_entry(eqsl.body, form_eqsl_password, width=190, show="\u2022"))
    _gui_form_row(eqsl.body, 2, tr("platforms.qth_nickname"), _gui_entry(eqsl.body, eqsl_qth, width=190))

    qrz = _GuiCard(frame, title=tr("platforms.qrz").rstrip(":"))
    qrz.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
    qrz_user = _gui_register("qrz_user", tk.StringVar(master=root, value=str(qrz_username)), page_key)
    form_qrz_password = _gui_register("form_qrz_password", tk.StringVar(master=root, value=str(qrz_password)), page_key)
    form_qrz_api_key = _gui_register("form_qrz_api_key", tk.StringVar(master=root, value=str(qrz_api_key)), page_key)
    _gui_form_row(qrz.body, 0, tr("platforms.user"), _gui_entry(qrz.body, qrz_user, width=190))
    _gui_form_row(qrz.body, 1, tr("platforms.password"), _gui_entry(qrz.body, form_qrz_password, width=190, show="\u2022"))
    _gui_form_row(qrz.body, 2, tr("platforms.qrz_api_key"), _gui_entry(qrz.body, form_qrz_api_key, width=190, show="\u2022"))


def _gui_port_selector(frame, variable_name, page_key):
    """Serial port drop-down with a button that rescans the ports."""
    row = ctk.CTkFrame(frame, fg_color="transparent")
    combo = _gui_register(variable_name, _GuiCombo(row, values=_gui_serial_ports(), width=20), page_key)
    combo.grid(row=0, column=0)

    def rescan():
        ports = _gui_serial_ports(rescan=True)
        for name in ("form_rx_port", "form_tx_port"):
            if name in _gui_registry:
                _gui_registry[name].set_values(ports)

    refresh = _GuiButton(row, text="\u21bb", width=34, command=rescan)
    refresh.grid(row=0, column=1, padx=(6, 0))
    _GuiTooltip(refresh, tr("serial.rescan_tip"))
    return row, combo


def _gui_build_rx_settings(frame, page_key):
    global form_rx_mode, rx_mode_choice, spin_threshold, spin_delay, spin_return, form_rx_port
    rx_mode_choice = tk.StringVar(master=root, value=str(rx_mode))
    form_rx_mode = _gui_register("form_rx_mode", _GuiCombo(frame, values=GUI_RX_MODES, variable=rx_mode_choice, width=18, command=rx_mode_changed), page_key)
    _gui_form_row(frame, 0, tr("settings.rx_control"), form_rx_mode)
    spin_threshold = _gui_register("vox_threshold", _GuiSpin(frame, 1, 32767, variable=vox_threshold, step=10, width=80), page_key)
    _gui_form_row(frame, 1, tr("settings.vox_threshold"), spin_threshold)
    spin_delay = _gui_register("vox_delay", _GuiSpin(frame, 1, 500, variable=vox_delay), page_key)
    _gui_form_row(frame, 2, tr("settings.vox_hang_time"), spin_delay)
    spin_return = _gui_register("vox_return", _GuiSpin(frame, 0, 50, variable=vox_return), page_key)
    _gui_form_row(frame, 3, tr("settings.return_hold"), spin_return)
    port_row, form_rx_port = _gui_port_selector(frame, "form_rx_port", page_key)
    _gui_form_row(frame, 4, tr("settings.serial_port"), port_row)


def _gui_build_tx_settings(frame, page_key):
    global form_tx_mode, tx_mode_choice, form_tx_port, form_ctrl_key_ptt, form_tx_timeout, tx_timeout_choice
    tx_mode_choice = tk.StringVar(master=root, value=str(tx_mode))
    form_tx_mode = _gui_register("form_tx_mode", _GuiCombo(frame, values=GUI_TX_MODES, variable=tx_mode_choice, width=18, command=tx_mode_changed), page_key)
    _gui_form_row(frame, 0, tr("settings.tx_control"), form_tx_mode)
    port_row, form_tx_port = _gui_port_selector(frame, "form_tx_port", page_key)
    _gui_form_row(frame, 1, tr("settings.serial_port"), port_row)
    tx_timeout_choice = tk.StringVar(master=root, value=str(tx_timeout_setting))
    form_tx_timeout = _gui_register("form_tx_timeout", _GuiCombo(frame, values=GUI_TOT_VALUES, variable=tx_timeout_choice, width=18), page_key)
    _gui_form_row(frame, 2, tr("settings.tx_timeout"), form_tx_timeout)
    form_ctrl_key_ptt = _gui_register("form_ctrl_key_ptt", tk.IntVar(master=root, value=int(ctrl_key_ptt or 0)), page_key)
    _gui_switch(frame, tr("settings.ctrl_key_ptt"), form_ctrl_key_ptt).grid(row=3, column=1, sticky="w", pady=8)


def _gui_build_aprs_settings(frame, page_key):
    global form_aprs_enabled, form_aprs_host, form_aprs_port, form_aprs_latitude, form_aprs_longitude
    form_aprs_enabled = _gui_register("form_aprs_enabled", tk.IntVar(master=root, value=int(aprs_enabled_setting or 0)), page_key)
    _gui_switch(frame, tr("aprs.enable"), form_aprs_enabled).grid(row=0, column=1, sticky="w", pady=(0, 8))
    form_aprs_host = _gui_register("form_aprs_host", tk.StringVar(master=root, value=str(aprs_host_setting)), page_key)
    _gui_form_row(frame, 1, tr("aprs.host"), _gui_entry(frame, form_aprs_host, width=300))
    form_aprs_port = _gui_register("form_aprs_port", tk.StringVar(master=root, value=str(aprs_port_setting)), page_key)
    _gui_form_row(frame, 2, tr("aprs.port"), _gui_entry(frame, form_aprs_port, width=110))
    form_aprs_latitude = _gui_register("form_aprs_latitude", tk.StringVar(master=root, value=str(aprs_lat_setting)), page_key)
    _gui_form_row(frame, 3, tr("aprs.latitude"), _gui_entry(frame, form_aprs_latitude, width=200))
    form_aprs_longitude = _gui_register("form_aprs_longitude", tk.StringVar(master=root, value=str(aprs_lon_setting)), page_key)
    _gui_form_row(frame, 4, tr("aprs.longitude"), _gui_entry(frame, form_aprs_longitude, width=200))


def _gui_build_auto_settings(frame, page_key):
    global form_auto_room, auto_room_choice, form_auto_connect
    auto_room_choice = tk.StringVar(master=root, value=str(auto_room))
    form_auto_room = _gui_register("form_auto_room", _GuiCombo(frame, values=[""], variable=auto_room_choice, width=18), page_key)
    _gui_form_row(frame, 0, tr("field.room"), form_auto_room)
    form_auto_connect = _gui_register("form_auto_connect", tk.IntVar(master=root, value=int(auto_connect_setting or 0)), page_key)
    _gui_switch(frame, tr("settings.connect_at_start"), form_auto_connect).grid(row=1, column=1, sticky="w", pady=8)


def rx_mode_changed(_event=None):
    """Enable only the receive-control fields that the chosen mode uses."""
    mode = str(rx_mode_choice.get())
    for spin in (spin_threshold, spin_delay, spin_return):
        spin.set_enabled(mode == "VOX")
    form_rx_port.set_enabled(mode.startswith("Serial"))


def tx_mode_changed(_event=None):
    """Enable the transmit serial port only for the serial PTT modes."""
    form_tx_port.set_enabled(str(tx_mode_choice.get()).startswith("Serial"))


@_gui_on_main_thread()
def select_server(server):
    """Select the server whose master address is `server`."""
    for item in server_list or []:
        if item.get("master") == server:
            form_server.set(item.get("name", ""))
            break


def ui_collect_setup_values():
    """Collect the settings form as plain values for settings.save_setup()."""
    values = {
        "form_scale_value": form_scale.get(),
        "form_rx_mode": form_rx_mode.get(),
        "form_rx_port": form_rx_port.get(),
        "form_tx_mode": form_tx_mode.get(),
        "form_tx_port": form_tx_port.get(),
        "form_auto_connect": form_auto_connect.get(),
        "form_auto_room": form_auto_room.get(),
        "form_callsign": form_callsign.get(),
        "form_dmr_id": form_dmr_id.get(),
        "form_message": form_message.get(),
        "form_access_code": form_access_code.get(),
        "form_server": form_server.get(),
        "form_always_on_top": form_always_on_top.get(),
        "form_roger_beep": form_roger_beep.get(),
        "input_device": form_input_device.get(),
        "output_device": form_output_device.get(),
        "eqsl_user": eqsl_user.get(),
        "form_eqsl_password": form_eqsl_password.get(),
        "eqsl_qth": eqsl_qth.get(),
        "qrz_user": qrz_user.get(),
        "form_qrz_password": form_qrz_password.get(),
        "form_qrz_api_key": form_qrz_api_key.get(),
        "form_language": _gui_language_code(form_language.get()),
        "vox_threshold": spin_threshold.get(),
        "vox_delay": spin_delay.get(),
        "vox_return": spin_return.get(),
        "form_ctrl_key_ptt": form_ctrl_key_ptt.get(),
        "form_tx_timeout": form_tx_timeout.get(),
        "form_aprs_enabled": form_aprs_enabled.get(),
        "form_aprs_host": form_aprs_host.get(),
        "form_aprs_port": form_aprs_port.get(),
        "form_aprs_latitude": form_aprs_latitude.get(),
        "form_aprs_longitude": form_aprs_longitude.get(),
    }
    return {key: value.strip() if isinstance(value, str) else value for key, value in values.items()}


def save_settings_button():
    """Validate and save the settings form (settings.save_setup), then reload the configuration."""
    values = ui_collect_setup_values()
    try:
        result = save_setup(values)
    except OSError as exc:
        gui_show_error(tr("tab.settings"), str(exc), parent=root)
        return
    if result.get("status") == "validation_error":
        gui_show_error(tr("tab.settings"), result.get("message", ""), parent=root)
        ui_focus_widget(result.get("focus", ""))
        return
    if result.get("status") == "saved":
        reload_settings()
        _gui_apply_settings()
        transmit_button.update_look(text=str(my_call))
        current_call.set(str(my_call))
        for warning in result.get("warnings", []):
            gui_show_warning(tr("tab.settings"), warning, parent=root)
        if result.get("needs_restart"):
            popup_toast(tr("settings.restart_needed"), "danger")
        ui_set_selected_tab(0)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class _GuiDialog(ctk.CTkToplevel):
    """Modal dialog centered over the main window.

    Subclasses fill self.body and call self.finish_layout() at the end of
    their constructor. Escape closes the dialog; Return runs on_accept().
    """

    def __init__(self, parent, title):
        super().__init__(parent, fg_color=GUI_COLORS["window"])
        self.withdraw()
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda _event: self.cancel())
        self._previous_grab = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew", padx=20, pady=(18, 8))
        self.buttons = ctk.CTkFrame(self, fg_color="transparent")
        self.buttons.grid(row=1, column=0, sticky="e", padx=20, pady=(4, 18))

    def add_buttons(self, accept_text=None, cancel_text=None):
        """Add the standard Cancel and Accept buttons."""
        if cancel_text is not None:
            _GuiButton(self.buttons, text=cancel_text, width=110, command=self.cancel).grid(row=0, column=0, padx=(0, 8))
        if accept_text is not None:
            _GuiButton(self.buttons, role="accent", text=accept_text, width=110, command=self.on_accept).grid(row=0, column=1)

    def finish_layout(self, focus_widget=None):
        """Center the dialog over the main window, show it and make it modal."""
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        try:
            x = root.winfo_rootx() + (root.winfo_width() - width) // 2
            y = root.winfo_rooty() + (root.winfo_height() - height) // 3
        except tk.TclError:
            x, y = 100, 100
        self.geometry("+{}+{}".format(max(0, x), max(0, y)))
        self.deiconify()
        self.lift()
        # CustomTkinter installs its own icon on new windows shortly after
        # they open, so the application icon is applied a moment later.
        self.after(250, lambda: _gui_apply_dialog_icon(self))
        self.after(20, lambda: self._make_modal(focus_widget))

    def _make_modal(self, focus_widget, attempts=10):
        """Grab the input once the window is visible (Tk refuses earlier)."""
        try:
            # Remember who held the input, so a message shown on top of
            # another dialog hands the input back to it when it closes.
            if getattr(self, "_previous_grab", None) is None:
                current = self.grab_current()
                self._previous_grab = current if current is not self else None
            self.grab_set()
        except tk.TclError:
            if attempts > 0:
                self.after(50, lambda: self._make_modal(focus_widget, attempts - 1))
                return
        target = focus_widget or self
        try:
            target.focus_set()
        except tk.TclError:
            pass

    def on_accept(self):
        self.cancel()

    def cancel(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        previous = getattr(self, "_previous_grab", None)
        self.destroy()
        if previous is not None:
            try:
                if previous.winfo_exists():
                    previous.grab_set()
                    previous.focus_set()
            except tk.TclError:
                pass


def _gui_apply_dialog_icon(window):
    if _gui_window_icon is not None:
        try:
            window.iconphoto(False, _gui_window_icon)
        except tk.TclError:
            pass


class LogbookRecordDialog(_GuiDialog):
    """Logbook record form, used both to add and to edit a QSO.

    edit_id is the record id to edit, or False to add a new record.
    prefill_call and prefill_name prefill the callsign and name when adding
    from a station shown in the main window. After the dialog closes, self.saved tells whether the
    record was stored.
    """

    # Bands offered first, with the frequency suggested for each (MHz). Any
    # other band of the ADIF list can be typed.
    BAND_FREQUENCIES = {"2m": "144.000", "70cm": "430.000", "10m": "28.000", "6m": "50.000", "23cm": "1240.000"}

    def __init__(self, parent, title_text, edit_id=False, prefill_call=None, prefill_name=None):
        super().__init__(parent, title_text)
        self.edit_id = edit_id
        self.saved = False
        now = datetime.now(timezone.utc)
        self.var_call = _gui_uppercase(tk.StringVar(master=root))
        self.var_name = tk.StringVar(master=root)
        self.var_date = tk.StringVar(master=root, value=now.strftime(DATE_FORMAT))
        self.var_time = tk.StringVar(master=root, value=now.strftime("%H:%M"))
        self.var_band = tk.StringVar(master=root)
        self.var_frequency = tk.StringVar(master=root)
        self.var_comment = tk.StringVar(master=root)

        if edit_id:
            record = logbook_get_record(edit_id)
            if record:
                for variable, value in zip(
                    (self.var_call, self.var_name, self.var_date, self.var_time, self.var_band, self.var_frequency, self.var_comment),
                    record,
                ):
                    variable.set("" if value is None else str(value))
        else:
            if prefill_call:
                self.var_call.set(prefill_call)
                self.var_name.set(prefill_name or "")
            last = logbook_last_record()
            if last:
                self.var_band.set(last[0] or "")
                self.var_frequency.set(last[1] or "")
                self.var_comment.set(last[2] or "")

        form = self.body
        self.callsign = _gui_entry(form, self.var_call, width=220)
        _gui_form_row(form, 0, tr("field.callsign"), self.callsign)
        _gui_form_row(form, 1, tr("field.name"), _gui_entry(form, self.var_name, width=220))
        self.date_entry = _gui_entry(form, self.var_date, width=130)
        _gui_form_row(form, 2, tr("field.date"), self.date_entry, hint="yyyy-mm-dd (UTC)")
        self.time_entry = _gui_entry(form, self.var_time, width=90)
        _gui_form_row(form, 4, tr("field.time"), self.time_entry, hint="HH:MM (UTC)")
        self.band_combo = _GuiCombo(form, values=list(self.BAND_FREQUENCIES), variable=self.var_band, readonly=False, width=12, command=self.band_changed)
        _gui_form_row(form, 6, tr("field.band"), self.band_combo)
        self.frequency_entry = _gui_entry(form, self.var_frequency, width=130)
        _gui_form_row(form, 7, tr("field.frequency"), self.frequency_entry)
        _gui_form_row(form, 8, tr("field.comment"), _gui_entry(form, self.var_comment, width=260))
        self.add_buttons(tr("common.ok"), tr("common.cancel"))
        self.bind("<Return>", lambda _event: self.on_accept())
        self.finish_layout(self.callsign)

    def band_changed(self, _event=None):
        """Suggest the usual frequency of the chosen band."""
        frequency = self.BAND_FREQUENCIES.get(self.var_band.get())
        if frequency:
            self.var_frequency.set(frequency)
        self.frequency_entry.focus_set()

    def validate(self):
        """Check the form; show what is wrong and return False on errors."""
        title = tr("logbook.title")
        # Only letters, numbers and "/" are kept, as a callsign is written in ADIF.
        call = clean_callsign(self.var_call.get())
        self.var_call.set(call)
        if len(call) < 3:
            gui_show_info(title, tr("form.callsign_missing"), parent=self)
            self.callsign.focus_set()
            return False
        try:
            datetime.strptime(self.var_date.get().strip(), DATE_FORMAT)
        except ValueError:
            gui_show_info(title, tr("logbook.date_invalid"), parent=self)
            self.date_entry.focus_set()
            return False
        time_text = self.var_time.get().strip()
        if _gui_parse_time(time_text) is None:
            gui_show_info(title, tr("logbook.time_invalid"), parent=self)
            self.time_entry.focus_set()
            return False
        band = self.var_band.get().strip().lower()
        if band not in ADIF_BANDS:
            gui_show_info(
                title,
                "{}\n\n{}".format(tr("logbook.band_invalid"), ", ".join(ADIF_BANDS)),
                parent=self,
            )
            self.band_combo.focus_set()
            return False
        self.var_band.set(band)
        frequency = _gui_parse_frequency(self.var_frequency.get())
        if frequency is None:
            gui_show_info(title, tr("logbook.frequency_invalid"), parent=self)
            self.frequency_entry.focus_set()
            return False
        # ADIF wants a plain number in MHz, with a dot as decimal separator.
        self.var_frequency.set(frequency)
        if not self.edit_id:
            record = logbook_find_by_call(call)
            if record:
                text = "{}\n\n{}: {}\n{}: {}\n{}: {}\n\n{}".format(
                    tr("logbook.duplicate").format(record[0]),
                    tr("field.date"),
                    record[2],
                    tr("field.time"),
                    record[3],
                    tr("field.band"),
                    record[4],
                    tr("common.continue_question"),
                )
                if not gui_ask_yes_no(title, text, parent=self):
                    return False
        return True

    def on_accept(self):
        if not self.validate():
            return
        if not gui_ask_yes_no(tr("logbook.title"), tr("logbook.confirm_save"), parent=self):
            return
        logbook_save_record(
            {
                "callsign": self.var_call.get().strip(),
                "name": self.var_name.get().strip(),
                "date": self.var_date.get().strip(),
                "time": self.var_time.get().strip(),
                "band": self.var_band.get().strip(),
                "comment": self.var_comment.get().strip(),
                "frequency": self.var_frequency.get().strip(),
            },
            self.edit_id or None,
        )
        self.saved = True
        self.cancel()


def _gui_parse_time(text):
    """A logbook time typed as HH:MM or HH:MM:SS, or None when it is not a valid time."""
    for time_format in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(str(text).strip(), time_format)
        except ValueError:
            continue
    return None


def _gui_parse_frequency(text):
    """A frequency in MHz as ADIF writes it ("144.800"), or None when it is not a positive number.

    A comma is accepted as decimal separator and a trailing "MHz" is ignored.
    """
    cleaned = str(text).strip().lower().replace("mhz", "").strip().replace(",", ".")
    try:
        value = float(cleaned)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    return "{:.6f}".format(value).rstrip("0").rstrip(".")


def _gui_listbox(master, height=10, width=18, selectmode="extended"):
    """Themed Tk listbox with a scrollbar, returned as (frame, listbox)."""
    frame = ctk.CTkFrame(master, fg_color=GUI_COLORS["field"], corner_radius=12, border_width=1, border_color=GUI_COLORS["card_border"])
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_rowconfigure(0, weight=1)
    listbox = tk.Listbox(
        frame,
        height=height,
        width=width,
        selectmode=selectmode,
        exportselection=False,
        activestyle="none",
        font=_gui_fonts["tk_body"],
        background=GUI_COLORS["field"],
        foreground=GUI_COLORS["text"],
        selectbackground=GUI_COLORS["accent_soft"],
        selectforeground=GUI_COLORS["accent"],
        highlightthickness=0,
        borderwidth=0,
    )
    listbox.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
    scrollbar = ctk.CTkScrollbar(frame, command=listbox.yview, width=12, button_color=GUI_COLORS["neutral_hover"])
    scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 4), pady=8)
    listbox.configure(yscrollcommand=scrollbar.set)
    return frame, listbox


class AlarmListDialog(_GuiDialog):
    """Editor of the callsigns that raise an alarm when they join or leave."""

    def __init__(self, parent, title_text):
        super().__init__(parent, title_text)
        self.var_call = _gui_uppercase(tk.StringVar(master=root))
        form = self.body
        form.grid_columnconfigure(0, weight=1)
        self.entry = _gui_entry(form, self.var_call, width=200)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _event: self.add())
        _GuiButton(form, role="accent", text=tr("common.add"), width=120, command=self.add).grid(row=0, column=1, padx=(8, 0))
        list_frame, self.listbox = _gui_listbox(form, height=10, width=20)
        list_frame.grid(row=1, column=0, rowspan=2, sticky="nsew", pady=(10, 0))
        for call in sorted(watched_calls.keys()):
            self.listbox.insert("end", call)
        self.listbox.bind("<Delete>", lambda _event: self.delete())
        side = ctk.CTkFrame(form, fg_color="transparent")
        side.grid(row=1, column=1, sticky="n", padx=(8, 0), pady=(10, 0))
        _GuiButton(side, text=tr("common.remove"), width=120, command=self.delete).grid(row=0, column=0, pady=(0, 6))
        _GuiButton(side, role="danger_soft", text=tr("common.remove_all").replace("\n", " "), width=120, command=self.delete_all).grid(row=1, column=0)
        self.add_buttons(tr("common.ok"), tr("common.cancel"))
        self.finish_layout(self.entry)

    def add(self):
        call = self.var_call.get().strip()
        if len(call) >= 3 and call not in self.listbox.get(0, "end"):
            self.listbox.insert("end", call)
        self.var_call.set("")
        self.entry.focus_set()

    def delete(self):
        for index in reversed(self.listbox.curselection()):
            self.listbox.delete(index)

    def delete_all(self):
        self.listbox.delete(0, "end")

    def on_accept(self):
        set_alarm_callsigns(self.listbox.get(0, "end"))
        self.cancel()


class ScanRoomsDialog(_GuiDialog):
    """Editor of the rooms the scanner visits, picked from the server's rooms."""

    def __init__(self, parent, title_text):
        super().__init__(parent, title_text)
        self.resizable(True, True)
        self.available_rooms = _gui_room_names() or sorted(
            {str(room).strip().upper() for room in room_picker.cget("values") if str(room).strip()}
        )
        form = self.body
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(2, weight=1)
        form.grid_rowconfigure(2, weight=1)

        _gui_label(form, tr("scan.available"), font="card_title").grid(row=0, column=0, sticky="w")
        self.selected_title = _gui_label(form, tr("scan.selected"), font="card_title")
        self.selected_title.grid(row=0, column=2, sticky="w")
        self.search = tk.StringVar(master=root)
        search_entry = _gui_entry(form, self.search, width=220)
        search_entry.grid(row=1, column=0, sticky="ew", pady=(6, 6))
        _GuiTooltip(search_entry, tr("scan.search_hint"))
        self.search.trace_add("write", lambda *_args: self._fill_available())

        available_frame, self.available_listbox = _gui_listbox(form, height=14, width=22)
        available_frame.grid(row=2, column=0, sticky="nsew")
        selected_frame, self.listbox = _gui_listbox(form, height=14, width=22)
        selected_frame.grid(row=2, column=2, sticky="nsew")
        for room in scan_rooms():
            self.listbox.insert("end", room)
        self.available_listbox.bind("<Double-1>", lambda _event: self.add())
        self.listbox.bind("<Double-1>", lambda _event: self.delete())
        self.listbox.bind("<Delete>", lambda _event: self.delete())

        middle = ctk.CTkFrame(form, fg_color="transparent")
        middle.grid(row=2, column=1, padx=12)
        _GuiButton(middle, role="accent", text="{}  \u203a".format(tr("common.add")), width=150, command=self.add).grid(row=0, column=0, pady=4)
        _GuiButton(middle, text="{}  \u00bb".format(tr("scan.add_all")), width=150, command=self.add_all).grid(row=1, column=0, pady=4)
        _GuiButton(middle, text="\u2039  {}".format(tr("common.remove")), width=150, command=self.delete).grid(row=2, column=0, pady=(18, 4))
        _GuiButton(middle, role="danger_soft", text="\u00ab  {}".format(tr("common.remove_all").replace("\n", " ")), width=150, command=self.delete_all).grid(row=3, column=0, pady=4)

        self._fill_available()
        self._update_count()
        self.add_buttons(tr("common.ok"), tr("common.cancel"))
        self.finish_layout(search_entry)

    def _fill_available(self):
        text = self.search.get().strip().upper()
        self.available_listbox.delete(0, "end")
        for room in self.available_rooms:
            if text in room:
                self.available_listbox.insert("end", room)

    def _update_count(self):
        self.selected_title.configure(text="{}  ({})".format(tr("scan.selected"), self.listbox.size()))

    def _insert(self, rooms):
        current = set(self.listbox.get(0, "end"))
        for room in rooms:
            room = str(room).strip().upper()
            if room and room not in current:
                self.listbox.insert("end", room)
                current.add(room)
        self._update_count()

    def add(self):
        self._insert(self.available_listbox.get(index) for index in self.available_listbox.curselection())

    def add_all(self):
        self._insert(self.available_listbox.get(0, "end"))

    def delete(self):
        for index in reversed(self.listbox.curselection()):
            self.listbox.delete(index)
        self._update_count()

    def delete_all(self):
        self.listbox.delete(0, "end")
        self._update_count()

    def on_accept(self):
        set_scan_rooms(self.listbox.get(0, "end"))
        self.cancel()


class InformationDialog(_GuiDialog):
    """Read-only text window for long answers from eQSL and QRZ.com."""

    def __init__(self, parent, title_text, text=""):
        super().__init__(parent, title_text)
        self.resizable(True, True)
        self.text_box = ctk.CTkTextbox(
            self.body,
            width=520,
            height=300,
            wrap="word",
            font=_gui_fonts["body"],
            fg_color=GUI_COLORS["field"],
            text_color=GUI_COLORS["text"],
            border_width=1,
            border_color=GUI_COLORS["card_border"],
            corner_radius=12,
        )
        self.text_box.grid(row=0, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)
        self.text_box.insert("end", str(text))
        self.text_box.configure(state="disabled")
        self.add_buttons(tr("common.ok"))
        self.finish_layout()


# Look of each kind of message: badge color and the symbol drawn inside it.
GUI_MESSAGE_KINDS = {
    "info": ("info", "i"),
    "warning": ("warning", "!"),
    "error": ("danger", "X"),
    "question": ("accent", "?"),
}


class _GuiMessageBox(_GuiDialog):
    """Short message or yes/no question drawn with the application theme.

    It replaces the operating system message boxes, which ignore the colors
    and fonts of the rest of the window. kind is "info", "warning", "error"
    or "question". A question shows No and Yes buttons and leaves the answer
    in self.result (True for Yes); the other kinds show a single Accept
    button.
    """

    def __init__(self, parent, title, message, kind="info"):
        super().__init__(parent, str(title).strip() or GUI_APP_NAME)
        self.kind = kind if kind in GUI_MESSAGE_KINDS else "info"
        self.result = False
        color, symbol = GUI_MESSAGE_KINDS[self.kind]

        card = _GuiCard(self.body, padding=16)
        card.grid(row=0, column=0, sticky="nsew")
        card.body.grid_columnconfigure(1, weight=1)

        badge = ctk.CTkLabel(
            card.body,
            text=symbol,
            image=_gui_circle_image(_gui_color(color), 40),
            compound="center",
            width=40,
            height=40,
            fg_color="transparent",
            text_color="#FFFFFF",
            font=_gui_fonts["button_big"],
        )
        badge.grid(row=0, column=0, sticky="n", padx=(0, 14))

        text = ctk.CTkLabel(
            card.body,
            text=str(message),
            font=_gui_fonts["body"],
            text_color=GUI_COLORS["text"],
            justify="left",
            anchor="w",
            wraplength=380,
        )
        text.grid(row=0, column=1, sticky="w")

        if self.kind == "question":
            _GuiButton(self.buttons, text=tr("common.no"), width=110, command=self.cancel).grid(row=0, column=0, padx=(0, 8))
            default = _GuiButton(self.buttons, role="accent", text=tr("common.yes"), width=110, command=self.on_accept)
        else:
            default = _GuiButton(self.buttons, role="accent", text=tr("common.ok"), width=110, command=self.on_accept)
        default.grid(row=0, column=1)
        self.bind("<Return>", lambda _event: self.on_accept())
        self.bind("<KP_Enter>", lambda _event: self.on_accept())
        self.finish_layout(focus_widget=default)

    def on_accept(self):
        self.result = True
        self.cancel()


def _gui_message_parent(parent):
    """The window a message belongs to: the given one while it exists, otherwise the main window."""
    try:
        if parent is not None and parent.winfo_exists():
            return parent
    except tk.TclError:
        pass
    return root


def gui_message(title, message, kind="info", parent=None, wait=True):
    """Show a themed message over parent (the main window by default).

    With wait=True the call returns once the user closes the message, and
    returns True when the user accepted it. With wait=False it returns at
    once, which suits messages coming from background events.
    """
    dialog = _GuiMessageBox(_gui_message_parent(parent), title, message, kind)
    if not wait:
        return None
    dialog.master.wait_window(dialog)
    return dialog.result


def gui_show_info(title, message, parent=None):
    """Themed information message; waits until the user closes it."""
    gui_message(title, message, "info", parent)


def gui_show_warning(title, message, parent=None):
    """Themed warning message; waits until the user closes it."""
    gui_message(title, message, "warning", parent)


def gui_show_error(title, message, parent=None):
    """Themed error message; waits until the user closes it."""
    gui_message(title, message, "error", parent)


def gui_ask_yes_no(title, message, parent=None):
    """Themed yes/no question. Returns True only when the user chose Yes."""
    return bool(gui_message(title, message, "question", parent))


# ---------------------------------------------------------------------------
# Clocks, transmission timer and connection status
# ---------------------------------------------------------------------------

def _gui_tick_clock():
    """Once per second: clocks, RX/TX timer, time-out timer and status pill."""
    global _gui_timer_seconds, _gui_timer_status
    if not _gui_alive:
        return
    status = globals().get("link_state", 0)
    if status != _gui_timer_status:
        _gui_timer_status = status
        _gui_timer_seconds = 0

    if status == 1:
        # Receiving: count up.
        _gui_timer_seconds += 1
        current_timer.set(str(_gui_timer_seconds).zfill(3))
        timer_label.configure(fg_color=GUI_COLORS["neutral"], text_color=GUI_COLORS["info"])
    elif status == 2:
        # Transmitting: count down the TX time-out. The core ends the
        # transmission itself when the time-out is reached.
        _gui_timer_seconds += 1
        remaining = tx_timeout_seconds() - _gui_timer_seconds
        current_timer.set(str(max(0, remaining)).zfill(3))
        warning = remaining <= 30
        timer_label.configure(
            fg_color=GUI_COLORS["danger"] if warning else GUI_COLORS["neutral"],
            text_color="#FFFFFF" if warning else GUI_COLORS["danger"],
        )
    else:
        _gui_timer_seconds = 0
        current_timer.set("000")
        timer_label.configure(fg_color=GUI_COLORS["neutral"], text_color=GUI_COLORS["accent"])

    _gui_widgets["clock_utc"].configure(text="UTC " + datetime.now(timezone.utc).strftime("%H:%M:%S"))
    _gui_widgets["clock_local"].configure(text="{} {}".format(tr("clock.local"), strftime("%H:%M:%S")))
    _gui_refresh_status()
    root.after(1000, _gui_tick_clock)


def _gui_refresh_status():
    """Show the connection state in the header pill."""
    pill = _gui_widgets.get("status")
    if pill is None:
        return
    status = globals().get("link_state", 0)
    room = str(globals().get("active_room") or "")
    if _gui_connection_state == "reconnecting" and not session_active:
        text, background, color = tr("status.reconnecting"), GUI_COLORS["warning"], "#FFFFFF"
    elif not session_active:
        text, background, color = tr("status.offline"), GUI_COLORS["neutral"], GUI_COLORS["muted"]
    elif not link_up:
        text, background, color = "{}  \u00b7  {}".format(tr("status.connecting"), room), GUI_COLORS["warning"], "#FFFFFF"
    elif status == 1:
        text, background, color = "{}  \u00b7  {}".format(tr("status.receiving"), heard_call), GUI_COLORS["info"], "#FFFFFF"
    elif status == 2:
        text, background, color = "{}  \u00b7  {}".format(tr("status.transmitting"), room), GUI_COLORS["danger"], "#FFFFFF"
    elif scanner_running:
        text, background, color = "{}  \u00b7  {}".format(tr("status.scanning"), room), GUI_COLORS["success_soft"], GUI_COLORS["success"]
    else:
        text, background, color = "{}  \u00b7  {}".format(tr("status.online"), room), GUI_COLORS["success_soft"], GUI_COLORS["success"]
    pill.configure(text="   {}   ".format(text), fg_color=background, text_color=color)


# ---------------------------------------------------------------------------
# Toast notifications
# ---------------------------------------------------------------------------

@_gui_on_main_thread()
def popup_toast(msg, role="accent"):
    """Show a short notification, centered at the bottom of the window, for a few seconds.

    role is a button role: "accent" (information), "success" (good news) or
    "danger" (removal or warning).
    """
    global _gui_toast_job, toast_frame
    background = _gui_color(GUI_BUTTON_ROLES.get(role, GUI_BUTTON_ROLES["accent"])[0])
    if toast_frame is None:
        toast_frame = ctk.CTkLabel(
            root,
            text="",
            font=_gui_fonts["body_bold"],
            corner_radius=16,
            height=40,
            text_color="#FFFFFF",
        )
    toast_frame.configure(text="   {}   ".format(msg), fg_color=background)
    toast_frame.place(relx=0.5, rely=1.0, y=-_gui_px(110), anchor="s")
    toast_frame.lift()
    if _gui_toast_job is not None:
        try:
            root.after_cancel(_gui_toast_job)
        except tk.TclError:
            pass
    _gui_toast_job = root.after(2600, toast_fade_away)


def toast_fade_away():
    """Hide the toast notification."""
    global _gui_toast_job
    _gui_toast_job = None
    if toast_frame is not None:
        toast_frame.place_forget()


# ---------------------------------------------------------------------------
# GUI helpers (thread safe)
# ---------------------------------------------------------------------------

def ui_set_value(variable_name, value):
    """Set a named value. From worker threads only the newest value is applied."""
    if _gui_is_main_thread():
        _gui_run_safely(_gui_write_value, variable_name, value)
        return
    with _gui_pending_lock:
        _gui_pending_values[variable_name] = value


@_gui_on_main_thread()
def ui_insert_tree_row(widget_name, values, parent="", index="end"):
    """Insert a row into a named table."""
    tree = _gui_lookup(widget_name)
    if tree is None:
        return None
    item = tree.insert(parent, index, values=tuple(str(v).strip() if isinstance(v, str) else v for v in values))
    if widget_name == "last_heard_tree":
        # Keep the session log to a sensible size.
        rows = tree.get_children()
        for extra in rows[500:]:
            tree.delete(extra)
    if widget_name == "online_tree":
        _gui_refresh_online_count()
    if index == "end":
        # Appending keeps the stripes of the rows above: only the new row needs one.
        if (len(tree.get_children()) - 1) % 2:
            tree.item(item, tags=tuple(tree.item(item, "tags")) + ("odd",))
    else:
        _gui_restripe(tree)
        tree.see(item)
    return item


@_gui_on_main_thread()
def ui_set_selected_tab(index):
    """Bring a main tab to the front."""
    tab_bar.select(int(index))


@_gui_on_main_thread()
def ui_scroll_tree_to_top(widget_name):
    tree = _gui_lookup(widget_name)
    if tree is not None:
        tree.yview_moveto(0)


@_gui_on_main_thread()
def ui_insert_log_entry(timestamp, callsign, name, duration):
    """Add a finished transmission to the top of the last heard list."""
    return ui_insert_tree_row("last_heard_tree", (timestamp, callsign, name, duration), parent="", index=0)


@_gui_on_main_thread()
def ui_set_options(widget_name, values):
    """Replace the choices of a named drop-down list."""
    widget = _gui_lookup(widget_name)
    if widget is None:
        return
    if hasattr(widget, "set_values"):
        widget.set_values(values)
    else:
        widget.configure(values=list(values))


@_gui_on_main_thread()
def ui_select_first(widget_name):
    """Select the first choice of a named drop-down list."""
    widget = _gui_lookup(widget_name)
    if widget is None:
        return
    try:
        if widget.cget("values"):
            widget.current(0)
    except (AttributeError, tk.TclError):
        pass


@_gui_on_main_thread()
def ui_focus_widget(widget_name):
    """Show the settings section that holds a widget and focus it."""
    page = _gui_registry_pages.get(widget_name)
    if page is not None:
        ui_set_selected_tab(4)
        _gui_show_settings_section(page)
    widget = _gui_registry.get(widget_name)
    target = getattr(widget, "entry", widget)
    if target is not None and hasattr(target, "focus_set"):
        try:
            target.focus_set()
        except tk.TclError:
            pass


@_gui_on_main_thread()
def ui_show_information_dialog(title, message):
    """Show a long server answer in a scrollable window.

    The call returns at once; the window stays open until the user closes
    it, and the rest of the interface keeps updating meanwhile.
    """
    InformationDialog(root, title, message)


def _send_qrz_worker(api_key):
    """Upload the logbook to QRZ.com with the key shown in Settings (worker thread) and show the answer."""
    response_text = upload_to_qrz(api_key)
    if response_text:
        _gui_on_qrz_reply(response_text)


def on_update_radioid_list():
    """Download a fresh RadioID user file; the button stays disabled until it finishes."""
    _gui_registry["update_ids_button"].update_look(enabled=False)
    update_user_ids()


# Ctrl key PTT state: whether Ctrl is held, and whether another key was
# pressed while it was held (a shortcut such as Ctrl+C, not a PTT press).
_gui_ctrl_down = False
_gui_ctrl_used_for_shortcut = False


def _gui_is_ctrl(event):
    return getattr(event, "keysym", "") in ("Control_L", "Control_R")


def _gui_on_ptt_key_press(event):
    """Remember that Ctrl went down, or that it is being used for a shortcut."""
    global _gui_ctrl_down, _gui_ctrl_used_for_shortcut
    if _gui_is_ctrl(event):
        if not _gui_ctrl_down:
            _gui_ctrl_down = True
            _gui_ctrl_used_for_shortcut = False
    elif _gui_ctrl_down:
        _gui_ctrl_used_for_shortcut = True


def _gui_on_ptt_key(event):
    """Ctrl key PTT: a press and release of Ctrl alone keys or unkeys the transmitter.

    Ctrl used together with another key (Ctrl+C, Ctrl+V, Ctrl+Q...) is a
    shortcut and never touches the transmitter. Keys are recognized by name
    (keysym), so no other key can be mistaken for Ctrl.
    """
    global _gui_ctrl_down
    if not _gui_is_ctrl(event):
        return
    was_shortcut = _gui_ctrl_used_for_shortcut
    _gui_ctrl_down = False
    if int(ctrl_key_ptt or 0) == 1 and not was_shortcut and ptt_allowed:
        toggle_transmit()


def _gui_apply_settings():
    """Show the loaded configuration on the settings form and apply the window options."""
    form_language.set(_gui_language_name(language_setting))
    form_rx_mode.set(rx_mode)
    rx_mode_changed(None)
    vox_threshold.set(int(vox_threshold_setting))
    vox_delay.set(int(vox_delay_setting))
    vox_return.set(int(vox_return_setting))
    if rx_serial_port and rx_serial_port in serial_port_list:
        form_rx_port.set(rx_serial_port)
    form_tx_mode.set(tx_mode)
    tx_mode_changed(None)
    form_tx_timeout.set(tx_timeout_setting)
    if tx_serial_port and tx_serial_port in serial_port_list:
        form_tx_port.set(tx_serial_port)
    select_server(master_host)
    form_dmr_id.set(str(dmr_id))
    root.attributes("-topmost", int(always_on_top or 0) == 1)
    if int(ctrl_key_ptt or 0) == 1:
        root.bind_all("<KeyPress>", _gui_on_ptt_key_press)
        root.bind_all("<KeyRelease>", _gui_on_ptt_key)
    else:
        root.unbind_all("<KeyPress>")
        root.unbind_all("<KeyRelease>")


# ---------------------------------------------------------------------------
# Core event handlers
# ---------------------------------------------------------------------------
# Each handler receives the data of one event published by the core (see
# events.py) and runs on the Tk main thread.

@_gui_on_main_thread()
def _gui_on_servers_loaded(names, current=""):
    ui_set_options("form_server", names)
    ui_select_first("form_server")
    select_server(current)


@_gui_on_main_thread()
def _gui_on_rooms_loaded(countries, initial=False):
    """Fill the room groups; the group already chosen (and its room) is kept when it still exists."""
    group_picker.set_values(countries)
    monitor_filter.set_groups(countries)
    current_group = group_picker.get()
    current_room = room_picker.get()
    group = current_group if current_group in countries else "ALL"
    group_picker.set(group)
    fill_room_list(group, initial and not current_room)
    if current_room and current_room in room_picker.cget("values"):
        room_picker.set(current_room)


# Connection shown in the header: "offline", "connecting", "online" or "reconnecting".
_gui_connection_state = "offline"


@_gui_on_main_thread()
def _gui_on_connecting():
    """The login was sent: Settings are locked and the button can cancel."""
    global _gui_connection_state
    _gui_connection_state = "connecting"
    tab_bar.set_state(4, "disabled")
    _gui_registry["connect_button"].update_look(role="danger_soft", text=tr("main.disconnect"))
    transmit_button.update_look(role=GUI_PTT_ROLES[0], text=str(my_call), enabled=False)
    _gui_refresh_status()


@_gui_on_main_thread()
def _gui_on_connection_changed(connected):
    global _gui_connection_state
    connect = _gui_registry["connect_button"]
    if connected:
        _gui_connection_state = "online"
        tab_bar.set_state(4, "disabled")
        connect.update_look(role="danger_soft", text=tr("main.disconnect"))
        transmit_button.update_look(role=GUI_PTT_ROLES[0], text=str(my_call), enabled=ptt_allowed)
    else:
        _gui_connection_state = "offline"
        tab_bar.set_state(4, "normal")
        connect.update_look(role="accent", text=tr("main.connect"))
        transmit_button.update_look(role=GUI_PTT_ROLES[0], text=str(my_call), enabled=False)
        clear_all_online()
    _gui_refresh_status()


@_gui_on_main_thread()
def _gui_on_reconnecting():
    """The server stopped answering; pressing the button now cancels the reconnection."""
    global _gui_connection_state
    _gui_connection_state = "reconnecting"
    tab_bar.set_state(4, "normal")
    _gui_registry["connect_button"].update_look(role="accent", text=tr("main.cancel_reconnect"))
    transmit_button.update_look(role=GUI_PTT_ROLES[0], text=str(my_call), enabled=False)
    _gui_refresh_status()


@_gui_on_main_thread()
def _gui_on_ptt_state(status, caption, enabled):
    transmit_button.update_look(role=GUI_PTT_ROLES.get(status, GUI_PTT_ROLES[0]), text=str(caption), enabled=enabled)


def _gui_on_audio_level(level):
    # Up to 50 updates per second: only the newest value is drawn
    ui_set_value("audio_level", int(level))


@_gui_on_main_thread()
def _gui_on_transmission_logged(time, callsign, name, duration):
    ui_insert_log_entry(time, callsign, name, duration)
    root.after(1000, ui_scroll_tree_to_top, "last_heard_tree")


@_gui_on_main_thread()
def _gui_on_station_photo(callsign, picture=None, name=""):
    show_station_picture(callsign, picture, photo_label)
    show_station_flag(callsign, flag_label)


@_gui_on_main_thread()
def _gui_on_station_identity(identity, name, location):
    gui_set_station_identity(identity, name, location)


@_gui_on_main_thread()
def _gui_on_online_stations(callsigns):
    clear_all_online()
    for call in callsigns:
        ui_insert_tree_row("online_tree", (call,), parent="", index=0)


@_gui_on_main_thread()
def _gui_on_alarms_updated(lines):
    """Show the new alarm without leaving the tab the user is working in."""
    alarm_log_view.gui_append("\n".join(lines), replace=True)
    tab_bar.set_badge(3)
    if lines:
        fields = (str(lines[0]).split("\t") + ["", ""])[:2]
        popup_toast(tr("alarms.toast").format(fields[0], _gui_alarm_state_text(fields[1])), "success")


@_gui_on_main_thread()
def _gui_on_scan_state(active):
    _gui_registry["scan_button"].update_look(role="success" if active else "neutral")


@_gui_on_main_thread()
def _gui_on_scan_room(room):
    # A scan room outside the current group is shown with every room listed
    if room not in room_picker.cget("values"):
        group_picker.set("ALL")
        fill_room_list("ALL")
    room_picker.set(room)


@_gui_on_main_thread()
def _gui_on_dmr_ids(ids):
    """Offer the DMR ids found on radioid.net; with none found the typed id is kept."""
    if ids is None:
        return
    found = [str(identity) for identity in (ids or []) if str(identity).strip()]
    if not found:
        popup_toast(tr("settings.dmr_not_found"), "danger")
        return
    ui_set_options("form_dmr_id", found)
    ui_select_first("form_dmr_id")


@_gui_on_main_thread()
def _gui_on_user_ids_updated(ok):
    if ok:
        popup_toast(tr("radioid.updated"), "accent")
    _gui_registry["update_ids_button"].update_look(enabled=True)


def _gui_on_eqsl_reply(text):
    ui_show_information_dialog(tr("logbook.eqsl_answer"), text)


def _gui_on_qrz_reply(text):
    ui_show_information_dialog(tr("logbook.qrz_answer"), text)


# Messages from the core are shown without making the core thread wait for
# the user to close the dialog.

@_gui_on_main_thread()
def _gui_on_info(title, message):
    gui_message(title, message, "info", wait=False)


@_gui_on_main_thread()
def _gui_on_warning(title, message):
    gui_message(title, message, "warning", wait=False)


@_gui_on_main_thread()
def _gui_on_error(title, message):
    gui_message(title, message, "error", wait=False)


@_gui_on_main_thread()
def _gui_on_setup_required(title, message):
    """The station has no callsign or access code yet: open Settings and explain what to fill in."""
    tab_bar.select(4)
    _gui_show_settings_section("general")
    gui_message(title, message, "warning", wait=False)


@_gui_on_main_thread()
def _gui_on_login_refused(title, message, reason=0):
    """The server refused the login: explain why; for a callsign or code problem open Settings."""
    if reason in (1, 2):
        tab_bar.select(4)
        _gui_show_settings_section("general")
    gui_message(title, message, "error", wait=False)


@_gui_on_main_thread()
def _gui_on_fatal_error(title, message):
    """The core is shutting down: show why, and close the program when the user closes the message.

    The core thread that reported the error never waits for the user.
    """
    dialog = _GuiMessageBox(root, title, message, "error")

    def close_program(event):
        if event.widget is dialog:
            root.after_idle(on_closing)

    dialog.bind("<Destroy>", close_program, add="+")


_GUI_EVENT_HANDLERS = {
    "servers_loaded": _gui_on_servers_loaded,
    "rooms_loaded": _gui_on_rooms_loaded,
    "connecting": _gui_on_connecting,
    "connection_changed": _gui_on_connection_changed,
    "reconnecting": _gui_on_reconnecting,
    "ptt_state": _gui_on_ptt_state,
    "audio_level": _gui_on_audio_level,
    "transmission_logged": _gui_on_transmission_logged,
    "station_photo": _gui_on_station_photo,
    "station_identity": _gui_on_station_identity,
    "online_stations": _gui_on_online_stations,
    "alarms_updated": _gui_on_alarms_updated,
    "scan_state": _gui_on_scan_state,
    "scan_room": _gui_on_scan_room,
    "dmr_ids": _gui_on_dmr_ids,
    "user_ids_updated": _gui_on_user_ids_updated,
    "eqsl_reply": _gui_on_eqsl_reply,
    "qrz_reply": _gui_on_qrz_reply,
    "info": _gui_on_info,
    "warning": _gui_on_warning,
    "error": _gui_on_error,
    "setup_required": _gui_on_setup_required,
    "login_refused": _gui_on_login_refused,
    "fatal_error": _gui_on_fatal_error,
}


def _gui_on_event(event_name, /, **data):
    """Event listener registered with the core: route each event to its handler."""
    handler = _GUI_EVENT_HANDLERS.get(event_name)
    if handler is not None:
        handler(**data)


# ---------------------------------------------------------------------------
# Startup, main loop and shutdown
# ---------------------------------------------------------------------------

def start_gui():
    """Build the main window and start listening to the core events.

    Called after initialize_application() and load_language(), and
    before start_application(), so no core event is missed.
    """
    create_main_window()
    set_event_listener(_gui_on_event)
    apply_ui_scale()
    root.title("{}  v{}".format(tr("app.title"), GUI_APP_VERSION))
    create_main_interface()
    _gui_apply_settings()
    reload_logbook_table()


def run_gui(on_ready=None):
    """Show the window and run the Tk main loop until the window closes.

    on_ready (usually the core's start_application) runs on the main thread
    right after the window appears, so any message it shows has a visible
    window to sit on and slow network work never delays the window.
    """
    root.after(1000, refresh_monitor_table)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    gui_set_window_icon(resource_path(os.path.join("data", "app.ico")))
    grow_to_content(root)
    root.update_idletasks()
    if on_ready is not None:
        root.after(50, lambda: _gui_run_safely(on_ready))
    root.mainloop()


def _gui_offer_to_save_recording():
    """Before closing, offer to save a recording that holds audio."""
    if not (recording_active and has_recorded_audio()):
        return
    if not gui_ask_yes_no("REC", tr("rec.save_on_exit"), parent=root):
        return
    file_name = filedialog.asksaveasfilename(
        parent=root, filetypes=[("WAV Audio Files", "*.wav")], defaultextension=".wav"
    )
    if file_name:
        try:
            save_recording(file_name)
        except (OSError, wave.Error) as exc:
            gui_show_error("REC", str(exc), parent=root)


@_gui_on_main_thread()
def on_closing():
    """Stop the core, leave the server and close the window."""
    global _gui_alive
    if _gui_alive:
        _gui_offer_to_save_recording()
        # The window disappears at once; stopping the threads can take a
        # few seconds and the user should not see a frozen window meanwhile.
        try:
            root.withdraw()
        except tk.TclError:
            pass
    shutdown()
    set_event_listener(None)
    _gui_alive = False
    try:
        root.destroy()
    except tk.TclError:
        pass
