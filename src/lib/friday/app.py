"""Friday's window: a launcher-style overlay (Super+Space).

GTK4, drawn as a layer-shell overlay on COSMIC (gtk4-layer-shell) so it floats
above windows like COSMIC's own launcher; a plain undecorated window elsewhere.
It hides itself whenever a tool that needs your approval runs, so the
approval dialog is never underneath it.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import tomllib
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402
except (ValueError, ImportError):
    LayerShell = None

from . import VERSION  # noqa: E402
from .backends import MCP_CMD, STATE, Friday  # noqa: E402
from .markup import esc, to_pango  # noqa: E402

APP_ID = "org.tegendo.Friday"
QUICK = [
    "What needs my attention?",
    "Any updates waiting?",
    "Why is my disk filling up?",
    "Did anything crash recently?",
]
DEFAULT_COLORS = {
    "background": "#1a1b26", "lighter_background": "#24283b", "dark_background": "#13141c",
    "foreground": "#a9b1d6", "bright_foreground": "#c0caf5", "dark_foreground": "#565f89",
    "accent": "#7aa2f7", "magenta": "#ad8ee6", "red": "#f7768e", "green": "#9ece6a", "yellow": "#e0af68",
}


def theme_colors() -> dict[str, str]:
    """The active tos theme's colors (falls back to Tegendo/Tokyo Night)."""
    colors = dict(DEFAULT_COLORS)
    path = Path(os.environ.get("TOS_STATE", STATE)) / "current/theme/colors.toml"
    try:
        data = tomllib.loads(path.read_text())
        colors.update({k: v for k, v in data.items() if isinstance(v, str) and v.startswith("#")})
    except (OSError, tomllib.TOMLDecodeError):
        pass
    return colors


def css(c: dict[str, str]) -> str:
    return f"""
window.friday {{ background: transparent; }}
.card {{
  background: alpha({c['background']}, 0.97);
  border: 1px solid alpha({c['accent']}, 0.35);
  border-radius: 20px; padding: 18px 18px 12px 18px; margin: 28px;
  box-shadow: 0 16px 48px rgba(0,0,0,0.5);
}}
.title {{ color: {c['bright_foreground']}; font-weight: 700; font-size: 15px; }}
.backend {{ color: {c['dark_foreground']}; font-size: 12px; }}
entry.ask {{
  background: {c['lighter_background']}; color: {c['bright_foreground']};
  border: 1px solid alpha({c['accent']}, 0.25); border-radius: 14px;
  padding: 10px 14px; font-size: 17px; min-height: 28px;
}}
entry.ask:focus-within {{ border-color: {c['accent']}; }}
button.chip {{
  background: alpha({c['accent']}, 0.12); color: {c['accent']};
  border: none; border-radius: 999px; padding: 4px 12px; font-size: 13px; box-shadow: none;
}}
button.chip:hover {{ background: alpha({c['accent']}, 0.22); }}
.user-msg {{
  background: alpha({c['accent']}, 0.16); color: {c['bright_foreground']};
  border-radius: 14px; padding: 8px 12px;
}}
.friday-msg {{ color: {c['foreground']}; font-size: 14px; }}
.tool {{ color: {c['dark_foreground']}; font-size: 12px; }}
.tool.ok {{ color: alpha({c['green']}, 0.85); }}
.tool.denied {{ color: {c['yellow']}; }}
.note {{ color: {c['dark_foreground']}; font-style: italic; font-size: 12px; }}
.error {{ color: {c['red']}; }}
.footer {{ color: {c['dark_foreground']}; font-size: 11px; }}
button.stop {{ color: {c['red']}; background: none; border: none; box-shadow: none; font-size: 12px; }}
"""


