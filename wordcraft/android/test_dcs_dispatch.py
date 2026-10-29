"""Execute the generated Activity's real dispatch method with a host Java harness."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('javac'), 'JDK required; executed in Android CI')
class DispatchBehavior(unittest.TestCase):
    def test_modal_keys_own_complete_gesture_and_leave_ime_alone(self):
        generated = Path(__file__).with_name('WordCraftExtension.java.inc').read_text()
        start = generated.index('    private final java.util.concurrent.atomic.AtomicInteger')
        method = generated.index('    @Override public boolean dispatchKeyEvent')
        brace = generated.index('{', method)
        depth = 1
        end = brace + 1
        while depth:
            depth += (generated[end] == '{') - (generated[end] == '}')
            end += 1
        body = generated[start:end]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'android/view').mkdir(parents=True)
            (root/'android/view/KeyEvent.java').write_text('''package android.view;
public class KeyEvent {
 public static final int ACTION_DOWN=0,ACTION_UP=1,KEYCODE_D=32,KEYCODE_C=31,KEYCODE_S=47,KEYCODE_ESCAPE=111,FLAG_SOFT_KEYBOARD=2;
 int key,action,repeat,flags; boolean modified;
 public KeyEvent(int k,int a,int r,boolean m,int f){key=k;action=a;repeat=r;modified=m;flags=f;}
 public int getKeyCode(){return key;} public int getAction(){return action;}
 public int getRepeatCount(){return repeat;} public int getFlags(){return flags;}
 public boolean hasNoModifiers(){return !modified;} public boolean isSystem(){return false;}
}''')
            (root/'Harness.java').write_text('''import android.view.KeyEvent;
class Parent { int forwarded=0; public boolean dispatchKeyEvent(KeyEvent e){forwarded++;return false;}
 public boolean onKeyDown(int c,KeyEvent e){forwarded++;return false;} public boolean onKeyUp(int c,KeyEvent e){forwarded++;return false;} }
public class Harness extends Parent {
 boolean imeWanted=true; int hides=0; void imeHide(){hides++;imeWanted=false;} void artcraftRestoreCanvasFocus(){}
''' + body + '''
 static KeyEvent event(int k,int a,int r,boolean m,int f){return new KeyEvent(k,a,r,m,f);}
 static void check(boolean b){if(!b) throw new AssertionError();}
 public static void main(String[] args){
  Harness h=new Harness();
  h.dispatchKeyEvent(event(32,0,0,false,0)); check(h.forwarded==1); check(h.wcUnsavedDialog(true)==0);
  check(h.dispatchKeyEvent(event(32,0,0,false,0))); check(h.wcUnsavedDialog(true)==1);
  h.dispatchKeyEvent(event(32,0,1,false,0)); check(h.wcUnsavedDialog(true)==0);
  h.wcUnsavedDialog(false); h.dispatchKeyEvent(event(32,1,0,false,0)); check(h.forwarded==1);
  h.wcUnsavedDialog(true); h.dispatchKeyEvent(event(31,0,0,true,0)); check(h.forwarded==2); check(h.wcUnsavedDialog(true)==0);
  h.dispatchKeyEvent(event(47,0,0,false,2)); check(h.forwarded==3); check(h.wcUnsavedDialog(true)==0);
  h.dispatchKeyEvent(event(31,0,0,false,0)); check(h.wcUnsavedDialog(true)==2);
  h.dispatchKeyEvent(event(31,1,0,false,0)); h.dispatchKeyEvent(event(47,0,0,false,0)); check(h.wcUnsavedDialog(true)==3);
  check(h.imeWanted && h.hides==0);
 }
}''')
            subprocess.run(['javac','android/view/KeyEvent.java','Harness.java'],cwd=root,check=True,capture_output=True)
            subprocess.run(['java','-ea','Harness'],cwd=root,check=True,capture_output=True)
