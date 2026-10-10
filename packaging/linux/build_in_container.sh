#!/usr/bin/env bash
# Builds the Linux bundle on Rocky Linux 8 (glibc 2.28), so that it also runs on RHEL/Rocky 8+ and
# on newer distributions such as Ubuntu LTS, then installs it as an unprivileged user (no admin
# rights) and uninstalls it again. Run inside the rockylinux:8 container with the repository
# mounted at /src:
#   docker run --rm -e HOST_UID=$(id -u) -e HOST_GID=$(id -g) -v "$PWD":/src -w /src \
#       rockylinux:8 bash packaging/linux/build_in_container.sh
set -euo pipefail
cd /src

dnf -y install python3.11 python3.11-pip mesa-libEGL mesa-libGL libxkbcommon libxkbcommon-x11 \
    dbus-libs fontconfig glib2 xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil \
    libXrender tar gzip shadow-utils
python3.11 -m venv /opt/venv
/opt/venv/bin/pip install --require-hashes -r requirements-dev.lock
/opt/venv/bin/pip install --no-deps -e .
export PATH="/opt/venv/bin:$PATH"
packaging/build.sh

version="$(python -c 'from budget_core import __version__; print(__version__)')"
name="system-budget-studio-${version}-linux-x86_64"
cp packaging/linux/install.sh packaging/linux/uninstall.sh dist/system-budget-studio/
python packaging/check_bundle.py dist/system-budget-studio
tar -C dist -czf "dist/${name}.tar.gz" system-budget-studio
(cd dist && sha256sum "${name}.tar.gz" > SHA256SUMS.txt)

# Install test as an ordinary user: no root, no network, a fresh HOME.
useradd --create-home tester
cp "dist/${name}.tar.gz" /home/tester/
su tester -c "
set -euo pipefail
cd ~
tar xzf ${name}.tar.gz
cd system-budget-studio
./install.sh
export PATH=\$HOME/.local/bin:\$PATH
budget --version
budget self-test
QT_QPA_PLATFORM=offscreen system-budget-studio --smoke
test -f ~/.local/share/applications/system-budget-studio.desktop
~/.local/opt/system-budget-studio/uninstall.sh
test ! -e ~/.local/opt/system-budget-studio
test ! -e ~/.local/bin/budget
"
echo "RHEL 8 build, install and uninstall: OK"

chown -R "${HOST_UID:-0}:${HOST_GID:-0}" dist build 2>/dev/null || true
