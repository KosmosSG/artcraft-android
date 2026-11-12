"""Read-only metadata/packaging audit; does not claim malware clearance."""
import argparse, hashlib, json, zipfile
from loguru import logger
logger.remove()
from androguard.core.apk import APK
p=argparse.ArgumentParser();p.add_argument('apk');p.add_argument('--expected-sha');a=p.parse_args()
data=open(a.apk,'rb').read();sha=hashlib.sha256(data).hexdigest()
if a.expected_sha: assert sha==a.expected_sha,'APK differs from approved release digest'
assert data[:4]==b'PK\x03\x04','Nonstandard ZIP header'
with zipfile.ZipFile(a.apk) as z:
 assert not z.testzip(),'Corrupt ZIP member'
 assert len(z.namelist())==len(set(z.namelist())),'Duplicate ZIP entries'
 assert all(not n.startswith('/') and '..' not in n.split('/') for n in z.namelist()),'Unsafe ZIP path'
 native=[n for n in z.namelist() if n.startswith('lib/')]
 assert native and all(n.startswith('lib/arm64-v8a/') for n in native),'Unexpected ABI'
 apk=APK(a.apk)
 permissions=sorted(apk.get_permissions())
 allowed={'android.permission.INTERNET','android.permission.REQUEST_INSTALL_PACKAGES','android.permission.READ_EXTERNAL_STORAGE','android.permission.WRITE_EXTERNAL_STORAGE','android.permission.MANAGE_EXTERNAL_STORAGE'}
 assert set(permissions)<=allowed,'New/unreviewed permission'
 assert not apk.get_services() and not apk.get_receivers() and not apk.get_providers(),'Unexpected components'
 report={'sha256':sha,'bytes':len(data),'package':apk.get_package(),'version':apk.get_androidversion_name(),'permissions':permissions,'certificate_sha256':[hashlib.sha256(c).hexdigest() for c in apk.get_certificates_der_v3()],'native':native,'zip_integrity':'pass','scope':'Metadata/packaging inspection only; no Play Protect clearance or full malware verdict.'}
 print(json.dumps(report,indent=2))
