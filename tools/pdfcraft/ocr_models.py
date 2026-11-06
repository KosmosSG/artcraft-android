"""Fetch and stage the official pinned PDFCraft OCR model pair; fail closed."""
from pathlib import Path
import hashlib, json, shutil, sys, tomllib, urllib.request, zipfile
EXPECTED = {
 'text-detection.onnx':'a917b23dbd9524b465df7e922641b3ff2981623df4ded5a0234004ef2fee7cfe',
 'text-recognition.onnx':'86c145c2edb96c8caed5b1ebb8f44d706408922211451c309c625157dd6061c5',
}
def digest(path):
    with open(path,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def download(url, path, expected):
    if path.is_file() and digest(path)==expected: return
    temp=path.with_suffix(path.suffix+'.part')
    try:
        with urllib.request.urlopen(url,timeout=120) as src, open(temp,'wb') as dst:
            shutil.copyfileobj(src,dst)
        if digest(temp)!=expected: raise ValueError('SHA256 mismatch: '+path.name)
        temp.replace(path)
    finally: temp.unlink(missing_ok=True)
def fetch(source):
    entries=tomllib.loads((source/'ATTRIBUTION.toml').read_text())['fetched']
    records=[next(r for r in entries if r['file']==name) for name in EXPECTED]
    dest=source/'assets/models'; dest.mkdir(parents=True,exist_ok=True)
    for r in records:
        if r['sha256']!=EXPECTED[r['file']]: raise ValueError('Upstream model pin changed')
        download(r['url'],dest/r['file'],r['sha256'])
    r=records[0]
    licence=Path(__file__).with_name('OCR-LICENSE.txt')
    if digest(licence)!=r['licence_sha256']: raise ValueError('Bundled OCR licence mismatch')
    shutil.copyfile(licence,dest/'CC-BY-SA-4.0.txt')
    (dest/'ATTRIBUTION.json').write_text(json.dumps({'models':records,'modified':False},indent=2)+'\n')
    return dest

def stage(source, android):
    dest=fetch(source)
    target=android/'ocr-assets/models'; target.mkdir(parents=True,exist_ok=True)
    for name in [*EXPECTED,'CC-BY-SA-4.0.txt','ATTRIBUTION.json']:
        shutil.copyfile(dest/name,target/name)
    rows=[f'    ("{n}", "{h}"),' for n,h in EXPECTED.items()]
    (android/'src/pdfcraft_ocr_manifest.rs').write_text('const MODELS: &[(&str, &str)] = &[\n'+'\n'.join(rows)+'\n];\n')

def verify(apk):
    with zipfile.ZipFile(apk) as z:
        for name, expected in EXPECTED.items():
            data=z.read('assets/models/'+name)
            if hashlib.sha256(data).hexdigest()!=expected: raise ValueError('Packaged model mismatch: '+name)
            print(name, len(data), expected)
        assert z.read('assets/models/CC-BY-SA-4.0.txt')
        assert json.loads(z.read('assets/models/ATTRIBUTION.json'))['modified'] is False
    print('PASS: both OCR model hashes and attribution verified inside APK')
if __name__=='__main__':
    if sys.argv[1]=='fetch': fetch(Path(sys.argv[2]))
    elif sys.argv[1]=='stage': stage(Path(sys.argv[2]),Path(sys.argv[3]))
    elif sys.argv[1]=='verify': verify(Path(sys.argv[2]))
    else: raise SystemExit('usage: ocr_models.py fetch SOURCE | stage SOURCE ANDROID | verify APK')
