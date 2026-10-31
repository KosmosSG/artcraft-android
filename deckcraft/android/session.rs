// Settings/session metadata is separate from upstream's dirty-document recovery snapshots.
impl SlideApp {
    pub fn android_save_session(&self, dir: &std::path::Path) -> Result<(), String> {
        let paths: Vec<_> = self.session.documents().iter().filter_map(|d| d.path.clone()).take(64).collect();
        let active = self.session.active().and_then(|d| d.path.clone());
        let bytes = serde_json::to_vec(&serde_json::json!({"paths": paths, "active": active})).map_err(|e| e.to_string())?;
        std::fs::create_dir_all(dir).map_err(|e| e.to_string())?;
        let temp = dir.join("android-session.json.tmp");
        std::fs::write(&temp, bytes).map_err(|e| e.to_string())?;
        std::fs::rename(temp, dir.join("android-session.json")).map_err(|e| e.to_string())
    }

    pub fn android_restore_session(&mut self, dir: &std::path::Path) {
        let path = dir.join("android-session.json");
        let Ok(meta) = std::fs::metadata(&path) else { return };
        if !meta.is_file() || meta.len() > 256 * 1024 { return; }
        let Ok(bytes) = std::fs::read(path) else { return };
        let Ok(value) = serde_json::from_slice::<serde_json::Value>(&bytes) else { return };
        // Recover dirty snapshots first. Never replace them with older saved files.
        if let Some(paths) = value.get("paths").and_then(|v| v.as_array()) {
            for path in paths.iter().take(64).filter_map(|p| p.as_str()) {
                if self.session.documents().iter().any(|d| d.path.as_deref() == Some(path)) { continue; }
                if let Err(error) = self.open_path(path) { self.set_status(format!("Could not restore {path}: {error}")); }
            }
        }
        if let Some(active) = value.get("active").and_then(|v| v.as_str()) {
            if let Some(index) = self.session.documents().iter().position(|d| d.path.as_deref() == Some(active)) {
                self.session.set_active(index);
            }
        }
    }
}

#[cfg(test)]
mod android_session_regression {
    use super::*;
    #[test]
    fn corrupt_session_keeps_current_document() {
        let dir = std::env::temp_dir().join(format!("deck-session-corrupt-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("android-session.json"), b"not json").unwrap();
        let mut app = SlideApp::new(Session::with_new(), Services::default());
        let uid = app.session.active().unwrap().uid;
        app.android_restore_session(&dir);
        assert_eq!(app.session.active().unwrap().uid, uid);
        std::fs::remove_dir_all(dir).unwrap();
    }
    #[test]
    fn session_reopens_saved_file_without_overwriting_current_document() {
        let dir = std::env::temp_dir().join(format!("deck-session-roundtrip-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let source = dir.join("sample.deckcraft");
        let mut app = SlideApp::new(Session::with_new(), Services::default());
        let bytes = deckcraft_engine::cmd::file::save_bytes(&app.session.active().unwrap().doc, "deckcraft").unwrap();
        std::fs::write(&source, bytes).unwrap();
        app.open_path(source.to_str().unwrap()).unwrap();
        app.android_save_session(&dir).unwrap();
        let mut restored = SlideApp::new(Session::new(), Services::default());
        restored.android_restore_session(&dir);
        assert_eq!(restored.session.active().unwrap().path.as_deref(), source.to_str());
        let uid = restored.session.active().unwrap().uid;
        restored.android_restore_session(&dir);
        assert_eq!(restored.session.documents().len(), 1);
        assert_eq!(restored.session.active().unwrap().uid, uid);
        std::fs::remove_dir_all(dir).unwrap();
    }
}
