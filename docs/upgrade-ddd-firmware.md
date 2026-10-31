# Upgrading a Domesday Duplicator from the original firmware (Linux)

How to bring a Domesday Duplicator (DdD) that is running the **original firmware** (USB ID `1d50:603b`) up to the
current firmware and gateware, using the upstream project's capture application on **Linux**.

Based on the upstream project's own documentation for **gui-v3.2.0** and **fw-v3.2.0** (written 2026-10-31). The
steps follow upstream's pages, but this guide has not been run end to end on hardware. Anything marked
*[untested]* is an interpretation of upstream's text rather than something that has been tried. Upstream's own
pages, listed at the end, are the authority if they differ.

---

## 0. Read this before you start

- **This is a one-way step for software built for the old firmware.** After the upgrade the board identifies itself
  as `1209:2347` instead of `1d50:603b`. Any program that looks for the old ID, including older Domesday Duplicator
  command-line builds and forks of the old Qt application, will no longer find the board. Upstream documents no way
  to return a board to the original firmware.
- **Make a known-good capture first.** If you can, record a reference capture on the original firmware before
  upgrading, so you have something to compare against and a fallback while you move your tools over.
- **Modified units.** Upstream says one signal (`CTL_07`) is driven by the FX3 board under the original design and by
  the FPGA under the current one. If your unit carries modifications, such as an external clock or clock-bridge mod,
  check whether any of it touches that signal before you begin, and photograph the wiring. Upstream has not said
  anything about such mods. *[unverified]*
- **The board cannot be bricked by stopping part way**, according to upstream: fitting jumper J4 always reaches the
  FX3's boot ROM, JTAG always reaches the FPGA's configuration flash, and every step can be run again from the
  start.
- **The command-line tools are not available.** `ddd-update` and `ddd-jtag` exist, but are not in the released
  packages (upstream builds them only through its Nix development environment). The Flatpak's graphical wizard is
  the supported route, so you need a graphical session on the computer the board is attached to.

## 1. What you need

**Hardware**

| Item | Notes |
| ---- | ----- |
| The Domesday Duplicator, out of its case | The DE0-Nano's mini-USB socket cannot be reached with the case on |
| The kit's **USB 3.0 cable** | Plug it into a USB 3 port directly on the computer, not through a hub |
| A **mini-USB cable that carries data** | Charge-only cables are the commonest failure; the board lights up either way |
| A **jumper (shunt)** | For header J4 (labelled `PMODE`) on the FX3 board |
| About 30 minutes | The programming itself is about 5 minutes; most of the time is setup |

**Files** (downloaded into `~/ddd-upgrade/`)

| File | From | Used for |
| ---- | ---- | -------- |
| `DomesdayDuplicator-3.2.0.flatpak` | release `gui-v3.2.0` | The capture application, which contains the bring-up wizard |
| `SHA256SUMS` | release `gui-v3.2.0` | Checking the Flatpak |
| `domesday-duplicator-update-3.2.0.dddfw` (2,048,000 bytes) | release `fw-v3.2.0` | The firmware and gateware bundle. Upstream says the installed app already carries a copy, but download it so you can choose it explicitly |
| `SHA256SUMS` (saved as `SHA256SUMS-fw`) | release `fw-v3.2.0` | Checking the `.dddfw`. Saved under a different name so the two lists do not overwrite each other |
| `70-domesday-duplicator.rules` | upstream repository, `fx3/programmer/configs/` | Lets the app open the board and the USB-Blaster JTAG cable without root |

`fw-v3.2.0` **requires** `gui-v3.2.0`; use this matched pair.

## 2. Download and check

Each command is a single line.

```bash
mkdir -p ~/ddd-upgrade && cd ~/ddd-upgrade
```

```bash
curl -fLO https://github.com/Domesday86/DomesdayDuplicator/releases/download/gui-v3.2.0/DomesdayDuplicator-3.2.0.flatpak && curl -fLO https://github.com/Domesday86/DomesdayDuplicator/releases/download/gui-v3.2.0/SHA256SUMS
```

