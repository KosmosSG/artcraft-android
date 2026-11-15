"""Android.11 VectorCraft PhotoCraft-style bottom native update notifications.

Run on the staged disposable Android adapter AFTER Android.5 verified downloader
and Android.11 hover-button/history patch. The reference PhotoCraft stable
v0.23.1-android.5 calls Android Toast.makeText(..., LENGTH_LONG).show().
Do not add an egui bar: Android controls the OS-styled bottom pill/app icon.
Keep existing verified in-app APK download, PackageInstaller consent, updater
signing gates, private app state, and the working Android.10 IME untouched.
"""
from pathlib import Path
import sys

def replace_one(s: str, before: str, after: str, label: str) -> str:
    count = s.count(before)
    if count != 1:
        raise ValueError(f"Android.11 PhotoCraft updater toast {label}: expected 1, found {count}")
    return s.replace(before, after, 1)

def patch(root: Path) -> None:
    a = root / "adapters/vectorcraft"
    java = a / "java/com/artcraft/vectorcraft/VectorCraftActivity.java"
    host = a / "src/lib.rs"
    src_j = java.read_text()
    src_h = host.read_text()
    if "VC_ANDROID11_PHOTOCRAFT_UPDATE_TOAST" in src_j:
        raise ValueError("Android.11 updater toast already patched")

    # System-owned Android 12+ toast includes the app icon and dark/rounded
    # pill seen in the approved PhotoCraft screenshot. It is deliberately not
    # drawn on the wgpu/egui canvas and cannot grab focus or IME ownership.
    src_j = replace_one(src_j,
        '    public void vcOpenUpdatePage(String url) { extras.openRelease(url); }',
        '''    // VC_ANDROID11_PHOTOCRAFT_UPDATE_TOAST: system app-icon notification.
    public void vcShowUpdateToast(String message) {
        if (message == null) return;
        final String safe = message.trim();
        if (safe.isEmpty()) return;
        final String label = safe.length() <= 150 ? safe : safe.substring(0, 149) + "…";
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) return;
            android.widget.Toast.makeText(this, label, android.widget.Toast.LENGTH_LONG).show();
        });
    }
    public void vcOpenUpdatePage(String url) { extras.openRelease(url); }''',
        "PhotoCraft-style native Android Toast method")

    # Use a separate single-purpose JNI method; do not mutate the update
    # download destination, HTTPS/Digest validation, installer, or keyboard.
    src_h = replace_one(src_h,
        '    fn check_for_updates(&self) -> Result<(), String> {',
        '''    fn vc_show_update_toast(&self, message: &str) -> Result<(), String> {
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let message = JObject::from(env.new_string(message)?);
            env.call_method(&*activity, jni_str!("vcShowUpdateToast"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&message)])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }
    fn check_for_updates(&self) -> Result<(), String> {''',
        "Rust JNI Toast helper")

    # Startup checks are deliberately quiet, as in PhotoCraft. Only a
    # manual press causes immediate Checking... and terminal outcome toasts.
    src_h = replace_one(src_h,
        '''    updates: UpdateDialogState,
    ime: ime_bridge::ime::ImeBridge,''',
        '''    updates: UpdateDialogState,
    manual_update_toast_pending: bool,
    ime: ime_bridge::ime::ImeBridge,''',
        "manual-check status state")
    src_h = replace_one(src_h,
        '''                updates: {
                    let mut state = UpdateDialogState::default();''',
        '''                manual_update_toast_pending: false,
                updates: {
                    let mut state = UpdateDialogState::default();''',
        "initialize manual-only notifications")

    # The post-Android.5 updater result is an owned serde_json::Value. Do
    # not queue toast for every download-progress tick. Give one result toast
    # only when the manual check completes or a download reaches a milestone.
    src_h = replace_one(src_h,
        '''                            let state = result.get("state").and_then(serde_json::Value::as_str)
                                .unwrap_or("error");
                            if state == "update_available"''',
        '''                            let state = result.get("state").and_then(serde_json::Value::as_str)
                                .unwrap_or("error");
                            let was_downloading = self.updates.downloading;
                            if state == "update_available"''',
        "capture downloader phase before update result")
    src_h = replace_one(src_h,
        '''                                _ => {}
                            }
                        }
                        Err(error) => {''',
        '''                                _ => {}
                            }
                            let check_completed = matches!(state,
                                "update_available" | "up_to_date" | "no_release" | "error");
                            if self.manual_update_toast_pending && check_completed {
                                self.manual_update_toast_pending = false;
                                let notice = match state {
                                    "update_available" => format!(
                                        "Update available: {}", self.updates.available_version
                                            .as_deref().unwrap_or("new version")),
                                    "up_to_date" => "VectorCraft is up to date.".to_owned(),
                                    "no_release" => "No published VectorCraft update found.".to_owned(),
                                    _ => "Couldn't check VectorCraft updates.".to_owned(),
                                };
                                if let Err(error) = self.bridge.vc_show_update_toast(&notice) {
                                    log::warn!("VectorCraft update notification: {error}");
                                }
                            } else if was_downloading && matches!(state,
                                "verified" | "install_pending" | "permission_required"
                                    | "installed" | "unavailable" | "error") {
                                // Respect the exact downloader's result; never
                                // claim an install succeeded before Android says so.
                                let notice = match state {
                                    "verified" => "Update downloaded and verified.".to_owned(),
                                    "install_pending" => "Confirm update installation in Android.".to_owned(),
                                    _ => self.updates.message.clone(),
                                };
                                if let Err(error) = self.bridge.vc_show_update_toast(&notice) {
                                    log::warn!("VectorCraft update notification: {error}");
                                }
                            }
                        }
                        Err(error) => {''',
        "update check completion and install milestones")

    src_h = replace_one(src_h,
        '''                            self.updates.message = format!("Invalid update reply: {error}");
                        }
                    }
                    ctx.request_repaint();''',
        '''                            self.updates.message = format!("Invalid update reply: {error}");
                            if self.manual_update_toast_pending {
                                self.manual_update_toast_pending = false;
                                let _ = self.bridge.vc_show_update_toast("Couldn't check VectorCraft updates.");
                            }
                        }
                    }
                    ctx.request_repaint();''',
        "invalid response notification")
    src_h = replace_one(src_h,
        '''                    self.updates.message = format!("Update service unavailable: {error}");
                }
            }
        }''',
        '''                    self.updates.message = format!("Update service unavailable: {error}");
                    if self.manual_update_toast_pending {
                        self.manual_update_toast_pending = false;
                        let _ = self.bridge.vc_show_update_toast("VectorCraft update service unavailable.");
                    }
                }
            }
        }''',
        "JNI reply failure notification")

    # One manual-check entry point covers both tapped top-left Vc menu and
    # About VectorCraft > Updates. Show system toast immediately on success.
    src_h = replace_one(src_h,
        '''                match self.bridge.check_for_updates() {
                    Ok(()) => self.updates.checking = true,
                    Err(error) => self.updates.message =
                        format!("Could not check releases: {error}"),
                }''',
        '''                match self.bridge.check_for_updates() {
                    Ok(()) => {
                        self.updates.checking = true;
                        self.manual_update_toast_pending = true;
                        if let Err(error) = self.bridge.vc_show_update_toast("Checking for updates…") {
                            log::warn!("VectorCraft check notification: {error}");
                        }
                    }
                    Err(error) => {
                        self.updates.message = format!("Could not check releases: {error}");
                        let _ = self.bridge.vc_show_update_toast("Couldn't start VectorCraft update check.");
                    }
                }''',
        "manual update check shows native OS toast")

    # The verified in-app download is unchanged. Add matching native notice
    # on an explicit user-initiated download only; no automatic installation.
    src_h = replace_one(src_h,
        '''                        self.updates.message = "Preparing verified APK download…".into();
                        ctx.request_repaint();''',
        '''                        self.updates.message = "Preparing verified APK download…".into();
                        if let Err(error) = self.bridge.vc_show_update_toast("Downloading VectorCraft update…") {
                            log::warn!("VectorCraft download notification: {error}");
                        }
                        ctx.request_repaint();''',
        "download begins with a PhotoCraft-style toast")
    src_h = replace_one(src_h,
        '''                    Err(error) => self.updates.message =
                        format!("Could not start in-app download: {error}"),''',
        '''                    Err(error) => {
                        self.updates.message = format!("Could not start in-app download: {error}");
                        let _ = self.bridge.vc_show_update_toast("Couldn't start VectorCraft update download.");
                    },''',
        "download start failure notifies")

    for token in ('vcShowUpdateToast(String message)', 'android.widget.Toast.makeText(this, label, android.widget.Toast.LENGTH_LONG).show()'):
        assert token in src_j
    for token in ('vc_show_update_toast(', 'manual_update_toast_pending: bool',
                  '"Checking for updates…"', '"Downloading VectorCraft update…"',
                  '"Update downloaded and verified."', '"VectorCraft is up to date."',
                  '"edit.undo"', '"edit.redo"'):
        # History commands remain in the host on Android.11.
        assert token in src_h, token
    assert 'vcResetIme(long requestId)' in src_j
    assert 'self.ime.poll(ctx, raw);' in src_h
    assert 'fn download_verified_update(&self, version: &str)' in src_h
    assert 'self.bridge.download_verified_update(version)' in src_h
    assert 'vcAndroid11HistoryMode' in src_j
    assert 'vcAndroid11HistoryMode' in src_h
    java.write_text(src_j)
    host.write_text(src_h)
    print("PASS: PhotoCraft v0.23.1-android.5 native bottom update toasts, manual checks and verified download; preserved .ai typing")

if __name__ == "__main__":
    patch(Path(sys.argv[1]))
