"""Exercise the actual pinned-builder patch and generated launcher icons."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from PIL import Image, ImageDraw, ImageFilter
from prepare_icon import normalize, BRAND
from adaptive_safe import patch

ROOT = Path(__file__).parent


class RevisionTests(unittest.TestCase):
    def test_normalized_icon_and_adaptive_masks_have_no_black_border(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'normalized.png'
            normalize(ROOT / 'icon/wordcraft-approved-192.webp', source)
            original = Image.open(ROOT / 'icon/wordcraft-approved-192.webp').convert('RGBA')
            fixed = Image.open(source).convert('RGBA')
            # The bright glass lettering must retain its exact source pixels.
            for y in range(192):
                for x in range(192):
                    if original.getpixel((x, y))[1] > 80:
                        self.assertEqual(original.getpixel((x, y)), fixed.getpixel((x, y)))
            for point in [(0, 0), (191, 0), (0, 191), (191, 191)]:
                self.assertEqual(fixed.getpixel(point), BRAND)
            (root / 'lib').mkdir()
            shutil.copyfile(ROOT / 'reference/app_icons.py', root / 'lib/app_icons.py')
            patch(root, 'wordcraft')
            spec = importlib.util.spec_from_file_location('generated_icons', root / 'lib/app_icons.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.generate(root, 'wordcraft', root / 'res', source)
            self.assertNotIn('#000000', (root / 'res/drawable/ic_launcher_background.xml').read_text())
            fg = Image.open(root / 'res/drawable-xxxhdpi/ic_launcher_foreground.png').convert('RGBA')
            for shape in ['circle', 'squircle', 'square']:
                mask = Image.new('L', fg.size)
                draw = ImageDraw.Draw(mask)
                if shape == 'circle': draw.ellipse((72, 72, 359, 359), fill=255)
                elif shape == 'squircle': draw.rounded_rectangle((72, 72, 359, 359), radius=64, fill=255)
                else: draw.rectangle((72, 72, 359, 359), fill=255)
                inset = mask.filter(ImageFilter.MinFilter(9))
                for y in range(432):
                    for x in range(432):
                        if mask.getpixel((x, y)) and not inset.getpixel((x, y)):
                            self.assertGreater(fg.getpixel((x, y))[2], 120)

    def test_pinned_builder_gets_integrated_menu_without_tools_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ['lib', 'templates/android', 'source/wordcraft/crates/ui-egui/src']:
                (root / directory).mkdir(parents=True)
            shutil.copyfile(ROOT / 'reference/build-common.sh', root / 'lib/build-common.sh')
            shutil.copyfile(ROOT / 'reference/app_icons.py', root / 'lib/app_icons.py')
            shutil.copyfile(ROOT / 'reference/SafActivity.java', root / 'templates/android/SafActivity.java')
            java = root / 'templates/android/SafActivity.java'
            java.write_text(java.read_text().rstrip() + '\n')
            shutil.copyfile(ROOT / 'reference/ribbon.rs', root / 'source/wordcraft/crates/ui-egui/src/ribbon.rs')
            subprocess.run([sys.executable, str(ROOT / 'patch_builder.py'), str(root)], check=True)
            script = (root / 'lib/build-common.sh').read_text()
            self.assertIn('{wc_preui}{inner_ui}', script)
            self.assertIn('self.wc.prepare_menu(ui.ctx(), frame)', script)
            self.assertIn('self.wc.update_feedback(ui.ctx())', script)
            subprocess.run(['bash', '-n', str(root / 'lib/build-common.sh')], check=True)
            ribbon = (root / 'source/wordcraft/crates/ui-egui/src/ribbon.rs').read_text()
            self.assertIn('width + android_tools_width', ribbon)
            self.assertEqual(ribbon.count('artcraft_android_menu(ui);'), 1)
            self.assertIn('ui.menu_button("ArtCraft"', ribbon)
            shell = (root / 'templates/android/wordcraft_android.rs').read_text()
            self.assertNotIn('wc_android_menu', shell)
            self.assertNotIn('Window::new("WordCraft Android tools")', shell)
            self.assertIn('wcSetStartupUpdates', shell)
            self.assertIn('TopBottomPanel::bottom("wc_update_feedback")', shell)
            self.assertIn('update_checking', shell)
            self.assertIn('request_repaint_after(Duration::from_millis(250))', shell)
            self.assertNotIn('Window::new("WordCraft update', shell)
            java = (root / 'templates/android/SafActivity.java').read_text()
            self.assertIn('wcShowUpdateMessage(String message)', java)
            self.assertIn('WordCraft-v" + version + "-arm64-v8a.apk"', java)
            self.assertIn('wcPollUpdateResult()', java)
            self.assertIn('Window::new("WordCraft Shortcut Pad")', shell)


if __name__ == '__main__':
    unittest.main()
