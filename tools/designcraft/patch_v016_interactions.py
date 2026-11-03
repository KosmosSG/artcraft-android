#!/usr/bin/env python3
"""DesignCraft v0.16 debug-only Android shared SAF fonts and hardware keyboard integration."""
from pathlib import Path
import sys

def put_once(text, old, new, label):
    count=text.count(old)
    if count!=1: raise ValueError(f"{label}: expected one anchor, found {count}: {old[:80]}")
    return text.replace(old,new,1)

def edit(path,old,new,label):
    path.write_text(put_once(path.read_text(),old,new,label))

def ui_source(src):
    base=src/"crates/ui-egui/src"
    p=base/"menus/ui_commands.rs"
    a='    ("app.artcraftImportFont", "Import Fonts (TTF/OTF/TTC)…", None, "{}"),'
    edit(p,a,a+'''
    #[cfg(target_os = "android")]
    ("app.artcraftSelectSharedFonts", "Select Shared Font Folder…", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftRefreshSharedFonts", "Refresh Shared Fonts", None, "{}"),
    #[cfg(target_os = "android")]
    ("app.artcraftToggleAndroidTools", "Show / Hide Android Tools", None, "{}"),''',"UI command registry")
    p=base/"menus/run.rs"
    a='pub fn take_android_font_import() -> bool {'
    edit(p,a,'''static ANDROID_SHARED_ACTIONS: std::sync::atomic::AtomicU8 =
    std::sync::atomic::AtomicU8::new(0);
#[cfg(target_os = "android")]
static ANDROID_TOOLS_TOGGLE: std::sync::atomic::AtomicBool =
    std::sync::atomic::AtomicBool::new(false);

#[cfg(target_os = "android")]
pub fn take_android_shared_actions() -> u8 {
    ANDROID_SHARED_ACTIONS.swap(0, std::sync::atomic::Ordering::Relaxed)
}

#[cfg(target_os = "android")]
pub fn take_android_tools_toggle() -> bool {
    ANDROID_TOOLS_TOGGLE.swap(false, std::sync::atomic::Ordering::Relaxed)
}

#[cfg(target_os = "android")]
'''+a,"UI action flags")
    a='    if id == "app.artcraftImportFont" {'
    edit(p,a,'''    if id == "app.artcraftToggleAndroidTools" {
        ANDROID_TOOLS_TOGGLE.store(true, std::sync::atomic::Ordering::Relaxed);
        return Some(Ok(Value::Null));
    }
    #[cfg(target_os = "android")]
    if id == "app.artcraftSelectSharedFonts" {
        ANDROID_SHARED_ACTIONS.fetch_or(1, std::sync::atomic::Ordering::Relaxed);
        return Some(Ok(Value::Null));
    }
    #[cfg(target_os = "android")]
    if id == "app.artcraftRefreshSharedFonts" {
        ANDROID_SHARED_ACTIONS.fetch_or(2, std::sync::atomic::Ordering::Relaxed);
        return Some(Ok(Value::Null));
    }
    #[cfg(target_os = "android")]
'''+a,"UI action dispatch")
    p=base/"menus.rs"
    edit(p,'pub use run::take_android_font_import;',
         'pub use run::{take_android_font_import, take_android_shared_actions, take_android_tools_toggle};',"UI action exports")
    p=base/"menus/tables.rs"
    a='            "ui:app.artcraftImportFont",\n            "-",'
    edit(p,a,'            "ui:app.artcraftImportFont",\n            "ui:app.artcraftSelectSharedFonts",\n            "ui:app.artcraftRefreshSharedFonts",\n            "-",',"Type actions")
    edit(p,'    (\n        "Help",\n        &[','''    (
        "Android",
        &[
            "ui:app.artcraftImportFont",
            "ui:app.artcraftSelectSharedFonts",
            "ui:app.artcraftRefreshSharedFonts",
            "-",
            "ui:app.artcraftToggleAndroidTools",
        ],
    ),
    (
        "Help",
        &[''',"main Android menu")
    p=base/"dialogs.rs";s=p.read_text()
    a='let action = ctx.input(|i| i.events.iter().find_map(|event| match event {'
    s=put_once(s,a,'''let action = ctx.data_mut(|d| d.remove_temp::<u8>(
            egui::Id::new("designcraft.unsaved.dcs")
        )).or_else(|| ctx.input(|i| i.events.iter().find_map(|event| match event {''',"early dialog DCS")
    start=s.index('let action = ctx.data_mut')
    ending='''            _ => None,
        }));'''
    pos=s.index(ending,start)
    s=s[:pos]+s[pos:].replace(ending,'''            _ => None,
        })));''',1)
    p.write_text(s)

