#!/usr/bin/env bash
# PhotoCraft AI PR #93 — optional per-user Linux Lab desktop launcher.
# No root, autostart, service install, downloads, or changes to ComfyUI.
set -euo pipefail

user_home="$HOME"
runner="$user_home/.local/bin/start-photocraft-u2netp.sh"
application_dir="$user_home/.local/share/applications"
application_file="$application_dir/photocraft-u2netp-server.desktop"
desktop_dir="$user_home/Desktop"
if command -v xdg-user-dir >/dev/null 2>&1; then
    configured_desktop="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    if [[ -n "$configured_desktop" && "$configured_desktop" == "$user_home"/* ]]; then
        desktop_dir="$configured_desktop"
    fi
fi

mkdir -p "$(dirname "$runner")" "$application_dir" "$desktop_dir"

cat > "$runner" <<'RUNNER'
#!/usr/bin/env bash
# Starts the dedicated CPU U2NetP server only when launched by the user.
# The bearer token is generated in memory by the server on each start.
set -u
venv_python="$HOME/photocraft-ai-cpu-venv/bin/python"
scripts="$HOME/photocraft-ai-tests"
server="$scripts/loopback_u2netp_server.py"
model="$HOME/.local/share/photocraft-ai-cpu/u2netp.onnx"

printf '\nPhotoCraft AI — U2NetP Local CPU Server\n'
printf '%s\n' '------------------------------------'
printf 'This server listens only on 127.0.0.1:18793.\n'
printf 'Do not share its session token or expose this port to the network.\n\n'
if [[ ! -x "$venv_python" ]]; then
    printf 'ERROR: Dedicated Python environment was not found:\n  %s\n' "$venv_python"
    printf 'Set up the PhotoCraft AI CPU environment before starting this shortcut.\n'
    status=2
elif [[ ! -f "$server" || ! -f "$scripts/local_background_bridge.py" || ! -f "$scripts/validate_output_png.py" || ! -f "$scripts/benchmark_u2netp.py" ]]; then
    printf 'ERROR: One or more U2NetP server helper scripts are missing in:\n  %s\n' "$scripts"
    printf 'Download the four reviewed PR #93 helpers to that folder before retrying.\n'
    status=2
elif [[ ! -f "$model" ]]; then
    printf 'ERROR: U2NetP model is not installed at:\n  %s\n' "$model"
    printf 'No model is downloaded automatically.\n'
    status=2
else
    cd "$scripts" || exit 2
    printf 'Starting local server. Leave this terminal open while using PhotoCraft.\n'
    printf 'Copy the temporary token into PhotoCraft AI Preview without sharing it.\n\n'
    "$venv_python" "$server" --port 18793
    status=$?
fi
printf '\nU2NetP server stopped or could not start (exit status %s).\n' "$status"
printf 'Press Enter to close this terminal window... '
IFS= read -r _ || true
exit "$status"
RUNNER

cat > "$application_file" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Start PhotoCraft U2NetP
GenericName=Local AI Background Removal Server
Comment=Start the private local CPU server for PhotoCraft AI Preview
Exec=$runner
Icon=applications-graphics
Terminal=true
StartupNotify=false
Categories=Graphics;Utility;
EOF

chmod 755 "$runner" "$application_file"
desktop_file="$desktop_dir/Start PhotoCraft U2NetP.desktop"
cp "$application_file" "$desktop_file"
chmod 755 "$desktop_file"
# Some desktop file managers require a trusted-launcher attribute. Failure is
# harmless on LXQt/XFCE installations without the corresponding GVFS backend.
if command -v gio >/dev/null 2>&1; then
    gio set "$desktop_file" metadata::trusted true >/dev/null 2>&1 || true
fi
if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$application_file" || true
fi
printf 'Installed desktop shortcut: %s\n' "$desktop_file"
printf 'Installed application menu entry: %s\n' "$application_file"
printf 'One click starts the local server; Ctrl+C in its terminal stops it.\n'