```bash
curl -fLO https://github.com/Domesday86/DomesdayDuplicator/releases/download/fw-v3.2.0/domesday-duplicator-update-3.2.0.dddfw && curl -fL -o SHA256SUMS-fw https://github.com/Domesday86/DomesdayDuplicator/releases/download/fw-v3.2.0/SHA256SUMS
```

```bash
sha256sum -c SHA256SUMS --ignore-missing && sha256sum -c SHA256SUMS-fw --ignore-missing
```

Both must report `OK`. Stop if either does not.

## 3. Install the application

You need Flatpak (`flatpak --version` to check; most distributions package it). Then:

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

```bash
flatpak install --user ~/ddd-upgrade/DomesdayDuplicator-3.2.0.flatpak
```

The first install also downloads the KDE runtime from Flathub, which is large. Run the application with:

```bash
flatpak run io.github.simoninns.DddGui
```

This needs a graphical login. A text-only console session is not enough.

## 4. Install the device rules (needs sudo)

A Flatpak cannot install these; they belong on the host. Keep the `70-` file name: upstream warns that a name sorting
after `73-seat-late.rules` leaves the access tag with nothing to act on.

```bash
sudo curl -fL -o /etc/udev/rules.d/70-domesday-duplicator.rules https://raw.githubusercontent.com/Domesday86/DomesdayDuplicator/main/fx3/programmer/configs/70-domesday-duplicator.rules
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

This one file covers every USB identity the bring-up uses: the FX3 in boot-ROM mode (`04b4:00f3`), the board running
the current firmware (`1209:2347`), and the DE0-Nano's on-board USB-Blaster (`09fb:6001`).

If you already have rules for the old ID `1d50:603b` (for example from an older capture guide), leave them in place
until the upgrade is finished, so the old firmware keeps working in the meantime.

## 5. Check the application can see the board (before touching any hardware)

Start the application with the board connected as it is today (USB 3.0 cable only). It should name the board as
running the original firmware (`1d50:603b`), not report "no device". Upstream deliberately never opens a board in that
state. If it finds nothing at all, recheck the rules and replug the USB cable.

## 6. Prepare the hardware

1. Stop any capture and close anything else that uses the board.
2. **Photograph** the unit, including any modifications or added wiring (see section 0).
3. Unplug **both** cables if either is connected. Open the case.
4. Fit the jumper across **J4** (the two-pin `PMODE` header) on the FX3 board. Upstream's bring-up page shows a
   photograph of the fitted and removed positions.
5. Connect **both** cables: the kit's USB 3.0 cable to a USB 3 port, and the mini-USB data cable from the DE0-Nano
   to another port on the same computer.

**A power cycle always means unplugging both cables.** The unit is powered through either one, so pulling only one
leaves it running and looking normal while nothing has happened. This is the most common reason a step waits
forever.

## 7. Run the bring-up wizard

In the application: **Tools ▸ Firmware ▸ Bring up a new or legacy board…** Do not use *Update firmware…*; that is
only for boards already running the current firmware.

| Page | What to do | What you should see |
| ---- | ---------- | ------------------- |
| 1. What this does | Read the checklist, press Next | Nothing is written yet |
| 2. Both boards, and jumper J4 | Jumper fitted (step 6.4). Unplug both cables, then plug both back in | FX3 row ticks *In its boot ROM after restarting*. FPGA row ticks *Found and opened* |
| 3. The update file | Accept the bundled file, or use the button to pick `~/ddd-upgrade/domesday-duplicator-update-3.2.0.dddfw` | Signature and digests are checked before anything is written |
| 4. Load the gateware | Press **Load the gateware** (about 3 seconds) | Becomes *Gateware loaded*. Nothing is written permanently yet |
| 5. Program the board | Press **Program the board** | EEPROM, factory image, then application image are written. The bar pauses every few seconds while flash blocks are erased; that is normal |
| 6. Remove jumper J4 | Take the jumper off. **Do not unplug anything yet.** Press Next | The application cannot detect the jumper, so it just asks |
| 7. Power cycle | Unplug **both** cables, wait a couple of seconds, plug **both** back in | *Waiting for both cables to come out*, then *Waiting for the Duplicator to come back*, then *All done* |
| 8. What it is running | Read the result, then unplug the **mini-USB**, put the case back on, press Close | Four checks pass, including the FPGA running the **application gateware** |

If page 2 shows the FX3 row as amber (*original Duplicator firmware … 1d50:603b*), that is the expected state for a
board being upgraded from the original firmware; carry on.

## 8. Check it worked

```bash
lsusb | grep -i -E "1209:2347|1d50:603b"
```

Expect `1209:2347` and **no** `1d50:603b`. Restart the application and read the **Status** line in the Capture
panel; it should say *Ready*. Do a short capture (10 to 20 seconds, anywhere with disk space) and look at the
Statistics panel for the sequence and integrity indicators. That is the current firmware's dropped-sample check, which
the original firmware cannot provide.

## 9. Afterwards

- **USB autosuspend.** Some capture guides add a udev rule that stops Linux powering down the board's USB port during
  a capture, to avoid buffer underflows. Such a rule is tied to the old ID. If you have one, make the equivalent for
  the new ID. For a rules file at `/etc/udev/rules.d/50-domesday-duplicator-power.rules` this command writes a
  copy for `1209:2347` *[untested as a whole; the `sed` part was checked on a sample file]*:

  ```bash
  sed -e 's/ATTR{idVendor}=="1d50"/ATTR{idVendor}=="1209"/' -e 's/ATTR{idProduct}=="603b"/ATTR{idProduct}=="2347"/' /etc/udev/rules.d/50-domesday-duplicator-power.rules | sudo tee /etc/udev/rules.d/50-domesday-duplicator-power-v1.rules
  ```

  Then reload with `sudo udevadm control --reload-rules && sudo udevadm trigger` and replug the board.
- Rules written for the old ID are now unused. They are harmless.
- Software built for the old firmware will not find the board (see section 0). Use the upstream `ddd-gui`
  application, or another program that supports the current protocol.
- Future firmware updates use **Tools ▸ Firmware ▸ Update firmware…** over the single USB cable, with no jumper.

## 10. If something goes wrong

| What you see | What it usually is |
| ------------ | ------------------ |
| A page waits for a board that never returns | Only one cable came out. Unplug **both**, count to three, reconnect |
| *The board did not lose power* on page 7 | The same thing, caught: only the USB 3.0 cable came out |
| FPGA row *Nothing found* | Charge-only mini-USB cable. Also possible: rules not installed, or the Flatpak sandbox not allowed to see the USB-Blaster *[untested]* |
| FPGA row *attached but could not be opened* | Something else holds the cable (for example Quartus's `jtagd`), or the rules are missing |
| Page 7 says *the board has come back in its boot ROM* | Jumper J4 is still fitted. Go back and remove it |
| Page 5 stops with *cannot be opened under that identifier* | Not expected on Linux with the rules installed; replug and run the wizard again |
| The file is refused on page 3 | Wrong or older bundle. Use `domesday-duplicator-update-3.2.0.dddfw` |

Any stopped run can simply be started again from page 1. Upstream also has an *If an update fails* page for a board
that was working and then stopped answering.

## 11. Sources (upstream, official)

- Documentation site: https://domesday86.github.io/DomesdayDuplicator/ (source in `docs/content/` of
  https://github.com/Domesday86/DomesdayDuplicator)
- Pages used: `capture-gui/bringing-up-a-board.md`, `capture-gui/install-flatpak.md`, `capture-gui/quick-start.md`,
  `development/hardware-programming/linux-device-access.md`, `development/device-update-mechanism.md`
- Releases: https://github.com/Domesday86/DomesdayDuplicator/releases/tag/gui-v3.2.0 and `.../tag/fw-v3.2.0`
