# PhotoCraft v0.12 native Android UI and Shortcut Pad — draft port

Port of the reviewed PhotoCraft private-feature branches onto official storyteller PhotoCraft v0.12.0. Existing original-certificate signing, production releases and version history are untouched.

* Type menu imports fonts directly, selects or refreshes shared folders, with Android Toast feedback; no floating Custom Fonts window.
* Help menu retains the versionCode-aware GitHub updater and adds native Android optional startup check preferences.
* Window menu provides the saved optional bottom Touch Shortcut Pad. It uses official menu command guards, respects text input, and reserves canvas space without generating keyboard events.
* Existing GPU adapter diagnostics/CPU fallback, left/right modifier handling, SAF document bridge, native IME, persisted fonts and exact glossy Pc icon remain in the draft.

**Not release-ready.** Revalidate upstream v0.12 menu patch, Java Activity, Android Rust compatibility, physical keyboard/shortcut behavior and Touch Pad on tablet. No signing, APK publishing, or automatic merger is authorized.
