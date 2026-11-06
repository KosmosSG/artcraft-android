import hashlib, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
import ocr_models as m
class ModelPackaging(unittest.TestCase):
    def test_bad_download_does_not_replace_verified_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); incoming=root/'incoming'; target=root/'model.onnx'
            incoming.write_bytes(b'bad'); target.write_bytes(b'previous')
            with self.assertRaises(ValueError):
                m.download(incoming.as_uri(),target,hashlib.sha256(b'good').hexdigest())
            self.assertEqual(target.read_bytes(),b'previous')
            self.assertFalse(target.with_suffix('.onnx.part').exists())
    def test_valid_download_and_cached_model(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); incoming=root/'incoming'; target=root/'model.onnx'
            incoming.write_bytes(b'good'); expected=hashlib.sha256(b'good').hexdigest()
            m.download(incoming.as_uri(),target,expected)
            incoming.unlink()
            m.download(incoming.as_uri(),target,expected)
            self.assertEqual(target.read_bytes(),b'good')
    def test_apk_rejects_changed_model(self):
        with tempfile.TemporaryDirectory() as d:
            apk=Path(d)/'test.apk'
            with zipfile.ZipFile(apk,'w') as z: z.writestr('assets/models/a.onnx',b'bad')
            with patch.dict(m.EXPECTED,{'a.onnx':hashlib.sha256(b'good').hexdigest()},clear=True):
                with self.assertRaises(ValueError): m.verify(apk)
