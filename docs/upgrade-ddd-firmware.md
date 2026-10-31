# Upgrading a Domesday Duplicator from the original firmware (Linux)

Written **2026-10-31** for the machine `solo` (Fedora 44, 192.168.43.182) and a board that reports USB ID
`1d50:603b` (original firmware). Based on the upstream project's own documentation for **gui-v3.2.0** and
**fw-v3.2.0**. **Nothing in this document has been run on the board yet.** Items marked *[untested]* are my reading
of the upstream pages, not something that has been tried here.

Companion documents: `docs/migration-plan.md` (why we are doing this), and upstream's pages listed at the end.

---

## 0. Read this before you start

- **This is a one-way step for the current toolkit.** After the upgrade the board identifies itself as `1209:2347`.
  The forked `DomesdayDuplicator` program the toolkit calls today only knows the old ID, so it will no longer find the
  board. Upstream documents no way to return a board to the original firmware.
- **Do a baseline capture first.** Get one capture working on the original firmware (through MISRC-GUI's legacy DdD
  profile, or the current fork) so you have a known-good reference and a fallback until the toolkit can capture
  through a new backend.
- **Unknown: the clockgen-lite mod.** Upstream says one wire (`CTL_07`) is driven by the FX3 under the original
  design and by the FPGA under the current one. Whether your clock bridge touches that wire has not been checked.
  Photograph the bridge wiring before you touch anything, and do not remove it unless you have a reason to.
  *[unverified]*
- **The board cannot be bricked by stopping part way**, according to upstream: fitting jumper J4 always reaches the
  FX3's boot ROM, JTAG always reaches the FPGA flash, and every step can be run again from the start.
- **The command-line tools are not available.** `ddd-update` and `ddd-jtag` exist but are not in the released
  packages (upstream builds them only through its Nix development environment). The Flatpak's graphical wizard is
  the supported route, so you need a graphical session on `solo`.

## 1. What you need

**Hardware**

| Item | Notes |
| ---- | ----- |
| The Domesday Duplicator, taken out of its case | The DE0-Nano's mini-USB socket cannot be reached with the case on |
| The kit's **USB 3.0 cable** | Into a USB 3 port directly on `solo`, not through a hub |
| A **mini-USB cable that carries data** | Charge-only cables are the commonest failure; the board lights up either way |
| A **jumper (shunt)** | For header J4 (labelled `PMODE`) on the FX3 board |
| About 30 minutes | The programming is about 5 minutes; most of the time is setup |

**Files** (all downloaded on `solo`, into `~/ddd-upgrade/`)

| File | From | Used for |
| ---- | ---- | -------- |
| `DomesdayDuplicator-3.2.0.flatpak` | release `gui-v3.2.0` | The capture application, which contains the bring-up wizard |
| `SHA256SUMS` (from `gui-v3.2.0`) | release `gui-v3.2.0` | Checking the Flatpak |
| `domesday-duplicator-update-3.2.0.dddfw` (2,048,000 bytes) | release `fw-v3.2.0` | The firmware and gateware bundle. Upstream says the installed app already carries a copy, but download it so you can choose it explicitly |
| `SHA256SUMS` (from `fw-v3.2.0`) | release `fw-v3.2.0` | Checking the `.dddfw`. Saved under a different name below so the two lists do not overwrite each other |
| `70-domesday-duplicator.rules` | upstream repo, `fx3/programmer/configs/` | Lets the app open the board and the USB-Blaster JTAG cable without root |

`fw-v3.2.0` **requires** `gui-v3.2.0`; use this matched pair.

## 2. Download and check (on `solo`)

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

Both lines must say `OK`. Stop if either does not.

## 3. Install the application (on `solo`)

