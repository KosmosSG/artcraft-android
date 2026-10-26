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

    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required (candidate CI runs this test)')
    def test_native_dispatch_bypasses_consuming_view_and_preserves_key_pairs(self):
        paths = ['tools/designcraft/support/patch_launcher.py', 'tools/effectcraft/integrate_updater.py', 'tools/filmcraft/runtime_patch.py']
        tested = 0
        for rel in paths:
            path = ROOT / rel
            if not path.exists(): continue
            constants = [n.value for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            candidates = [s for s in constants if 'boolean dispatchKeyEvent(' in s and 'super.onKeyDown' in s]
            if not candidates: continue
            java = candidates[0]
            start = java.index('@Override public boolean dispatchKeyEvent(')
            body = java.index('{', start)
            depth = 1; end = body + 1
            while depth:
                depth += (java[end] == '{') - (java[end] == '}'); end += 1
            method = java[start:end]
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp); v = root / 'android/view'; v.mkdir(parents=True)
                (v/'KeyEvent.java').write_text('''package android.view;
public class KeyEvent {
 public static final int ACTION_DOWN=0,ACTION_UP=1,KEYCODE_ESCAPE=111,FLAG_SOFT_KEYBOARD=2;
 public int action,code,flags,repeat; public boolean system,modified;
 public KeyEvent(int c,int a){code=c;action=a;}
 public int getKeyCode(){return code;} public int getAction(){return action;}
 public int getFlags(){return flags;} public int getRepeatCount(){return repeat;}
 public boolean hasNoModifiers(){return !modified;} public boolean isSystem(){return system;}
}''')
                (v/'View.java').write_text('package android.view; public class View { public void clearFocus(){} public void setFocusable(boolean b){} public void setFocusableInTouchMode(boolean b){} public boolean requestFocus(){return true;} }')
                (v/'Window.java').write_text('package android.view; public class Window { public View getDecorView(){return new View();} }')
                (root/'Harness.java').write_text('''import android.view.*;
class GameActivity {
 int downs,ups,fallback; KeyEvent last;
 // Simulate a consuming focused view: native delivery must bypass this.
 public boolean dispatchKeyEvent(KeyEvent e){fallback++;return true;}
 public boolean onKeyDown(int c,KeyEvent e){downs++;last=e;return false;}
 public boolean onKeyUp(int c,KeyEvent e){ups++;last=e;return false;}
}
public class Harness extends GameActivity {
 boolean imeWanted; View imeView=new View();
 void imeHide(){imeWanted=false;} void artcraftRestoreCanvasFocus(){}
 View fcFindNativeSurface(View v){return v;} Window getWindow(){return new Window();}
 METHOD
 static void check(boolean b){if(!b)throw new AssertionError();}
 static KeyEvent key(int c,int a){return new KeyEvent(c,a);}
 public static void main(String[] args){
  for(boolean editing:new boolean[]{true,false}){
   Harness h=new Harness(); h.imeWanted=editing;
   KeyEvent down=key(111,0),up=key(111,1);
   h.dispatchKeyEvent(down);h.dispatchKeyEvent(up);
   check(h.downs==1 && h.ups==1 && h.fallback==0 && !h.imeWanted && h.last==up);
  }
  Harness h=new Harness();
  h.dispatchKeyEvent(key(62,0));h.dispatchKeyEvent(key(62,1));
  check(h.downs==1 && h.ups==1 && h.fallback==0);
  KeyEvent chord=key(50,0);chord.modified=true;h.dispatchKeyEvent(chord);
  check(h.last==chord && h.downs==2 && h.fallback==0);
  h.imeWanted=true;h.dispatchKeyEvent(key(29,0));check(h.fallback==1);
  h.imeWanted=false;KeyEvent system=key(24,0);system.system=true;
  h.dispatchKeyEvent(system);check(h.fallback==2);
  KeyEvent soft=key(29,0);soft.flags=2;h.dispatchKeyEvent(soft);check(h.fallback==3);
 }
}'''.replace('METHOD',method))
                subprocess.run(['javac','-d',tmp,*map(str,v.glob('*.java')),str(root/'Harness.java')],check=True)
                subprocess.run(['java','-cp',tmp,'Harness'],check=True)
            tested += 1
        self.assertGreater(tested, 0, 'No updated native dispatch overlay tested')

if __name__=='__main__': unittest.main()
