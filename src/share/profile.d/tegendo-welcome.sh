# shellcheck shell=sh
# Tegendo OS terminal welcome: fastfetch + a few hints, once per boot.
# Turn it off:  touch ~/.config/tegendo-os/no-welcome   (or export TOS_WELCOME=0)

case $- in *i*) ;; *) return 0 ;; esac   # interactive shells only (this file is sourced)
[ "${TOS_WELCOME:-1}" = 0 ] && return 0
[ -e "${XDG_CONFIG_HOME:-$HOME/.config}/tegendo-os/no-welcome" ] && return 0
[ -e /run/.containerenv ] && return 0          # not inside Distrobox/Toolbx
[ -n "${XDG_RUNTIME_DIR:-}" ] || return 0
[ -e "$XDG_RUNTIME_DIR/tegendo-welcome" ] && return 0
: >"$XDG_RUNTIME_DIR/tegendo-welcome" 2>/dev/null || return 0

command -v fastfetch >/dev/null 2>&1 && fastfetch
printf '  \033[38;2;122;162;247mtos status\033[0m · \033[38;2;122;162;247mtos update\033[0m · \033[38;2;122;162;247mtos theme list\033[0m · \033[38;2;187;154;247mtos agent "ask Friday"\033[0m\n\n'
