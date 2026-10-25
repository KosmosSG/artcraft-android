"""Test-only OFL Montserrat fixtures from the original author; never bundled in APKs."""
from pathlib import Path
from urllib.request import urlopen
import hashlib, sys
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
base='https://raw.githubusercontent.com/JulietaUla/Montserrat/555facfb2a18c72c3c0380f0d9c0f060453a9058/'
files={
 'fonts/ttf/Montserrat-Regular.ttf':'3e8abe50c44c82e2242e97d1ec8c0d385c4890cdc50447bcdb8605c81a38cfb2',
 'fonts/ttf/Montserrat-SemiBold.ttf':'b4e1563393d73fdff491a869441245aef31add2ec03d9c97a6dae4de07c52fd0',
 'fonts/otf/Montserrat-Medium.otf':'f67081ad026955c8187bebe7dede147a09ddf0cc4d830c138fe2d08bf7b3d5ce',
 'OFL.txt':'8b7141c03fa4f8d44e6345d5d4931709290f0f67875e452e95ac1fd3a027802e',
}
for path,digest in files.items():
 with urlopen(base+path,timeout=60) as response:data=response.read(5*1024*1024)
 assert hashlib.sha256(data).hexdigest()==digest,path
 (root/Path(path).name).write_bytes(data)
print('PASS: pinned original-author OFL fixtures and hashes')