def java_source(root,android):
    p=android/"java/com/artcraft/designcraft/DesignCraftActivity.java"
    s=p.read_text()
    s=put_once(s,'    private static final int REQ_FOLDER = 0x5046;',
                 '''    private static final int REQ_FOLDER = 0x5046;
    private static final int REQ_FONT_FOLDER = 0x6041;
    private static final String FONT_FOLDER_PREF = "dc_shared_font_tree";''',"shared folder id")
    s=put_once(s,'        handleIncomingFiles(getIntent());',
               '        handleIncomingFiles(getIntent());\n        dcRestoreSharedFontsOnStartup();',"restore on startup")
    s=put_once(s,'        super.onActivityResult(requestCode, resultCode, data);','''        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_FONT_FOLDER) {
            requestIds.remove(REQ_FONT_FOLDER);
            if (resultCode != RESULT_OK || data == null || data.getData() == null) {
                enqueueCancel(0, "font_folder");
                return;
            }
            try {
                Uri tree = data.getData();
                getContentResolver().takePersistableUriPermission(
                    tree, Intent.FLAG_GRANT_READ_URI_PERMISSION);
                getSharedPreferences(PREFS, MODE_PRIVATE).edit()
                    .putString(FONT_FOLDER_PREF, tree.toString()).apply();
                scanFontFolder(0, tree);
            } catch (Exception error) {
                enqueueError(0, "font_folder", error.toString());
            }
            return;
        }''',"folder result")
    extra=(root/"tools/designcraft/support/font_methods.java").read_text()
    before='new File(getFilesDir(), "home/.local/share/fonts/shared")'
    after='new File(appStorageDir(), "home/.local/share/fonts/shared")'
    extra=put_once(extra,before,after,"matching Android HOME")
    term=s.rfind("\n}")
    if term<0: raise ValueError("unexpected Android Activity terminator")
    s=s[:term]+"\n"+extra+"\n"+s[term:]
    # NativeActivity physical-key routing (IME remains free to enter printable text).
    keys='''    private final java.util.concurrent.atomic.AtomicInteger dcDialogAction =
        new java.util.concurrent.atomic.AtomicInteger();
    private volatile boolean dcDialogActive;
    private final java.util.Set<Integer> dcDialogHeld =
        java.util.Collections.synchronizedSet(new java.util.HashSet<>());

    private final java.util.concurrent.atomic.AtomicInteger dcToolAction =
        new java.util.concurrent.atomic.AtomicInteger(0);

    /** Take a physical T/V key that was intercepted before Android's IME. */
    public int dcTakeToolAction() {
        return dcToolAction.getAndSet(0);
    }

    public int dcUnsavedDialog(boolean active) {
        dcDialogActive = active;
        if (!active) {
            // Never carry a pending D/C/S letter to the next unsaved dialog.
            dcDialogAction.set(0);
            dcDialogHeld.clear();
            return 0;
        }
        return dcDialogAction.getAndSet(0);
    }

    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        if (event == null) return super.dispatchKeyEvent(event);
        if ((event.getFlags() & KeyEvent.FLAG_SOFT_KEYBOARD) != 0)
            return super.dispatchKeyEvent(event);
        int code = event.getKeyCode();
        int state = event.getAction();
        if (dcDialogHeld.contains(code)) {
            if (state == KeyEvent.ACTION_UP) dcDialogHeld.remove(code);
            // Keep the native input queue running, so Rust can process and
            // repaint the dialog immediately after a hardware shortcut.
            return super.dispatchKeyEvent(event);
        }
        int action = code == KeyEvent.KEYCODE_D ? 1 :
            (code == KeyEvent.KEYCODE_C ? 2 : (code == KeyEvent.KEYCODE_S ? 3 : 0));
        if (dcDialogActive && action != 0 && event.hasNoModifiers()) {
            if (state == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
                dcDialogHeld.add(code);
                dcDialogAction.compareAndSet(0, action);
            }
            // Let the Rust modal poll take the action. Never forward D/C/S
            // into the document or focused EditText while the dialog is open.
            return true;
        }
        boolean escape = code == KeyEvent.KEYCODE_ESCAPE;
        boolean close = code == KeyEvent.KEYCODE_W && event.isCtrlPressed();
        // Queue physical T/V even if Android's IME state is stale after
        // Escape. Rust checks whether the document is actually still typing
        // before using this fallback, so printable text remains intact.
        if (!dcDialogActive && event.hasNoModifiers()
                && state == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0) {
            if (code == KeyEvent.KEYCODE_T) dcToolAction.set(1);
            else if (code == KeyEvent.KEYCODE_V) dcToolAction.set(2);
        }
        // Deliver normal key events as well, so the upstream keymap keeps
        // other shortcuts working. Rust deduplicates the T/V fallback.
        if (escape && imeWanted && state == KeyEvent.ACTION_DOWN) {
            imeWanted = false;
            if (imeView != null) imeView.clearFocus();
        }
        if (escape || close) {
            if (state == KeyEvent.ACTION_DOWN) {
                super.onKeyDown(code, event);
                return true;
            }
            if (state == KeyEvent.ACTION_UP) {
                super.onKeyUp(code, event);
                return true;
            }
        }
        return super.dispatchKeyEvent(event);
    }

'''
    s=put_once(s,'    public String safFilesDir() { return appStorageDir().getAbsolutePath(); }',
        keys+'    public String safFilesDir() { return appStorageDir().getAbsolutePath(); }',"hardware keyboard")
    p.write_text(s)