def tool_titles() -> dict[str, str]:
    try:
        out = subprocess.run([MCP_CMD, "--list-tools"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return {}
    titles = {}
    for line in out.splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3:
            titles[parts[1]] = parts[2].strip()
    return titles


class FridayWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application):
        super().__init__(application=app, title="Friday")
        self.friday = Friday()
        self.colors = theme_colors()
        self.titles = tool_titles()
        self.busy = False
        self.answer: Gtk.Label | None = None
        self.answer_text = ""
        self.tools: dict[str, Gtk.Label] = {}
        self.hidden_for_approval: set[str] = set()

        provider = Gtk.CssProvider()
        provider.load_from_string(css(self.colors))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.add_css_class("friday")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_default_size(780, -1)
        self.overlay = self._layer_shell()
        self._build()
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

    # ---- placement ------------------------------------------------------------------
    def _layer_shell(self) -> bool:
        display = Gdk.Display.get_default()
        # Only ask layer-shell on Wayland (it asserts on other backends).
        if LayerShell is None or display.__gtype__.name != "GdkWaylandDisplay" or not LayerShell.is_supported():
            return False
        LayerShell.init_for_window(self)
        LayerShell.set_namespace(self, "friday")
        LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
        LayerShell.set_anchor(self, LayerShell.Edge.TOP, True)
        monitors = Gdk.Display.get_default().get_monitors()
        height = monitors.get_item(0).get_geometry().height if monitors.get_n_items() else 900
        LayerShell.set_margin(self, LayerShell.Edge.TOP, int(height * 0.14))
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.EXCLUSIVE)
        return True

    # ---- layout -----------------------------------------------------------------------
    def _build(self) -> None:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.add_css_class("card")

        header = Gtk.Box(spacing=10)
        logo = Gtk.Image.new_from_icon_name("tegendo-logo")
        logo.set_pixel_size(26)
        title = Gtk.Label(label="Friday", xalign=0)
        title.add_css_class("title")
        self.spinner = Gtk.Spinner()
        self.backend_label = Gtk.Label(label=self.friday.label, xalign=1, hexpand=True)
        self.backend_label.add_css_class("backend")
        for w in (logo, title, self.spinner, self.backend_label):
            header.append(w)
        card.append(header)

        self.entry = Gtk.Entry(placeholder_text="Ask Friday about this computer…")
        self.entry.add_css_class("ask")
        self.entry.connect("activate", lambda e: self.submit(e.get_text()))
        card.append(self.entry)

        self.chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4,
                                 column_spacing=6, row_spacing=6)
        for q in QUICK:
            b = Gtk.Button(label=q)
            b.add_css_class("chip")
            b.connect("clicked", lambda _b, q=q: self.submit(q))
            self.chips.append(b)
        card.append(self.chips)

        self.log = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                           propagate_natural_height=True, max_content_height=460)
        self.scroller.set_child(self.log)
        self.scroller.set_visible(False)
        card.append(self.scroller)

        footer = Gtk.Box(spacing=8)
        hint = Gtk.Label(label="Esc hide  ·  Ctrl+N new chat  ·  Changes always ask you first",
                         xalign=0, hexpand=True)
        hint.add_css_class("footer")
        self.stop = Gtk.Button(label="Stop")
        self.stop.add_css_class("stop")
        self.stop.set_visible(False)
        self.stop.connect("clicked", lambda _b: self.friday.cancel())
        footer.append(hint)
        footer.append(self.stop)
        card.append(footer)
        self.set_child(card)

    # ---- behaviour ---------------------------------------------------------------------
    def _on_key(self, _ctl, keyval, _code, state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.set_visible(False)
            return True
        if keyval in (Gdk.KEY_n, Gdk.KEY_N) and state & Gdk.ModifierType.CONTROL_MASK:
            self.new_chat()
            return True
        return False

    def show_focused(self) -> None:
        self.present()
        self.entry.grab_focus()

    def new_chat(self) -> None:
        if self.busy:
            return
        self.friday.reset()
        while (child := self.log.get_first_child()) is not None:
            self.log.remove(child)
        self.scroller.set_visible(False)
        self.chips.set_visible(True)
        self.backend_label.set_label(self.friday.label)
        self.entry.grab_focus()

    def _label(self, css_class: str, markup: str = "", text: str = "", **kw) -> Gtk.Label:
        lbl = Gtk.Label(wrap=True, xalign=0, selectable=True, **kw)
        lbl.set_wrap_mode(2)  # Pango.WrapMode.WORD_CHAR
        lbl.add_css_class(css_class)
        if markup:
            lbl.set_markup(markup)
        else:
            lbl.set_text(text)
        self.log.append(lbl)
        self.scroller.set_visible(True)
        return lbl

    def submit(self, text: str) -> None:
        text = text.strip()
        if not text or self.busy:
            return
        self.entry.set_text("")
        self.chips.set_visible(False)
        self._label("user-msg", text=text, halign=Gtk.Align.END)
        self.answer, self.answer_text = None, ""
        self._set_busy(True)
        threading.Thread(target=self.friday.send, args=(text, self._emit), daemon=True).start()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.spinner.set_spinning(busy)
        self.stop.set_visible(busy)
        self.entry.set_sensitive(not busy)
        if not busy:
            self.entry.grab_focus()

    def _emit(self, ev: dict) -> None:  # worker thread
        GLib.idle_add(self._on_event, ev)

    def _scroll_end(self) -> bool:
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False

    def _on_event(self, ev: dict) -> bool:  # GTK thread
        t = ev["type"]
        if t == "text":
            self.answer_text += ev["text"]
            if self.answer is None:
                self.answer = self._label("friday-msg")
            markup = to_pango(self.answer_text, self.colors["dark_background"], self.colors["bright_foreground"])
            try:
                self.answer.set_markup(markup)
            except GLib.Error:
                self.answer.set_text(self.answer_text)
        elif t == "tool_start":
            title = self.titles.get(ev["name"], ev["name"].replace("_", " "))
            self.tools[ev["id"]] = self._label("tool", text=f"◌  {title}…")
            self.answer = None
            self.answer_text = ""
            if ev.get("tier") in ("user", "system"):
                # Approval dialog incoming: get out of its way until it's answered.
                self.hidden_for_approval.add(ev["id"])
                self.set_visible(False)
        elif t == "tool_end":
            lbl = self.tools.get(ev["id"])
            if lbl:
                title = lbl.get_text()[3:].rstrip("…")
                if ev["ok"]:
                    lbl.set_text(f"✓  {title}")
                    lbl.add_css_class("ok")
                else:
                    lbl.set_text(f"✗  {title}: {ev.get('summary') or 'failed'}")
                    lbl.add_css_class("denied")
            if ev["id"] in self.hidden_for_approval:
                self.hidden_for_approval.discard(ev["id"])
                self.show_focused()
        elif t == "note":
            self._label("note", text=ev["text"])
            self.backend_label.set_label(self.friday.label)
        elif t == "error":
            self._label("error", markup=f"<b>Couldn't finish:</b> {esc(ev['text'])}")
            self._set_busy(False)
        elif t == "done":
            self._set_busy(False)
        GLib.idle_add(self._scroll_end)
        return False


class FridayApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window: FridayWindow | None = None
        self._held = False

    def _ensure(self) -> FridayWindow:
        if self.window is None:
            self.window = FridayWindow(self)
        if not self._held:  # stay running while hidden, so Super+Space is instant
            self.hold()
            self._held = True
        return self.window

    def do_command_line(self, cmdline) -> int:
        args = cmdline.get_arguments()[1:]
        if "--version" in args:
            cmdline.print_literal(f"tos-friday {VERSION}\n")
            return 0
        win = self._ensure()
        if "--background" in args:
            return 0
        if "--show" in args or not win.get_visible():
            win.show_focused()
        else:
            win.set_visible(False)
        return 0


def main(argv: list[str]) -> int:
    return FridayApp().run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
