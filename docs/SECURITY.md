# Security

## Automated

- **Firewall:** ufw, deny all inbound, allow outbound, allow in on `tailscale0`.
- **SSH:** if OpenSSH is installed, key-only auth, no root login, no X11
  forwarding (validated with `sshd -t`). The server is never enabled for you.
- **Snapshots:** `snap-pac` snapshots before and after every pacman
  transaction. Agents are told to snapshot before changes.
- **Repo integrity:** preflight refuses to run if CachyOS repos are missing or
  an `[omarchy]` repo exists.
- **Upstream content:** pinned SHA, allowlisted, non-executable, reviewed
  (see UPSTREAM.md).
- **AI:** no auto-approve modes. Read-only collection, redaction, explicit
  consent, 0600 reports. The crash watcher runs with `NoNewPrivileges` and a
  read-only filesystem view.

## Checked and reported, not automated (mistakes here stop the machine booting)

- **Disk encryption (LUKS):** set it up in the CachyOS installer. Can't be
  added in place safely.
- **Secure Boot:** optional, via `sbctl` with your own keys. Rough path:
  `sbctl status` → setup mode in firmware → `sbctl create-keys` →
  `sbctl enroll-keys -m` (keep Microsoft keys for GPU option ROMs) → sign the
  Limine EFI binary and kernels. NVIDIA DKMS modules complicate this, so read
  the CachyOS wiki first and keep a live USB handy.
- **NVIDIA kernel cmdline:** `tos_fix_limine_cmdline: true` lets Ansible add
  `nvidia_drm.modeset=1 nvidia_drm.fbdev=1` to `/etc/default/limine` and take
  a snapshot first. Confirm the LTS entries afterwards.

## Things to watch

- **Docker bypasses ufw.** Published ports are inserted into iptables ahead of
  ufw's rules. Bind to localhost (`-p 127.0.0.1:8080:80`) unless you mean to
  expose a port. Podman (rootless) doesn't have this problem.
- **AUR = third-party code.** Read every PKGBUILD diff `paru` shows you.
- **CI actions:** `actions/checkout` is pinned to a full commit SHA;
  Dependabot (`.github/dependabot.yml`) opens weekly PRs to bump it.
- **Your future package-signing key** (roadmap step 2): keep it on a YubiKey
  or offline, with a revocable CI subkey. Whoever holds it can push updates
  to every machine that trusts your repo.
- **Cloud agents see your report.** Redaction catches common patterns, not
  every secret. `ollama` keeps data on your network.