def launcher(android):
    p=android/"src/lib.rs";s=p.read_text()
    a='''        match (kind, status) {
            ("open", "ok") => {'''
    b='''        if kind == "font_folder" {
            let count = value.get("count").and_then(serde_json::Value::as_u64).unwrap_or(0);
            if status == "ok" {
                v016_android::report_shared(Ok(format!(
                    "Shared folder scan completed: {count} font files"
                )));
            } else if status == "cancel" {
                // Release the pending state, otherwise a cancelled picker
                // makes all later Refresh clicks look permanently busy.
                v016_android::report_shared(Err(
                    "Shared font folder selection cancelled".to_owned()
                ));
            } else {
                v016_android::report_shared(Err(
                    value.get("message").and_then(serde_json::Value::as_str)
                        .unwrap_or("Shared font refresh failed").to_owned()
                ));
            }
            continue;
        }
        match (kind, status) {
            ("open", "ok") => {'''
    s=put_once(s,a,b,"SAF shared events")
    s=put_once(s,'        self.handle_clipboard_shortcuts(raw);',
        '''        self.handle_clipboard_shortcuts(raw);
        v016_android::handle_keys(&mut self.inner, ctx, raw, &self.saf_bridge);''',
        "pre-widget keyboard")
    bridge='''        pub fn dc_font_action(&self, id: u64, refresh: bool) -> Result<(), String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<()> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                if refresh {
                    env.call_method(&*activity, jni_str!("dcRefreshFontFolder"),
                        jni_sig!("(J)V"), &[JValue::Long(id as i64)])?;
                } else {
                    env.call_method(&*activity, jni_str!("dcRequestFontFolder"),
                        jni_sig!("(J)V"), &[JValue::Long(id as i64)])?;
                }
                Ok(())
            }).map_err(|e| e.to_string())
        }

        pub fn dc_tool_action(&self) -> Result<i32, String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                env.call_method(&*activity, jni_str!("dcTakeToolAction"),
                    jni_sig!("()I"), &[])?.i()
            }).map_err(|e| e.to_string())
        }

        pub fn dc_dialog_action(&self, active: bool) -> Result<i32, String> {
            self.vm.attach_current_thread(|env| -> jni::errors::Result<i32> {
                let ptr = self.app.activity_as_ptr() as jni::sys::jobject;
                let activity = unsafe { env.as_cast_raw::<JObject>(&ptr)? };
                env.call_method(&*activity, jni_str!("dcUnsavedDialog"),
                    jni_sig!("(Z)I"), &[JValue::Bool(active)])?.i()
            }).map_err(|e| e.to_string())
        }

'''
    s=put_once(s,'        pub fn request_folder(&self, id: u64) -> Result<(), String> {',
        bridge+'        pub fn request_folder(&self, id: u64) -> Result<(), String> {',"JNI bridge")
    p.write_text(s)

def main():
    if len(sys.argv)!=4: raise SystemExit("usage: patch_v016_interactions.py ROOT SRC ANDROID")
    root,src,android=(Path(p).resolve() for p in sys.argv[1:])
    if src.name!="designcraft" or android.name!="designcraft-android":
        raise ValueError("This source overlay is only for DesignCraft v0.16")
    ui_source(src)
    launcher(android)
    java_source(root,android)
    print("DesignCraft v0.16 debug: recursive shared SAF fonts, Android menu, keyboard bridge staged")

if __name__=="__main__": main()
