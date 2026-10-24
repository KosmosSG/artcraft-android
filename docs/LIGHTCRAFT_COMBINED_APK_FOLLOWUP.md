# LightCraft combined APK follow-up — 24 October 2026

Reviewed head: 40d827285c1c7f5016a3d4dc2a82136c0254bdb9 (PR16).

## Verified evidence

The three existing candidate/source/smoke runs all succeeded:
- https://github.com/KosmosSG/artcraft-android/actions/runs/40012385046
- https://github.com/KosmosSG/artcraft-android/actions/runs/40012385063
- https://github.com/KosmosSG/artcraft-android/actions/runs/40012385035

The updater now recognizes exact suite-standard lightcraft-<version>.apk alongside its legacy aliases. This is build evidence, not proof of production certificate continuity or device behavior.

## Remaining implementation/review gates

1. Release discovery currently reads only the first 100 suite releases. Add bounded pagination; test a LightCraft release on page two, an empty terminal page, HTTP errors and a response-size limit. Never report up-to-date when the search was truncated.
2. Replace inferred tag-derived version codes with verified per-release Android metadata tied to exact package, certificate, asset digest and persistently reserved code. The current patch-plus-revision formula can collide (patch 1/revision 1 equals patch 0/revision 2). Do not reserve or publish codes using that inference.
3. Add a total deadline and single-flight request handling to the updater; per-read timeouts alone cannot bound a slow response. Verify manual retry and stale-result isolation.
4. Verify packaged launcher resources, production identity and unchanged payload through the reviewed isolated signer before a replacement install announcement.
5. Fonts/shared folders must reach the actual watermark text renderer; font availability in egui alone is insufficient. Preserve RAW, colour and export engines.
6. Tablet acceptance remains separate: native Updates tab, startup preference persistence, SAF RAW import/export, keyboard/IME, touch/stylus, GPU diagnostics and CPU fallback. No advanced stylus support is claimed.

No new heavy build is needed for this evidence record. Reuse PR16; no merge, key bootstrap, publication or production code change is authorized by this checklist.
