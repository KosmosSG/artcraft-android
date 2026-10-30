# PhotoCraft AI — isolated U2NetP CPU experiment (HONOR Linux Lab)

**Status (30 October 2026):** U2NetP CPU processing is available as an experimental, **opt-in, localhost-only** service for the separate PhotoCraft AI Preview APK. ARM64 preview build #49 passed CI, and the owner reported successful background removal, a separate result layer, and Undo/Redo on HONOR MagicPad 4. This is **not** a production release or a standalone Android inference engine.

The experiment uses rembg 2.0.78 and explicit U2NetP via ONNX Runtime 1.28.0 CPUExecutionProvider on Ubuntu 24.04 ARM64 / Python 3.12. It does not need ComfyUI/PyTorch/GPU changes. The earlier ComfyUI inventory result of zero diffusion checkpoints and zero upscale models is expected and unrelated to these separate background-removal weights.

## Safety boundaries

- Do not alter the user's working ComfyUI at ~/ComfyUI or ~/comfyui-venv, Ubuntu desktop, PhotoCraft package/production key, icons, fonts, shortcuts or Window menu.
- No sudo, package manager changes, autostart or unattended download. The temporary token-authenticated model server binds **only to 127.0.0.1:18793** after the user manually starts it. The separate PhotoCraft AI Preview uploads each explicitly consented image **only to that tablet-local endpoint**; ComfyUI receives no image data.
- All Python packages are installed to a separate ~/photocraft-ai-cpu-venv.
- --check and --self-test do NOT download a model or run inference.
- The first --run needs a verified local U2NetP file, or explicit --allow-model-download to retrieve it from the rembg GitHub release. Review model licenses first.
- By default benchmark on a synthetic 512x512 image, not user documents.
- Max 4 megapixels and 24 MiB input; CPU threads capped at 2; output always a NEW PNG created exclusively without overwriting input.
- The separate Android AI Preview supports an undoable new raster layer after full PNG validation and stale-document checks. Cancelling a request discards its result on the app side, but the already running CPU inference may continue on Linux Lab. No production reliability or performance guarantee.

## 1 — Create a separate virtual environment (inside Linux Lab QTerminal)

    python3 -m venv "$HOME/photocraft-ai-cpu-venv"
    source "$HOME/photocraft-ai-cpu-venv/bin/activate"
    python --version

The prompt should display (photocraft-ai-cpu-venv). Do NOT activate or replace the existing comfyui-venv.

## 2 — Inspect compatible binary wheels first, then install

    python -m pip install --dry-run --only-binary=:all: \
      "rembg[cpu]==2.0.78" "onnxruntime==1.28.0"

Only if the dry run succeeds:

    python -m pip install --only-binary=:all: \
      "rembg[cpu]==2.0.78" "onnxruntime==1.28.0"
    python -m pip check

If a suitable ARM64 wheel is unavailable, STOP. Do not compile from source or change the existing PyTorch installation.

## 3 — Obtain the script from the PR #93 development branch

Review it in GitHub first:
https://github.com/KosmosSG/artcraft-android/blob/feature/photocraft-android-ai-tools-20261029/tools/photocraft_ai_cpu/benchmark_u2netp.py

Then inside Linux Lab:

    mkdir -p "$HOME/photocraft-ai-tests"
    curl --fail --location --show-error --silent \
      "https://raw.githubusercontent.com/KosmosSG/artcraft-android/feature/photocraft-android-ai-tools-20261029/tools/photocraft_ai_cpu/benchmark_u2netp.py" \
      -o "$HOME/photocraft-ai-tests/benchmark_u2netp.py"

Review the local file before execution. Then run:

    python "$HOME/photocraft-ai-tests/benchmark_u2netp.py" --self-test
    python "$HOME/photocraft-ai-tests/benchmark_u2netp.py" --check

## 4 — Explicit model download and synthetic CPU benchmark

After confirming dependencies and reviewing U2NetP weight rights, authorize the first download:

    python "$HOME/photocraft-ai-tests/benchmark_u2netp.py" \
      --run --allow-model-download

