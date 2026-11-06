"""Expose borrowed NDK motion history in PDFCraft's staged NativeActivity only."""
from pathlib import Path
import sys

def patch(text):
    marker = 'pub fn pdfcraft_history('
    if marker in text:
        return text
    anchor = '    pub fn meta_state(&self) -> MetaState {'
    assert text.count(anchor) == 2, 'NativeActivity motion/key metadata API drift'
    start = text.index('    /// Returns the state of any modifier keys that were pressed during the event.')
    return text[:start] + '''    /// Batched relative scroll samples, oldest first; the current sample is excluded.
    pub fn pdfcraft_history(&self) -> ndk::event::HistoricalMotionEventsIter<'_> {
        self.ndk_event.history()
    }

''' + text[start:]

if __name__ == '__main__':
    p = Path(sys.argv[1]) / 'src/native_activity/input.rs'
    p.write_text(patch(p.read_text()))
