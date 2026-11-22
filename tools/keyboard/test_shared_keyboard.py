"""Exercise actual generated Java dispatch and focus-search methods with view stubs.

Host-only tests do not prove Android device or IME behavior.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def method(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


class SharedKeyboard(unittest.TestCase):
    @unittest.skipUnless(shutil.which("javac") and shutil.which("java"), "JDK required; CI runs this test")
    def test_actual_dispatch_and_nested_surface_handoff(self):
        source = (ROOT / "templates/android/SafActivity.java").read_text()
        dispatch = method(source, "public boolean dispatchKeyEvent(KeyEvent event)")
        focus = method(source, "private boolean restoreCanvasKeyboardFocus(View node)")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            view = root / "android/view"
            view.mkdir(parents=True)
            (view / "View.java").write_text("package android.view; public class View { public boolean shown=true, focused=false; public boolean isShown(){return shown;} public void setFocusable(boolean v){} public void setFocusableInTouchMode(boolean v){} public boolean requestFocus(){focused=true;return true;} }")
            (view / "SurfaceView.java").write_text("package android.view; public class SurfaceView extends View {}")
            (view / "ViewGroup.java").write_text("package android.view; public class ViewGroup extends View { public View[] children; public ViewGroup(View...c){children=c;} public int getChildCount(){return children.length;} public View getChildAt(int i){return children[i];} }")
            harness = r"""
import android.view.*;
class KeyEvent {
 static final int KEYCODE_ESCAPE=111, ACTION_DOWN=0;
 int key, action, repeat; boolean modified;
 KeyEvent(int k,int a,int r,boolean m){key=k;action=a;repeat=r;modified=m;}
 int getKeyCode(){return key;} int getAction(){return action;}
 int getRepeatCount(){return repeat;} boolean hasNoModifiers(){return !modified;}
}
class Base { int forwarded; public boolean dispatchKeyEvent(KeyEvent e){forwarded++;return true;} }
public class Harness extends Base {
 boolean imeWanted=true; View imeView=new View(); int hides;
 void imeHide(){hides++;imeWanted=false;}
 DISPATCH
 FOCUS
 static void check(boolean ok){if(!ok)throw new AssertionError();}
 public static void main(String[] args){
   Harness h=new Harness();
   KeyEvent[] untouched={null,new KeyEvent(48,0,0,false),new KeyEvent(111,1,0,false),new KeyEvent(111,0,1,false),new KeyEvent(111,0,0,true)};
   for(KeyEvent e:untouched)check(h.dispatchKeyEvent(e));
   check(h.hides==0 && h.forwarded==5);
   check(h.dispatchKeyEvent(new KeyEvent(111,0,0,false)));
   check(h.hides==1 && h.forwarded==6);
   h.dispatchKeyEvent(new KeyEvent(111,0,0,false));check(h.hides==1);
   SurfaceView surface=new SurfaceView(); View wrong=new View();
   ViewGroup nested=new ViewGroup(wrong,new ViewGroup(h.imeView,surface));
   check(h.restoreCanvasKeyboardFocus(nested));
   check(surface.focused && !wrong.focused && !h.imeView.focused);
   SurfaceView hidden=new SurfaceView();hidden.shown=false;
   check(!h.restoreCanvasKeyboardFocus(new ViewGroup(hidden)) && !hidden.focused);
   check(!h.restoreCanvasKeyboardFocus(null));
 }
}
""".replace("DISPATCH", dispatch).replace("FOCUS", focus)
            (root / "Harness.java").write_text(harness)
            subprocess.run(["javac", "-d", tmp, *map(str, view.glob("*.java")), str(root / "Harness.java")], check=True)
            subprocess.run(["java", "-cp", tmp, "Harness"], check=True)

if __name__ == "__main__": unittest.main()