Flatpak 1.18.4 is already installed on `solo`.

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
```

```bash
flatpak install --user ~/ddd-upgrade/DomesdayDuplicator-3.2.0.flatpak
```

The first install also downloads the KDE runtime from Flathub, which is large. Run the app with:

```bash
flatpak run io.github.simoninns.DddGui
```

You need a graphical login on `solo` for this (at the time of writing it only had a text-console session).

## 4. Install the device rules (on `solo`, needs sudo)

A Flatpak cannot install these; they must go on the host. Keep the `70-` file name: upstream warns that a name
sorting after `73-seat-late.rules` leaves the access tag with nothing to act on.

```bash
sudo curl -fL -o /etc/udev/rules.d/70-domesday-duplicator.rules https://raw.githubusercontent.com/Domesday86/DomesdayDuplicator/main/fx3/programmer/configs/70-domesday-duplicator.rules
```

```bash
sudo udevadm control --reload-rules && sudo udevadm trigger
```

This one file covers all the USB identities the bring-up uses: the FX3 in boot-ROM mode (`04b4:00f3`), the board
running new firmware (`1209:2347`), and the DE0-Nano's on-board USB-Blaster (`09fb:6001`).

`solo` already has `50-domesday-duplicator-power.rules` and `99-domesday-duplicator.rules`. They match only the old
ID `1d50:603b`. **Leave them in place until the upgrade is done** so the old firmware keeps working in the meantime.

## 5. Check the app sees the board (before touching hardware)

Start the app with the board connected as it is today (USB 3.0 only). It should be named on screen as running the
original firmware (`1d50:603b`), not "no device". Upstream deliberately never opens a board in that state. If it says
nothing found at all, recheck the rules and replug the USB cable.

## 6. Prepare the hardware

1. Stop any capture. Close the toolkit and anything else using the board.
2. **Photograph** the unit, especially the clockgen-lite bridge wiring (see section 0).
3. Power down by unplugging **both** cables if connected. Open the case.
4. Fit the jumper across **J4** (the two-pin `PMODE` header) on the FX3 board. Upstream's page has a photograph:
   `capture-gui/bringing-up-a-board.md` shows `fx3-j4-fitted.jpeg` and `fx3-j4-removed.jpeg`.
5. Connect **both** cables: the kit's USB 3.0 cable into a USB 3 port on `solo`, and the mini-USB data cable from
   the DE0-Nano to another port on `solo`.

**A power cycle always means unplugging both cables.** The unit is powered through either one, so pulling only one
leaves it running and looking normal while nothing has happened. This is the most common cause of a step waiting
forever.

## 7. Run the bring-up wizard

In the app: **Tools ▸ Firmware ▸ Bring up a new or legacy board…** Do not use *Update firmware…*; that is only for
boards already running the current firmware.

| Page | What to do | What you should see |
| ---- | ---------- | ------------------- |
| 1. What this does | Read the checklist, press Next | Nothing is written yet |
| 2. Both boards, and jumper J4 | Jumper fitted (step 6.4). Unplug both cables, then plug both back in | FX3 row ticks *In its boot ROM after restarting*. FPGA row ticks *Found and opened* |
| 3. The update file | Accept the bundled file, or press the button and pick `~/ddd-upgrade/domesday-duplicator-update-3.2.0.dddfw` | Signature and digests checked before anything is written |
| 4. Load the gateware | Press **Load the gateware** (about 3 seconds) | Becomes *Gateware loaded*. Nothing is written permanently yet |
| 5. Program the board | Press **Program the board** | EEPROM, factory image, then application image are written. The bar pauses every few seconds while flash blocks are erased; that is normal |
| 6. Remove jumper J4 | Take the jumper off. **Do not unplug anything yet.** Press Next | The app cannot detect the jumper, so it just asks |
| 7. Power cycle | Unplug **both** cables, wait a couple of seconds, plug **both** back in | *Waiting for both cables to come out*, then *Waiting for the Duplicator to come back*, then *All done* |
| 8. What it is running | Read the result, then unplug the **mini-USB**, put the case on, press Close | Four checks pass, including the FPGA being on the **application gateware** |

If page 2 shows the FX3 row as amber (*original Duplicator firmware … 1d50:603b*), that is the expected state for
your board; carry on.

## 8. Check it worked

```bash
lsusb | grep -i -E "1209:2347|1d50:603b"
```

Expect `1209:2347` and **no** `1d50:603b`. Then restart the app and read the **Status** line in the Capture panel:
it should say *Ready*. Do a short capture (10-20 seconds, anywhere you have disk space) and look at the Statistics
panel for the sequence/integrity indicators; this is the new firmware's dropped-sample check.

*[untested]* Check the clockgen audio device still appears (`cat /proc/asound/cards` should still list
`CXADC+ADC-ClockGen`) and that the sync flow still starts, once a backend for the new ID exists.

## 9. Afterwards

- **USB autosuspend rule.** `50-domesday-duplicator-power.rules` stops Linux powering the port down during capture
  (it exists "to prevent buffer underflows"), but only for the old ID. Create the equivalent for the new ID *[untested]*:

  ```bash
  sed -e 's/ATTR{idVendor}=="1d50"/ATTR{idVendor}=="1209"/' -e 's/ATTR{idProduct}=="603b"/ATTR{idProduct}=="2347"/' /etc/udev/rules.d/50-domesday-duplicator-power.rules | sudo tee /etc/udev/rules.d/50-domesday-duplicator-power-v1.rules
  ```

  I ran the `sed` part against `solo`'s file and the output is the same two rules with the new ID. Then reload
  with `sudo udevadm control --reload-rules && sudo udevadm trigger` and replug.
- The old `99-domesday-duplicator.rules` and the old half of the power rule are now unused. They are harmless.
- The toolkit's forked `DomesdayDuplicator` will not find the board. Capture through `ddd-gui` or MISRC-GUI's new
  DdD protocol profile instead (see `docs/migration-plan.md`, Phase 3).
- Future firmware updates use **Tools ▸ Firmware ▸ Update firmware…** over the single USB cable, with no jumper.

## 10. If something goes wrong

| What you see | What it usually is |
| ------------ | ------------------ |
| A page waits for a board that never returns | Only one cable came out. Unplug **both**, count to three, reconnect |
| *The board did not lose power* on page 7 | The same thing, caught: the USB 3.0 cable alone came out |
| FPGA row *Nothing found* | Charge-only mini-USB cable. Also possible: rules not installed, or the Flatpak sandbox not allowed to see the USB-Blaster *[untested]* |
| FPGA row *attached but could not be opened* | Something else holds the cable (Quartus's `jtagd`), or the rules are missing |
| Page 7 says *the board has come back in its boot ROM* | Jumper J4 is still fitted. Go back and remove it |
| Page 5 stops with *cannot be opened under that identifier* | Not expected on Linux with the rules installed; replug and rerun the wizard |
| The file is refused on page 3 | Wrong or older bundle. Use `domesday-duplicator-update-3.2.0.dddfw` |

Any stopped run can simply be started again from page 1. Upstream also has an *If an update fails* page for a board
that was working and then stopped answering.

## 11. Sources (upstream, official)

- Documentation site: https://domesday86.github.io/DomesdayDuplicator/ (source in `docs/content/` of
  https://github.com/Domesday86/DomesdayDuplicator)
- Pages used: `capture-gui/bringing-up-a-board.md`, `capture-gui/install-flatpak.md`, `capture-gui/quick-start.md`,
  `development/hardware-programming/linux-device-access.md`, `development/device-update-mechanism.md`
- Releases: https://github.com/Domesday86/DomesdayDuplicator/releases/tag/gui-v3.2.0 and `.../tag/fw-v3.2.0`
