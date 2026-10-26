"""Compile the actual overlay's surface traversal against host Android view stubs."""
import ast
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

class NativeFocus(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required (available in candidate CI)')
    def test_nested_native_surface_and_hidden_views(self):
        paths = ['tools/designcraft/support/patch_launcher.py', 'tools/effectcraft/integrate_updater.py', 'tools/filmcraft/runtime_patch.py']
        path = next(ROOT / p for p in paths if (ROOT / p).is_file())
        constants = [n.value for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        helper = next(s for s in constants if 'private android.view.View artcraftNativeSurface' in s)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            v = root / 'android/view'; v.mkdir(parents=True)
            (v/'View.java').write_text('package android.view; public class View { public boolean shown=true, focused=false; public int requests=0; public boolean isShown(){return shown;} public boolean hasFocus(){return focused;} public void setFocusable(boolean b){} public void setFocusableInTouchMode(boolean b){} public boolean requestFocus(){focused=true;requests++;return true;} }')
            (v/'SurfaceView.java').write_text('package android.view; public class SurfaceView extends View {}')
            (v/'ViewGroup.java').write_text('package android.view; public class ViewGroup extends View { View[] c; public ViewGroup(View...c){this.c=c;} public int getChildCount(){return c.length;} public View getChildAt(int i){return c[i];} }')
            (v/'Window.java').write_text('package android.view; public class Window { public View root; public View getDecorView(){return root;} }')
            harness = '''import android.view.*;
public class Harness {
 Window window=new Window(); Window getWindow(){return window;}
 HELPER
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
  Harness h=new Harness(); View overlay=new View(); SurfaceView s=new SurfaceView();
  SurfaceView hidden=new SurfaceView(); hidden.shown=false;
  ViewGroup group=new ViewGroup(hidden,overlay,new ViewGroup(s)); h.window.root=group;
  h.artcraftRestoreCanvasFocus(); check(s.focused && !overlay.focused && !group.focused && !hidden.focused);
  h.artcraftRestoreCanvasFocus(); check(s.requests==1);
  h.window.root=new ViewGroup(overlay,hidden); check(h.artcraftNativeSurface(h.window.root)==null);
  h.window=null; h.artcraftRestoreCanvasFocus();
 }
}'''.replace('HELPER',helper)
            (root/'Harness.java').write_text(harness)
            subprocess.run(['javac','-d',tmp,*map(str,v.glob('*.java')),str(root/'Harness.java')],check=True)
            subprocess.run(['java','-cp',tmp,'Harness'],check=True)

if __name__=='__main__': unittest.main()
