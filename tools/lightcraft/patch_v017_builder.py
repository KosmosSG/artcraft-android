#!/usr/bin/env python3
"""Stage reviewed LightCraft v0.17 SAF create-new support in an Android builder COPY.

Read-only unless --apply is passed. No APK, GitHub Actions, signing or release.
The new upstream Services::write_new callback must not replace an existing file.
SAF staged files under media/ are rejected because committing them could still
overwrite a remote document selected earlier by the Android file picker.
"""
import argparse
from pathlib import Path

MARKER = 'LIGHTCRAFT_V017_WRITE_NEW_PRIVATE_ONLY'
LIGHTCRAFT = '    "lightcraft": {\n'
NEXT_APP = '    "cadcraft": {\n'

PRIVATE_NEW_WRITER = '''/// LIGHTCRAFT_V017_WRITE_NEW_PRIVATE_ONLY: create-new for private paths only.
/// SAF staged files live under media/ and MUST NOT use this callback:
/// an Android provider might overwrite a previously selected URI.
fn saf_write_new_private(bridge: &saf::Bridge, path: &str, bytes: &[u8]) -> Result<(), String> {
    use std::io::Write as _;
    use std::path::Component;

    let root = bridge.files_dir()?.canonicalize()
        .map_err(|e| format!("Android app data directory unavailable: {e}"))?;
    let requested = std::path::Path::new(path);
    let relative = requested.strip_prefix(&root)
        .map_err(|_| "Create-new writes require an absolute app-private path".to_owned())?;
    if relative.as_os_str().is_empty()
        || relative.components().any(|c| !matches!(c, Component::Normal(_)))
    {
        return Err("Invalid create-new file path".to_owned());
    }
    if relative.components().next() == Some(Component::Normal(std::ffi::OsStr::new("media"))) {
        return Err("Create-new SAF exports are unavailable: refusing possible URI overwrite".to_owned());
    }
    let parent = requested.parent().ok_or("Create-new path has no parent")?;
    std::fs::create_dir_all(parent)
        .map_err(|e| format!("Could not create parent directory: {e}"))?;
    let canonical_parent = parent.canonicalize()
        .map_err(|e| format!("Could not check parent directory: {e}"))?;
    if !canonical_parent.starts_with(&root) {
        return Err("Create-new path would escape private app storage".to_owned());
    }
    let mut output = std::fs::OpenOptions::new().write(true).create_new(true)
        .open(requested)
        .map_err(|e| format!("Cannot create new file without replacing an existing file: {e}"))?;
    if let Err(error) = output.write_all(bytes).and_then(|_| output.sync_all()) {
        drop(output);
        let _ = std::fs::remove_file(requested);
        return Err(format!("Could not finish creating new file: {error}"));
    }
    Ok(())
}

'''


def patch_source(content: str) -> str:
    """Fail closed on layout drift and modify ONLY the LightCraft SAF recipe."""
    if content.count('SAF_RECIPES = {') != 1:
        raise ValueError('Cannot locate one Android SAF recipes table')
    region_start = content.index('SAF_RECIPES = {')
    if content.count(LIGHTCRAFT, region_start) < 1:
        raise ValueError('LightCraft recipe is missing')
    start = content.index(LIGHTCRAFT, region_start)
    if content.count(NEXT_APP, start) < 1:
        raise ValueError('Cannot identify LightCraft recipe boundary')
    end = content.index(NEXT_APP, start)
    segment = content[start:end]
    if MARKER in segment:
        if segment.count(MARKER) != 1 or 'write_new: Some(Box::new(' not in segment:
            raise ValueError('Existing LightCraft patch is incomplete or ambiguous')
        return content
    if 'write_new: Some(' in segment:
        raise ValueError('LightCraft create-new writer already exists; review instead of replacing')
    service = "        \"services\": '''\n"
    if segment.count(service) != 1:
        raise ValueError('LightCraft Services recipe layout changed')
    func = 'fn saf_services(bridge: saf::Bridge, state: Arc<SafState>, _inbox: SafInbox) -> Services {\n'
    if segment.count(func) != 1:
        raise ValueError('LightCraft SAF Services constructor layout changed')
    bridge = '    let write_bridge = bridge.clone_ref();\n'
    if segment.count(bridge) != 1:
        raise ValueError('Expected exactly one LightCraft writer bridge clone')
    writer = '        write: Some(Box::new(move |path: &str, bytes: &[u8]| saf_write_and_commit(&write_bridge, path, bytes))),\n'
    if segment.count(writer) != 1:
        raise ValueError('Existing LightCraft SAF write service has drifted')
    segment = segment.replace(func, PRIVATE_NEW_WRITER + func, 1)
    segment = segment.replace(bridge, bridge + '    let write_new_bridge = bridge.clone_ref();\n', 1)
    segment = segment.replace(writer, writer + '        write_new: Some(Box::new(move |path: &str, bytes: &[u8]| saf_write_new_private(&write_new_bridge, path, bytes))),\n', 1)
    return content[:start] + segment + content[end:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('builder', type=Path, help='Local copy of pinned Android builder')
    parser.add_argument('--apply', action='store_true', help='Modify local builder COPY')
    args = parser.parse_args()
    path = args.builder / 'lib' / 'build-common.sh'
    original = path.read_text(encoding='utf-8')
    patched = patch_source(original)
    if args.apply:
        if patched != original:
            path.write_text(patched, encoding='utf-8')
        print('LightCraft v0.17 private create-new writer staged in local Android builder copy.')
    else:
        print('LightCraft v0.17 builder patch preflight passed (read-only).')
    print('No APK, production signing, GitHub Actions, or publication performed.')


if __name__ == '__main__':
    main()