With the pinned rembg 2.0.78, the model is saved at ~/.local/share/photocraft-ai-cpu/u2netp.onnx (flat U2NET_HOME directory), completely separate from ComfyUI. The script sets U2NET_HOME only in its own process. An earlier script mistakenly checked models/u2netp/u2netp.onnx; the path was corrected after the owner's 4.57 MB download succeeded. The revised script verifies the already downloaded model rather than downloading it again.
U2NetP's upstream MD5 reference is checked before and after model load.
The script emits model-load time, inference time, max process RSS, output alpha
range, and a new PNG under ~/Pictures/PhotoCraft-AI-Tests/.

After the model has been downloaded, use the corrected script with --run **without** --allow-model-download. It verifies the cached model file's MD5 integrity before using it, and refuses missing or unverified weights.

Later local tests can use --run without the download flag. For an explicitly
chosen <=4 MP non-sensitive image stored in Linux Lab:

    python "$HOME/photocraft-ai-tests/benchmark_u2netp.py" \
      --run --input "$HOME/Pictures/test-image.png"

This never overwrites the input. CPU inference can be slow; close other
memory-heavy apps first and keep Linux Lab visible.


## One-click Linux Lab desktop shortcut

Run the checked-in **launcher installer** once from QTerminal inside Linux Lab.
It creates an executable \`Start PhotoCraft U2NetP.desktop\` shortcut in
\`~/Desktop\` and an application-menu entry. It uses the existing dedicated
\`~/photocraft-ai-cpu-venv/bin/python\`, verifies helper scripts and model path,
and never downloads models, installs packages, or changes ComfyUI.

\`\`\`bash
curl -fLsS \
  "https://raw.githubusercontent.com/KosmosSG/artcraft-android/feature/photocraft-android-ai-tools-20261029/tools/photocraft_ai_cpu/install_linux_lab_launcher.sh" \
  -o /tmp/install-photocraft-u2netp.sh
bash /tmp/install-photocraft-u2netp.sh
\`\`\`

Review the downloaded script before execution. Double-click **Start PhotoCraft
U2NetP** to open a terminal and launch the loopback-only server. It prints a
**temporary bearer token** that is required in PhotoCraft AI Preview's
\`AI Tools → Remove Background · Local CPU Preview…\` dialog. Do not include the
token in screenshots or save it in the launcher. The server runs only while
the terminal is open; press Ctrl+C to stop it.

The separate preview's \`Remove Background\` action requires explicit
per-image consent. For first tests, use a non-sensitive RGB 8-bit image
under 4 million pixels. If Linux Lab is suspended while PhotoCraft is
foregrounded, keep it visible in a floating window.

**Release boundary:** this is still a disposable-signature preview,
not an approved public release. Before merging or distributing production
APKs, review model weight/data licensing, worker cancellation and
Android lifecycle behavior, UI/desktop shortcut regressions, and the
long-term production signing/update plan.

## What results unlock further integration?

Show the --check providers and the benchmark JSON. Test whether output alpha
and memory use are reasonable for this tablet before connecting it to any
PhotoCraft document. The first opt-in loopback PNG exchange and an undoable **new raster layer** have now been implemented and owner-tested in the separate Android preview. Remaining work includes robust Android lifecycle/cancellation testing, selection-only processing and masks, deeper regression testing and model-rights review. No automatic uploads, generative fill or inpainting workflow is enabled.

Licensing: rembg source is MIT; U²-Net project uses Apache-2.0. The rights for
model weights and training data are distinct and require review before
commercial use, redistribution or inclusion in an APK. Other rembg models
(such as BRIA RMBG-2.0) have different commercial terms and are NOT selected.

References:
https://github.com/danielgatis/rembg
https://github.com/danielgatis/rembg/blob/main/rembg/sessions/u2netp.py
https://github.com/xuebinqin/U-2-Net
https://pypi.org/project/rembg/2.0.78/
https://pypi.org/project/onnxruntime/1.28.0/
