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
  No COPR; Tailscale comes from Fedora's own repo. **One exception: the
  NVIDIA driver from RPM Fusion nonfree**, see below.
- **Updates are explicit:** the auto-apply timer (which reboots on its own) is
  disabled. `tos update` stages; you reboot when ready.
- **Upstream content:** Omarchy themes are pinned by SHA, allowlisted,
  non-executable and reviewed (see UPSTREAM.md).
- **AI (Friday):** no auto-approve modes; OS-enforced dialog and password
  gates; no live package installs; read-only collection, redaction, explicit
  consent, 0600 reports and audit logs. See FRIDAY.md.

## Supply chain

- **Two signatures on every published image:**
  - **cosign key** (`COSIGN_PRIVATE_KEY` secret; public half at
    `image/signing/cosign.pub`). This is what machines enforce.
  - **keyless** (GitHub OIDC identity, logged in the Rekor transparency log),
    as public provenance anyone can check with `cosign verify`.
- **Enforced on the machine** after `tos signing enforce` (once per machine;
  it runs `bootc switch --enforce-container-sigpolicy`). From then on
  `bootc upgrade`, `tos update` and Friday's `system_update` only install
  `ghcr.io/rebelknightx84/tegendo-os` images signed with that key
  (`/etc/containers/policy.json` → `/etc/pki/containers/tegendo-os.pub`).
  A compromised GitHub account or registry can't push you an OS without the
  key. `tos signing` shows the state. Other images keep Fedora's default policy.
- **Why a key and not keyless for enforcement:** the container library bootc
  uses (containers/image) can only match keyless identities by email, and
  GitHub Actions identities are URIs. Support is an open upstream PR
  (containers/container-libs#625). When it ships, enforcement can move to
  keyless and the key can retire.
- **Key handling:** generated with `tools/make-cosign-key.sh` (plain openssl,
  EC P-256). Only the Actions secret holds the private key. CI converts it in
  a private temp dir with a one-time password and wipes it after signing.
- **Rotating the key:** ship the new public key *alongside* the old one for
  one release (`keyPaths` in the policy), because each machine verifies the
  next image with the policy it's currently running. Only then swap the secret.
- **Tested in CI** (`tests/signing-policy.sh`): the real signing script and
  the real policy, checked by skopeo (same library as bootc). Signed images
  are accepted; unsigned and wrong-key images are rejected.
- **Smaller updates:** images are rechunked (`rpm-ostree compose
  build-chunked-oci`) into content-based layers, so an update downloads what
  changed rather than the whole OS.
- **Image visibility:** if the ghcr package stays private, each machine needs
  a read-only registry token in `/etc/ostree/auth.json`. Making the image
  public is simpler; it contains no secrets (verify that stays true in review).
- **CI actions** are pinned to full commit SHAs; Dependabot bumps them weekly.

## Your choices at install time

- **Disk encryption (LUKS):** pick it in the Fedora installer. It can't be
  added in place.
- **Secure Boot:** works out of the box with Fedora's signed shim and kernel.
- **Secure Boot + NVIDIA:** after the first switch to an image with NVIDIA,
  run `tos mok enroll`, reboot, and approve the key in the blue MOK Manager
  screen. Then turn Secure Boot on in the firmware. `tos mok status` checks.

## NVIDIA driver

- **Source:** RPM Fusion nonfree, the long-standing community repo Fedora
  itself offers for NVIDIA. NVIDIA's own repo had no Fedora 45 build when
  this was set up; switching later means editing `image/nvidia/`.
- **Scope:** the repo exists only inside the image build, only for packages
  named `*nvidia*`, and is deleted before the image is finished. Its signing
  key comes from Fedora's `distribution-gpg-keys` package, so RPM Fusion's
  key reaches you through Fedora. Nothing compiles on your machines (no
  akmods/DKMS in the image).
- **Open kernel modules** (MIT/GPL). The build fails if it gets anything else.
- **Your key, your kernel trust.** CI signs the modules with your Machine
  Owner Key (`tools/make-mok-key.sh`; private half in the `MOK_PRIVATE_KEY`
  GitHub secret, public cert committed at `image/nvidia/tegendo-mok.der`).
  The build checks the key matches the cert and every module's signer, and
  CI checks the finished image contains no trace of the private key.
  **Anyone with that private key can get kernel code trusted by your
  machines**: keep it in your password manager, not on disk; protect the
  GitHub account with a hardware key. Pull-request builds never see it.
- **Rotation** means a new cert, re-enrolling every machine (`tos mok
  enroll`), and removing the old one (`mokutil --delete`).

## Gaming

- Steam and tools are Flathub Flatpaks (`image/flatpaks.txt`), installed
  system-wide on boot. Flathub is enabled unfiltered for this.
- `steam-devices` (Fedora) adds udev rules giving your user access to game
  controllers and VR headsets, a deliberate widening of device access.
- Steam's Flatpak sandbox is broad by design (devices, network, some of home).
  Flatseal (included) shows and tightens it; anti-cheat and Proton may break
  if you tighten too far.

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
