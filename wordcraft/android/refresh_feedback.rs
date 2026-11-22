//! Font refresh progress shared by the Android poller and ribbon.
#[derive(Default)]
pub struct FontRefresh {
    pub busy: bool,
    total: usize,
    handled: usize,
    imported: usize,
    skipped: usize,
    limited: bool,
}

impl FontRefresh {
    pub fn start(&mut self) -> String {
        *self = Self { busy: true, ..Self::default() };
        "Refreshing shared fonts…".into()
    }

    pub fn staged(&mut self, total: usize, skipped: usize, limited: bool) -> String {
        *self = Self { busy: total > 0, total, skipped, limited, ..Self::default() };
        self.message()
    }

    pub fn record(&mut self, success: bool) -> String {
        self.handled += 1;
        if success { self.imported += 1; } else { self.skipped += 1; }
        self.busy = self.handled < self.total;
        self.message()
    }

    pub fn stop(&mut self, message: String) -> String {
        self.busy = false;
        message
    }

    fn message(&self) -> String {
        if self.busy {
            return format!("Refreshing fonts: {} of {} files processed…", self.handled, self.total);
        }
        let mut message = if self.total == 0 && self.skipped == 0 {
            "Font refresh complete: no supported font files found.".to_owned()
        } else {
            format!("Font refresh complete: {} imported; {} already available or skipped.", self.imported, self.skipped)
        };
        if self.limited { message.push_str(" Scan limit reached; some folders or files were not processed."); }
        message
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_folder_finishes_instead_of_staying_on_importing() {
        let mut state = FontRefresh::default();
        state.start();
        let message = state.staged(0, 0, false);
        assert!(!state.busy);
        assert!(message.contains("no supported font files"));
        assert!(!message.contains("processed…"));
    }

    #[test]
    fn completion_counts_imports_and_already_available_files() {
        let mut state = FontRefresh::default();
        state.start();
        state.staged(2, 1, false);
        assert!(state.record(true).contains("1 of 2"));
        assert!(state.busy);
        let message = state.record(false);
        assert!(!state.busy);
        assert!(message.contains("1 imported; 2 already available or skipped"));
    }

    #[test]
    fn truncated_scan_is_disclosed_even_with_no_staged_files() {
        let mut state = FontRefresh::default();
        let message = state.staged(0, 3, true);
        assert!(!state.busy);
        assert!(message.contains("3 already available or skipped"));
        assert!(message.contains("Scan limit reached"));
    }

    #[test]
    fn error_and_cancellation_allow_a_later_refresh() {
        let mut state = FontRefresh::default();
        state.start();
        assert_eq!(state.stop("Folder access expired".into()), "Folder access expired");
        assert!(!state.busy);
        state.start();
        assert!(state.busy);
        state.stop("Font folder selection cancelled".into());
        assert!(!state.busy);
    }
}
