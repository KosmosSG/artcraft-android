"""VectorCraft Android.5: opt-in verified in-app download and Android installer handoff.

Apply ONLY to the disposable Android.4-generated staging tree, after the
reviewed upstream, Android.2, and About/Updates overlays. Neither the official
source checkout nor any production APK/signing material is modified.
Every transformation is source-guarded before ARM64 compilation.
"""
from pathlib import Path
import shutil
import sys

def once(src, old, new, label):
    count = src.count(old)
    if count != 1:
        raise ValueError(f"Android.5 {label}: expected one anchor, found {count}")
    return src.replace(old, new, 1)

def patch(root: Path, owner: Path) -> None:
    base = root / "adapters/vectorcraft"
    java = base / "java/com/artcraft/vectorcraft"
    host_path = base / "src/lib.rs"
    extras_path = java / "VectorCraftExtras.java"
    activity_path = java / "VectorCraftActivity.java"
    manifest_path = base / "Cargo.toml"
    about_path = root / "source/vectorcraft/crates/ui-egui/src/dialogs/about.rs"

    extras = extras_path.read_text()
    activity = activity_path.read_text()
    host = host_path.read_text()
    manifest = manifest_path.read_text()
    about = about_path.read_text()

    extras = once(extras,
        '    private final ConcurrentLinkedQueue<String> updates = new ConcurrentLinkedQueue<>();',
        '''    private final ConcurrentLinkedQueue<String> updates = new ConcurrentLinkedQueue<>();
    private final VectorCraftUpdateInstaller verifiedUpdater =
        new VectorCraftUpdateInstaller(activity, updates);''',
        "isolated verified downloader state")
    extras = once(extras,
        '    String pollUpdate() { return updates.poll(); }',
        '''    String pollUpdate() { return updates.poll(); }
    void downloadUpdate(String version) { verifiedUpdater.start(version, updateIo); }
    void updateInstallStatus(Intent intent) { verifiedUpdater.onInstallStatus(intent); }''',
        "download + installer hooks")
    extras = once(extras,
        '                String latest = null, releaseUrl = null;',
        '''                String latest = null, releaseUrl = null;
                String latestAssetUrl = null, latestDigest = null;
                long latestAssetBytes = 0L;''',
        "selected asset and digest")
    extras = once(extras,
        '''                    boolean apkFound = false;
                    if (assets != null) for (int j = 0; j < assets.length(); j++) {
                        JSONObject asset = assets.optJSONObject(j);
                        if (asset == null) continue;
                        // Check exact same-app ARM64 asset, not an unrelated
                        // test APK or an incomplete upload.
                        String filename = asset.optString("name", "");
                        if (("VectorCraft-v" + version + "-arm64-v8a.apk").equals(filename)
                                && "uploaded".equals(asset.optString("state", ""))
                                && asset.optLong("size", 0L) > 0) apkFound = true;
                    }''',
        '''                    boolean apkFound = false;
                    String assetUrl = null, assetDigest = null;
                    long assetBytes = 0L;
                    if (assets != null) for (int j = 0; j < assets.length(); j++) {
                        JSONObject asset = assets.optJSONObject(j);
                        if (asset == null) continue;
                        // Name and exact repo release URL are both pinned. A
                        // GitHub-provided SHA-256 digest is mandatory to install.
                        String filename = asset.optString("name", "");
                        String expected = "VectorCraft-v" + version + "-arm64-v8a.apk";
                        if (expected.equals(filename)
                                && "uploaded".equals(asset.optString("state", ""))
                                && asset.optLong("size", 0L) > 0) {
                            apkFound = true;
                            assetUrl = asset.optString("browser_download_url", "");
                            assetDigest = asset.optString("digest", "");
                            assetBytes = asset.optLong("size", 0L);
                        }
                    }''',
        "exact release APK metadata")
    extras = once(extras,
        '''                        latest = version;
                        releaseUrl = url;''',
        '''                        latest = version;
                        releaseUrl = url;
                        latestAssetUrl = assetUrl;
                        latestDigest = assetDigest;
                        latestAssetBytes = assetBytes;''',
        "selected newest APK metadata")
    extras = once(extras,
        '''                JSONObject result = new JSONObject();
                result.put("status", "ok");
                result.put("installed_version", installed);''',
        '''                verifiedUpdater.remember(latest, latestAssetUrl, latestDigest, latestAssetBytes);
                JSONObject result = new JSONObject();
                result.put("status", "ok");
                result.put("installed_version", installed);''',
        "candidate lock before showing update")
    extras = once(extras,
        '''                    result.put("latest_version", latest);
                    result.put("url", releaseUrl);
                    result.put("state", compareVersions(latest, installed) > 0
                            ? "update_available" : "up_to_date");''',
        '''                    result.put("latest_version", latest);
                    result.put("url", releaseUrl);
                    boolean newer = compareVersions(latest, installed) > 0;
                    result.put("state", newer ? "update_available" : "up_to_date");
                    result.put("downloadable", newer && verifiedUpdater.canDownload(latest));''',
        "download-ready state in release reply")

    activity = once(activity,
        '    public void vcOpenUpdatePage(String url) { extras.openRelease(url); }',
        '''    public void vcOpenUpdatePage(String url) { extras.openRelease(url); }
    // Explicit user click only; this does not run during startup checks.
    public void vcDownloadUpdate(String version) { extras.downloadUpdate(version); }''',
        "JNI download entrypoint")
    activity = once(activity,
        '''        imeSetup();
        handleIncomingFiles(getIntent());
    }''',
        '''        imeSetup();
        extras.updateInstallStatus(getIntent());
        handleIncomingFiles(getIntent());
    }''',
        "cold-launch installer status")
    activity = once(activity,
        '''        setIntent(intent);
        applyImmersiveFullscreen();
        handleIncomingFiles(intent);
    }''',
        '''        setIntent(intent);
        extras.updateInstallStatus(intent);
        applyImmersiveFullscreen();
        handleIncomingFiles(intent);
    }''',
        "existing-task installer status")

    permission = '''[[package.metadata.android.uses_permission]]
name = "android.permission.INTERNET"'''
    manifest = once(manifest, permission,
        permission + '''

# The user explicitly authorizes an update, then Android's package installer
# shows the final approval. Only the original signed app can update itself.
[[package.metadata.android.uses_permission]]
name = "android.permission.REQUEST_INSTALL_PACKAGES"''',
        "Android system installer permission")

    host = once(host,
        '    fn files_dir(&self) -> Result<String, String> {',
        '''    fn download_verified_update(&self, version: &str) -> Result<(), String> {
        // Never accept arbitrary paths or URLs from an egui control.
        if !version.bytes().all(|b| b.is_ascii_digit() || b == b'.' || b == b'-' || b == b'a'
            || b == b'n' || b == b'd' || b == b'r' || b == b'o' || b == b'i') {
            return Err("Invalid release version".into());
        }
        self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
            let raw = self.app.activity_as_ptr() as jni::sys::jobject;
            let activity = unsafe { env.as_cast_raw::<JObject>(&raw)? };
            let version = JObject::from(env.new_string(version)?);
            env.call_method(&*activity, jni_str!("vcDownloadUpdate"),
                jni_sig!("(Ljava/lang/String;)V"), &[JValue::Object(&version)])?;
            Ok(())
        }).map_err(|error| error.to_string())
    }

    fn files_dir(&self) -> Result<String, String> {''',
        "Rust JNI updater action")
    host = once(host,
        '''struct UpdateDialogState {
    checking: bool,
    message: String,
    release_url: Option<String>,
    include_preview: bool,
}''',
        '''struct UpdateDialogState {
    checking: bool,
    downloading: bool,
    downloadable: bool,
    available_version: Option<String>,
    message: String,
    release_url: Option<String>,
    include_preview: bool,
}''',
        "update UI state")

    start = host.index('        if self.updates.checking {\n            match self.bridge.poll_update_result() {')
    end = host.index('        // Then deliver any file the system asked us to open, through the same inbox.', start)
    old = host[start:end]
    if old.count('self.updates.checking = false;') != 2 or 'self.bridge.poll_update_result()' not in old:
        raise ValueError("Android.5 upstream update event loop changed; manual review required")
    new = '''        if self.updates.checking || self.updates.downloading {
            match self.bridge.poll_update_result() {
                Ok(Some(raw)) => {
                    match serde_json::from_str::<serde_json::Value>(&raw) {
                        Ok(result) => {
                            let state = result.get("state").and_then(serde_json::Value::as_str)
                                .unwrap_or("error");
                            if state == "update_available" || state == "up_to_date"
                                || state == "no_release" || state == "error" {
                                self.updates.checking = false;
                            }
                            match state {
                                "update_available" | "up_to_date" | "no_release" => {
                                    self.updates.available_version = result.get("latest_version")
                                        .and_then(serde_json::Value::as_str).map(str::to_owned);
                                    self.updates.downloadable = result.get("downloadable")
                                        .and_then(serde_json::Value::as_bool).unwrap_or(false);
                                    self.updates.release_url = result.get("url")
                                        .and_then(serde_json::Value::as_str)
                                        .filter(|u| u.starts_with(
                                            "https://github.com/KosmosSG/artcraft-android/releases/tag/vectorcraft-v"))
                                        .map(str::to_owned);
                                    let installed = result.get("installed_version")
                                        .and_then(serde_json::Value::as_str).unwrap_or("unknown");
                                    let latest = result.get("latest_version")
                                        .and_then(serde_json::Value::as_str).unwrap_or("unknown");
                                    self.updates.message = match state {
                                        "update_available" => format!("Update available: {latest} (installed: {installed})"),
                                        "up_to_date" => format!("You're up to date (installed: {installed}; latest: {latest})."),
                                        _ => "No published VectorCraft Android APK yet.".into(),
                                    };
                                }
                                "downloading" | "verified" | "install_pending" => {
                                    self.updates.downloading = true;
                                    self.updates.message = result.get("message")
                                        .and_then(serde_json::Value::as_str).unwrap_or("Preparing update…").to_owned();
                                }
                                "permission_required" | "installed" | "unavailable" | "error" => {
                                    self.updates.downloading = false;
                                    self.updates.message = result.get("message")
                                        .and_then(serde_json::Value::as_str).unwrap_or("Update unavailable.").to_owned();
                                }
                                _ => {}
                            }
                        }
                        Err(error) => {
                            self.updates.downloading = false;
                            self.updates.checking = false;
                            self.updates.message = format!("Invalid update reply: {error}");
                        }
                    }
                    ctx.request_repaint();
                }
                Ok(None) => ctx.request_repaint_after(std::time::Duration::from_millis(250)),
                Err(error) => {
                    self.updates.downloading = false;
                    self.updates.checking = false;
                    self.updates.message = format!("Update service unavailable: {error}");
                }
            }
        }
'''
    host = host[:start] + new + host[end:]

    host = once(host,
        '''            d.insert_temp(egui::Id::new("artcraft.vectorcraft.update_checking"), self.updates.checking);''',
        '''            d.insert_temp(egui::Id::new("artcraft.vectorcraft.update_checking"), self.updates.checking);
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.update_downloading"), self.updates.downloading);
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.update_downloadable"), self.updates.downloadable);
            d.insert_temp(egui::Id::new("artcraft.vectorcraft.available_version"),
                self.updates.available_version.clone().unwrap_or_default());''',
        "publish download availability to About tab")
    host = once(host,
        '''        let mut check_updates = false;''',
        '''        let mut check_updates = false;
        let mut download_update_requested = false;''',
        "download requested flag")
    host = once(host,
        '''              tab_preview_changed, tab_preview_desired, tab_open_release) =''',
        '''              tab_preview_changed, tab_preview_desired, tab_open_release, tab_download) =''',
        "About action tuple")
    host = once(host,
        '''                let open = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.open_release_requested")).unwrap_or(false);''',
        '''                let open = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.open_release_requested")).unwrap_or(false);
                let download = d.get_temp::<bool>(egui::Id::new("artcraft.vectorcraft.download_update_requested")).unwrap_or(false);''',
        "pop download action")
    host = once(host,
        '''                             "artcraft.vectorcraft.open_release_requested"] {''',
        '''                             "artcraft.vectorcraft.open_release_requested",
                             "artcraft.vectorcraft.download_update_requested"] {''',
        "clear one-shot download command")
    host = once(host,
        '''                 (check, startup_changed, startup, preview_changed, preview, open)''',
        '''                 (check, startup_changed, startup, preview_changed, preview, open, download)''',
        "return one-shot action")
    host = once(host,
        '''        if tab_check { check_updates = true; }''',
        '''        if tab_check { check_updates = true; }
        if tab_download { download_update_requested = true; }''',
        "accept explicitly clicked download action")
    host = once(host,
        '''                    self.updates.release_url = None;''',
        '''                    self.updates.release_url = None;
                    self.updates.downloadable = false;
                    self.updates.available_version = None;''',
        "clear candidate when channel changes")
    host = once(host,
        '''        if tab_open_release {''',
        '''        if download_update_requested && !self.updates.checking && !self.updates.downloading
            && self.updates.downloadable {
            if let Some(version) = self.updates.available_version.as_deref() {
                match self.bridge.download_verified_update(version) {
                    Ok(()) => {
                        self.updates.downloading = true;
                        self.updates.message = "Preparing verified APK download…".into();
                        ctx.request_repaint();
                    }
                    Err(error) => self.updates.message =
                        format!("Could not start in-app download: {error}"),
                }
            }
        }
        if tab_open_release {''',
        "guarded user-triggered download")

    # The real Android About tab is generated before this patch runs.
    about = once(about,
        '''                    if checking { ui.spinner(); }''',
        '''                    if checking { ui.spinner(); }
                    let downloading = context.data(|d| d.get_temp::<bool>(
                        egui::Id::new("artcraft.vectorcraft.update_downloading"))).unwrap_or(false);
                    if downloading { ui.spinner(); }''',
        "in-app progress feedback")
    about = once(about,
        '''                    ui.separator();
                    ui.label("Update Channel");''',
        '''                    let downloadable = context.data(|d| d.get_temp::<bool>(
                        egui::Id::new("artcraft.vectorcraft.update_downloadable"))).unwrap_or(false);
                    let version = context.data(|d| d.get_temp::<String>(
                        egui::Id::new("artcraft.vectorcraft.available_version"))).unwrap_or_default();
                    if downloadable && !checking && !downloading && !version.is_empty()
                        && ui.button(format!("Download & Install VectorCraft {version}")).clicked() {
                        context.data_mut(|d| d.insert_temp(
                            egui::Id::new("artcraft.vectorcraft.download_update_requested"), true));
                        context.request_repaint();
                    }
                    if downloading {
                        ui.small("Download runs within VectorCraft; Android confirms the final installation.");
                    } else if !downloadable {
                        ui.small("In-app installation requires an official release with SHA-256 and the original app signing key. Test builds cannot replace the production app.");
                    }
                    ui.separator();
                    ui.label("Update Channel");''',
        "install button and controlled help text")

    # Install-copy is known Java source, not downloaded from external services.
    installer = owner / "tools/vectorcraft/VectorCraftUpdateInstaller.java"
    if not installer.is_file():
        raise FileNotFoundError(installer)
    if (java / installer.name).exists():
        raise ValueError("Updater java source was already generated")
    if "REQUEST_INSTALL_PACKAGES" not in manifest or "VectorCraftUpdateInstaller" not in extras:
        raise AssertionError("Updater source safety guards failed")

    extras_path.write_text(extras)
    activity_path.write_text(activity)
    host_path.write_text(host)
    manifest_path.write_text(manifest)
    about_path.write_text(about)
    shutil.copyfile(installer, java / installer.name)
    print("PASS: Android.5 opt-in verified APK download, production identity/signer gate and system installer consent")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: patch_v0241_android5_updater.py STAGED_BUILDER OWNER_CHECKOUT")
    patch(Path(sys.argv[1]), Path(sys.argv[2]))
