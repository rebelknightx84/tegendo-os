# Security

## Built into the image

- **Immutable OS:** `/usr` is read-only and replaced as a whole on update.
  The previous image stays bootable; `tos undo` switches back.
- **SELinux enforcing** (Fedora default), never disabled by tegendo-os or Friday.
- **Firewall:** firewalld default zone `tegendo` drops all unsolicited inbound
  traffic except DHCPv6 replies. Fedora Workstation's own default allows ports
  1025-65535 in; this doesn't. `tailscale0` sits in the `trusted` zone.
- **SSH:** off. If you enable it: key-only, no root login, no X11 forwarding.
- **Packages:** official Fedora repos only (CI checks `image/packages.txt`).
  No COPR or third-party repos; Tailscale comes from Fedora's own repo.
- **Updates are explicit:** the auto-apply timer (which reboots on its own) is
  disabled. `tos update` stages; you reboot when ready.
- **Upstream content:** Omarchy themes are pinned by SHA, allowlisted,
  non-executable and reviewed (see UPSTREAM.md).
- **AI (Friday):** no auto-approve modes; OS-enforced dialog and password
  gates; no live package installs; read-only collection, redaction, explicit
  consent, 0600 reports and audit logs. See FRIDAY.md.

## Supply chain

- **Image signing:** CI signs every pushed image with Sigstore keyless signing
  (GitHub OIDC identity, logged in Rekor). Verify any image with the
  `cosign verify` command in the CI run summary.
- **Not yet enforced on the machine.** `bootc switch` / `bootc upgrade` don't
  check that signature until a containers policy requiring it is in place
  (`/etc/containers/policy.json` with a `sigstoreSigned` rule for
  `ghcr.io/<owner>/tegendo-os`). That's the next hardening step. Until then,
  your trust is in the GitHub account and the registry's TLS.
- **Image visibility:** if the ghcr package stays private, each machine needs
  a read-only registry token in `/etc/ostree/auth.json`. Making the image
  public is simpler; it contains no secrets (verify that stays true in review).
- **CI actions** are pinned to full commit SHAs; Dependabot bumps them weekly.

## Your choices at install time

- **Disk encryption (LUKS):** pick it in the Fedora installer. It can't be
  added in place.
- **Secure Boot:** works out of the box with Fedora's signed shim and kernel.
- **NVIDIA (not in the image yet):** the proprietary driver needs a kernel
  module signed with a key your firmware trusts (one-time MOK enrollment).
  Options to decide on: build and sign the module in CI with your own key
  (most control, most work), or reuse Universal Blue's prebuilt signed
  modules (less work, but you trust their signing key with kernel code).

## Things to watch

- **Docker bypasses firewalld** if you ever add it: published ports go around
  your zone rules. Bind to 127.0.0.1 unless you mean to expose a port.
  Podman (rootless, the default here) doesn't have this problem.
- **Flatpak permissions:** apps from Flathub run sandboxed, but some request
  broad access (home folder, devices). Check with `flatpak info --show-permissions <app>`;
  Flatseal (a Flatpak) makes it easy to tighten.
- **Distrobox containers share your home folder** and aren't a security
  boundary; they're for compatibility, not isolation.
- **Cloud agents see your report.** Redaction catches common patterns, not
  every secret. `ollama` keeps data on your network.
