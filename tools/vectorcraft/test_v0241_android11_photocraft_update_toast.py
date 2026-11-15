"""Source contract checks for native PhotoCraft-style VectorCraft update Toast.

Run after patch_v0241_android11_photocraft_update_toast.py against generated
staging (no APK, network, install, or production update performed).
"""
from pathlib import Path
import sys

def verify(root: Path) -> None:
    a=root/"adapters/vectorcraft"
    java=(a/"java/com/artcraft/vectorcraft/VectorCraftActivity.java").read_text()
    host=(a/"src/lib.rs").read_text()
    extras=(a/"java/com/artcraft/vectorcraft/VectorCraftExtras.java").read_text()
    installer=(a/"java/com/artcraft/vectorcraft/VectorCraftUpdateInstaller.java").read_text()
    about=(root/"source/vectorcraft/crates/ui-egui/src/dialogs/about.rs").read_text()
    assert java.count('VC_ANDROID11_PHOTOCRAFT_UPDATE_TOAST') == 1
    assert java.count('vcShowUpdateToast(String message)') == 1
    assert 'runOnUiThread(() -> {' in java
    assert 'android.widget.Toast.makeText(this, label, android.widget.Toast.LENGTH_LONG).show()' in java
    assert java.count('vcDownloadUpdate(String version)') == 1
    assert java.count('vcAndroid11HistoryMode(boolean enabled)') == 1
    assert 'vcResetIme(long requestId)' in java
    assert host.count('fn vc_show_update_toast(&self, message: &str)') == 1
    assert host.count('manual_update_toast_pending: bool') == 1
    assert 'manual_update_toast_pending: false' in host
    assert 'self.manual_update_toast_pending = true;' in host
    assert 'vc_show_update_toast("Checking for updates…")' in host
    assert 'vc_show_update_toast("Downloading VectorCraft update…")' in host
    assert 'vc_show_update_toast("VectorCraft update service unavailable.")' in host
    assert '"verified" | "install_pending" | "permission_required"' in host
    assert 'self.bridge.download_verified_update(version)' in host
    assert 'self.updates.downloadable' in host
    assert 'self.bridge.vc_android11_poll_history()' in host
    assert 'has_android_redo_chord(' in host
    assert 'has_android_undo_chord(' in host
    assert 'self.ime.poll(ctx, raw);' in host
    assert 'verifiedUpdater.start(version, updateIo)' in extras
    assert 'verifiedUpdater.remember(latest, latestAssetUrl, latestDigest, latestAssetBytes)' in extras
    assert 'com.artcraft.vectorcraft' in installer
    assert 'sameSigningIdentity(' in installer
    assert 'MessageDigest.isEqual(' in installer
    assert 'canRequestPackageInstalls()' in installer
    assert 'session.commit(sender.getIntentSender())' in installer
    assert 'Download & Install VectorCraft' in about
    assert 'Check for Updates' in about
    assert 'getBoolean("enabled", true)' in java
    print("PASS: PhotoCraft-style bottom-center native Toast and safe update download/installer, preserved Android.10 typing and Android.11 wheel/keyboard")

if __name__=="__main__":
    verify(Path(sys.argv[1]))
