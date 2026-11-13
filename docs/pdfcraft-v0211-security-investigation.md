# PDFCraft v0.21.1 Android.1 investigation

## Verified provenance

Official stable v0.21.1 resolves to `b503b2e62dfeec5598f344e4e287d9c9cbdb34fa`.
Android baseline: `d2296d7dab86863baf8697b3e77c89caea6174bb`, production build 43261309457, preserving owner-tested PR #159 source `7c9da7c71879d255789aef219409844eb5532a20`.
The builder stages the exact official source and reapplies guarded Android overlays. It does not reconstruct upstream functionality.

The upstream comparison changes 541 files. Changes include annotation styles and editing, PDF text rewrite/find-and-replace, forms/document actions, redaction, rendering, OCR, font handling and Office import. Security-relevant changes include zeroizing cryptographic keys/password buffers and stronger bounded filter decoding. Upstream egui changes from `6d518fc799681571963842f95b55a6b68431b15a` to `725a39fca940f77149ffbb9c58eef405a16997bc`; winit stays `a517b3846ee8457d84ee4975110bfda6797c44dc`. No independent dependency upgrades are requested.

Android overlays adapt PageKeys anchors, selection-state reset and on_exit signature while retaining input routing and existing wheel artwork, preferences, pressure, SAF, fonts, OCR and updater paths. Desktop printing and platform-specific Office conversion are not claimed to work on Android; device coverage of new upstream functionality is pending.

## Exact published APK inspection

Downloaded release assets, not locally rebuilt substitutes:

| Item | Android.4 | Android.5 |
|---|---|---|
| SHA-256 | fa65eb8d63cf106d048da402a7966e93814122cea59da9f66e6153e9d4128bda | 41a072925e4bfa7731a24a74cb282e851d361cc327834b7e0cbc755eb044479a |
| Bytes | 42191158 | 42268982 |
| versionCode | 16782340 | 16782341 |
| Package | com.artcraft.pdfcraft | com.artcraft.pdfcraft |

Both extracted v3 certificates have SHA-256 `be7254670cf0d451a17dd7ad8462ada3f806e50ab296d78a5db685e2a30a849f`. The production job reports successful apksigner v3 verification. Local inspection extracts the certificate; it is not independently a cryptographic signature verification.

Both target SDK 35, min SDK 28, debuggable=false. Both contain one exported launcher/document Activity and no declared services, receivers or providers. Both contain only `lib/arm64-v8a/libpdfcraft_android.so`. ZIP headers, paths, duplicate entries and CRC checks pass.

Both declare INTERNET, REQUEST_INSTALL_PACKAGES, MANAGE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE (maxSDK 32) and WRITE_EXTERNAL_STORAGE (maxSDK 29). Broad storage enables the existing direct-file browser; removing it requires validating a SAF-only replacement. None of the SMS/accessibility/notification-listener permissions listed in Google's separate sensitive-permission blocking guidance are present. This does not establish why Google classified the app.

Bundled OCR model hashes match between both APKs and the pinned model manifest:
- text-detection.onnx: a917b23dbd9524b465df7e922641b3ff2981623df4ded5a0234004ef2fee7cfe
- text-recognition.onnx: 86c145c2edb96c8caed5b1ebb8f44d706408922211451c309c625157dd6061c5

## Reviewed code and fixes

Updater accepts the repository's stable PDFCraft release asset pattern, requires SHA-256, copies to a verified private snapshot, checks exact package/version/newer versionCode/signer, and uses a user-confirmed PackageInstaller session. Callbacks use a random private token and session ID. No claim that checksums or matching signatures prove safety.

The exported file handler accepted file:// paths without excluding its own private data. The new PDFCraft-only guard rejects canonical credential/device-protected private paths, including symlink/.. aliases, before querying or copying them. Normal shared file paths and provider-enforced content URI grants remain supported. This is a source-level hardening finding, not an established Play Protect cause.

Wheel hover was forwarded to document input, and native hover synthesis appended another move after wheel filtering. Filtering now runs after both sources, preserves wheel-local position and clears retained egui hover. Contact activation is retained. Hardware verification remains required.

## Unresolved security questions

