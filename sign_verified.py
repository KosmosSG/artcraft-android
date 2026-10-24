"""Sign only a SHA-pinned verified APK using an existing app-specific identity."""
import base64, hashlib, io, json, os, pathlib, re, subprocess, tarfile, tempfile, urllib.request, zipfile
P=pathlib.Path

def digest(b): return hashlib.sha256(b).hexdigest()
def run(args, env=None, payload=None):
    p=subprocess.run([str(x) for x in args],input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if p.returncode: raise RuntimeError('Protected operation failed: '+str(args[0]))
    return p.stdout

def payload(apk):
    with zipfile.ZipFile(apk) as z:
        return {n:digest(z.read(n)) for n in z.namelist() if not re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))',n,re.I)}

def main():
    os.umask(0o077)
    c=json.loads(P('sign-config.json').read_text()); app=c['app']; a=app.lower()
    sdk=P(os.environ['ANDROID_HOME'])/'build-tools'/'35.0.0'; signer=sdk/'apksigner'; aapt=sdk/'aapt2'
    def cert(apk):
        out=run([signer,'verify','--verbose','--print-certs',apk]).decode()
        pins=re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)',out)
        assert len(pins)==1,'Expected exactly one signer'
        return pins[0].lower()
    def identity(apk):
        s=run([aapt,'dump','badging',apk]).decode()
        m=re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'",s)
        assert m and "native-code: 'arm64-v8a'" in s
        return m[1],int(m[2]),m[3]
    files=list(P('candidate').rglob('*.apk')); assert len(files)==1
    apk=files[0]; assert digest(apk.read_bytes())==c['candidate_sha256']
    info=json.loads(next(P('candidate').rglob('verification.json')).read_text())
    assert info['compiled_pixels_verified'] and info['native_ui_brand_embedded']
    expected_id=(c['package'],c['code'],c['version']); assert identity(apk)==expected_id
    with tempfile.TemporaryDirectory(dir=os.environ['RUNNER_TEMP']) as d:
        d=P(d)
        if 'baseline_url' in c:
            urllib.request.urlretrieve(c['baseline_url'],d/'previous.apk')
            assert digest((d/'previous.apk').read_bytes())==c['baseline_sha256']
            old=identity(d/'previous.apk'); assert old[0]==c['package'] and old[1]<c['code']
            pin=cert(d/'previous.apk')
        else:
            run(['gh','run','download','39822965531','-R','KosmosSG/artcraft-android','-n','deckcraft-encrypted-signing-backup','-D',d/'original'])
            s=(d/'original/certificate-sha256.txt').read_text().split('=')[-1].strip().replace(':','').lower()
            assert re.fullmatch('[0-9a-f]{64}',s); pin=s
        env=dict(os.environ)
        if a in ['vectorcraft','pdfcraft','deckcraft']:
            key=base64.b64decode(os.environ['KEYSTORE_BASE64'],validate=True)
            store=os.environ['STORE_PASSWORD']; private=os.environ['KEY_PASSWORD']; alias=os.environ['KEY_ALIAS']
        else:
            spec=c['restore']; backup=P(spec['backup'])
            if spec['kind']=='openssl':
                decrypted=run(['openssl','enc','-d','-aes-256-cbc','-pbkdf2','-iter',spec['iterations'],'-pass','env:BACKUP_PASSWORD','-in',backup])
            else:
                decrypted=run(['gpg','--batch','--quiet','--pinentry-mode','loopback','--passphrase-fd','0','--decrypt',backup],payload=(os.environ['BACKUP_PASSWORD']+'\n').encode())
            with tarfile.open(fileobj=io.BytesIO(decrypted),mode='r:*') as t:
                members=t.getmembers()
                assert len(members)==len(spec['members']) and set(m.name for m in members)==set(spec['members'])
                assert all(m.isfile() and m.size<2000000 for m in members)
                key=t.extractfile(spec['key']).read()
                if a=='wordcraft':
                    credentials=json.loads(t.extractfile('credentials.json').read());alias=credentials['alias'];assert alias=='wordcraft-release'
                    store=credentials['store_password'];private=credentials['key_password']
                    assert digest(t.extractfile('wordcraft-certificate.der').read())==pin
                else:
                    alias=spec['alias'];store=t.extractfile(spec['password']).read().decode().strip();private=store
        assert key and store and private and alias
        keypath=d/'existing-key';keypath.write_bytes(key)
        env.update(SIGN_STORE_PASSWORD=store,SIGN_KEY_PASSWORD=private)
        exported=run(['keytool','-exportcert','-keystore',keypath,'-storepass:env','SIGN_STORE_PASSWORD','-alias',alias],env=env)
        assert digest(exported)==pin,'Restored key does not match original certificate'
        # Preserve every non-signature ZIP entry byte-for-byte.
        clean=d/'unsigned.apk'
        original_payload=payload(apk)
        with zipfile.ZipFile(apk) as src, zipfile.ZipFile(clean,'w') as dst:
            for entry in src.infolist():
                if entry.filename in original_payload: dst.writestr(entry,src.read(entry.filename))
        aligned=d/'aligned.apk';run([sdk/'zipalign','-P','16','-f','4',clean,aligned])
        out=P('signed-output');out.mkdir(exist_ok=True)
        target=out/f'{app}-v{c["version"]}-arm64-v8a.apk'
        run([signer,'sign','--ks',keypath,'--ks-key-alias',alias,'--ks-pass','env:SIGN_STORE_PASSWORD','--key-pass','env:SIGN_KEY_PASSWORD','--v4-signing-enabled','false','--out',target,aligned],env=env)
        assert cert(target)==pin and identity(target)==expected_id
        run([sdk/'zipalign','-c','-P','16','4',target])
        assert payload(target)==payload(apk),'APK payload changed during signing'
        h=digest(target.read_bytes())
        info.update(apk_sha256=h,production_signing_verified=True,certificate_sha256=pin,source_run=c['run'],source_commit=c['source_sha'],signed_payload_unchanged=True,device_tested=False,eligible_for_release=False)
        (out/'verification.json').write_text(json.dumps(info,indent=2)+'\n')
        (out/'SHA256SUMS.txt').write_text(f'{h}  {target.name}\n')
        (out/'TESTING-REQUIRED.txt').write_text('Permanently signed testing candidate. Not device-tested. No public release authorized by this workflow. Test in-place update, data/font retention, launcher and native UI logo, SAF, updater, keyboard and GPU on HONOR MagicPad 4.\n')
        print(f'PASS: {app} original certificate, package, version, ARM64, alignment and identical payload. SHA256 {h}')
if __name__=='__main__': main()
