# Installing and uninstalling

System Budget Studio installs for one user and needs no administrator rights. The installers work offline and add no background service.

## Windows 10 and 11

Run `system-budget-studio-<version>-windows-x64-setup.exe`. It installs to `%LOCALAPPDATA%\Programs\System Budget Studio` and adds a Start menu entry. Tick *Add the command-line tool budget to my PATH* if you want `budget` in every terminal.

For a silent install: `setup.exe /VERYSILENT /CURRENTUSER /DIR="C:\Tools\SBS"`.

A portable alternative is `system-budget-studio-<version>-windows-x64-portable.zip`: extract it anywhere and start `system-budget-studio.exe`. Nothing is written outside the folder.

To uninstall use *Apps and features*, or run `unins000.exe` in the install folder.

## Linux (RHEL and Rocky 8 or newer, Ubuntu LTS)

```
tar xzf system-budget-studio-<version>-linux-x86_64.tar.gz
cd system-budget-studio
./install.sh
```

The script copies the program to `~/.local/opt/system-budget-studio`, links `system-budget-studio` and `budget` into `~/.local/bin`, adds an application-menu entry, and runs the self-test. Options: `--prefix DIR` for another folder, `--no-links`, `--no-desktop`. Installing again replaces the previous version. An existing folder that was not created by the installer is never overwritten.

The window needs the usual desktop libraries (EGL, OpenGL, xkbcommon, fontconfig). On a minimal RHEL 8 install them with `sudo dnf install mesa-libEGL mesa-libGL libxkbcommon libxkbcommon-x11 fontconfig xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil`. The command-line tool and the self-test work without a display.

To uninstall run `~/.local/opt/system-budget-studio/uninstall.sh`. It removes the program, the links and the menu entry that the installer created and nothing else.

## Your files

Projects, reports and exports live in folders you choose. Neither installing, upgrading nor uninstalling touches them. The tool keeps no settings, caches, logs or crash dumps outside your project folders.

## Checking an installation

```
budget --version
budget self-test
```

The self-test computes and renders a small budget in every report format and builds this guide, using only the installed files.

## Air-gapped machines

The installers contain every dependency. To install from source on a machine without internet access, use a mirrored wheel set: `pip install --no-index --find-links wheelhouse --require-hashes -r requirements.lock`.