The screenshot shows Harmful app blocked / This app may be harmful, with More details collapsed. It does not disclose Google's malware/unwanted-software category. No trustworthy exact-Android.5 hash malware-analysis verdict was obtained; prior Android.4 VirusTotal results cannot be applied to this APK. This investigation is not exhaustive binary reverse engineering, dynamic malware analysis or a complete dependency vulnerability audit.

The shared document copier has no explicit byte budget for incoming streams; a malicious document provider may exhaust disk space. No arbitrary PDF size cap is imposed here without defining supported document limits. Browser HTTP(S) file associations exist, but ContentResolver copying is not an HTTP downloader. The packager emits two unusual empty Android-namespaced application children (allowNativeHeapPointerTagging/requestLegacyExternalStorage) in both releases; their significance to Play Protect is unknown.

No false-positive determination or Play Protect clearance is claimed. Keep Play Protect enabled. Device confirmation and Google's classification/appeal outcome are required.

Official guidance: https://developers.google.com/android/play-protect/warning-dev-guidance
Official app-verification appeal entry: https://support.google.com/googleplay/android-developer/answer/2992033
An appeal should identify the exact APK URL, SHA-256, package, version, signing certificate, screenshot/details and explained permissions/updater behavior. No appeal has been submitted automatically.

## Test and release gates

Separate test package `com.artcraft.pdfcraft.v0211test1`, disposable key, versionCode 16782593 (greater than production Android.5). Existing releases and signing secrets unchanged. CI must pass before test delivery. No merge, production signing or stable publication is authorized.

Device checklist: keep Play Protect enabled; record any expanded classification; test hover before first contact over wheel segments with a PDF object underneath, no document highlight/draw/selection; tip activation, eraser and pressure; custom assignments/size/opacity persistence; ESC and repeated D/C/S; Ctrl+Q/relaunch ten times; mouse/trackpad/touch and pinch; PDF editing/forms/redaction/save/reopen; OCR and imported/shared fonts; update-check feedback and startup preference. Test-package data is separate from production.

## Owner test follow-up — 13 November 2026

The owner supplied an expanded Play Protect screenshot for the Android.1 test APK. It still says Harmful app blocked / This app may be harmful / Installing this app may put your device at risk. It provides no malware family/category. The block is confirmed on the separate test package as well as previously on production. This does not prove a certificate-reputation cause, a false positive, or actual malware; earlier source hardening did not clear the block.

Official appeal form verified: https://support.google.com/googleplay/android-developer/contact/protectappeals
The form requests email, application package, the SHA-256 of the APK uploaded to VirusTotal, and supporting information. It states no response will be provided. No appeal or third-party APK upload has been submitted by this workflow.

Exact blocked test package: `com.artcraft.pdfcraft.v0211test1`
Version: `0.21.1-android.1`
APK SHA-256: `985dc737da326fd9f0a36f5f20c34ab48549709f45a28716453a3b13af85331a`
Source: `8a55a760b7a410c992a7577fa4513be30a3e5dcd`
Artifact: https://github.com/KosmosSG/artcraft-android/actions/runs/43334978712/artifacts/13997243297

Suggested factual appeal wording (review before submission):

Please review the Play Protect classification of this independently maintained, open-source PDF editor for Android, distributed through GitHub. The attached warning appears on HONOR MagicPad 4 / MagicOS 10. This submission concerns the exact test package and APK hash entered above. The app provides local PDF editing, annotation, forms, OCR and font import. It declares storage access for document/font handling, Internet for GitHub update checking, and REQUEST_INSTALL_PACKAGES for a user-initiated updater. The updater requires checksum, package, version and signer checks and Android installation confirmation. It does not declare SMS, accessibility or notification-listener access. The separate test package cannot update the production package. The source, build and audit are public in PR #160. We have verified the published bytes and reviewed these paths, but do not claim that a successful build or scanner verdict alone establishes safety. Please review the classification of this exact APK.

Production Android.5 requires a separate entry using `com.artcraft.pdfcraft` and its own `41a072...44479a` full hash above. Never substitute the earlier Android.4 hash or a newly rebuilt APK's hash for the file under appeal. Keep Play Protect enabled.

Wheel appearance follow-up: the global theme's transparent inactive weak fill hid the stock slider rails. The appearance card now locally overrides rail/handle/fill colors, includes size/opacity ranges, and uses bold percentage values. Existing values, ranges, preview behavior and persistence are retained. This UI change is unrelated to the Play Protect classification.
