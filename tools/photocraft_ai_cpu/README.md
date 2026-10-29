# PhotoCraft AI — isolated U2NetP CPU experiment (HONOR Linux Lab)

**Status: standalone benchmark ONLY.** This is not a PhotoCraft plugin, Android APK or public release. The Remove Background menu remains disabled.

The experiment uses rembg 2.0.78 and explicit U2NetP via ONNX Runtime 1.28.0 CPUExecutionProvider on Ubuntu 24.04 ARM64 / Python 3.12. It does not need ComfyUI/PyTorch/GPU changes. The earlier ComfyUI inventory result of zero diffusion checkpoints and zero upscale models is expected and unrelated to these separate background-removal weights.

## Safety boundaries

- Do not alter the user's working ComfyUI at ~/ComfyUI or ~/comfyui-venv, Ubuntu desktop, PhotoCraft package/production key, icons, fonts, shortcuts or Window menu.
- No sudo, package manager changes, background service, model server, upload or unattended download.
- All Python packages are installed to a separate ~/photocraft-ai-cpu-venv.
- --check and --self-test do NOT download a model or run inference.
- The first --run needs a verified local U2NetP file, or explicit --allow-model-download to retrieve it from the rembg GitHub release. Review model licenses first.
- By default benchmark on a synthetic 512x512 image, not user documents.
- Max 4 megapixels and 24 MiB input; CPU threads capped at 2; output always a NEW PNG created exclusively without overwriting input.
- This is not an image-processing backend for PhotoCraft yet. No editable layers, Undo, cancellation or performance guarantee.

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

The model is placed at ~/.local/share/photocraft-ai-cpu/models/u2netp/u2netp.onnx, completely separate from ComfyUI. The script sets U2NET_HOME only in its own process.
U2NetP's upstream MD5 reference is checked before and after model load.
The script emits model-load time, inference time, max process RSS, output alpha
range, and a new PNG under ~/Pictures/PhotoCraft-AI-Tests/.

Later local tests can use --run without the download flag. For an explicitly
chosen <=4 MP non-sensitive image stored in Linux Lab:

    python "$HOME/photocraft-ai-tests/benchmark_u2netp.py" \
      --run --input "$HOME/Pictures/test-image.png"

This never overwrites the input. CPU inference can be slow; close other
memory-heavy apps first and keep Linux Lab visible.

## What results unlock further integration?

Show the --check providers and the benchmark JSON. Test whether output alpha
and memory use are reasonable for this tablet before connecting it to any
PhotoCraft document. The NEXT stage requires approved per-image exchange,
bounded input/output, cancellation, masks, undoable NEW layers, and device
testing. No automatic uploads or generative/inpainting workflow is enabled.

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
