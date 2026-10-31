"""Run the actual SAF walker with a fake document provider on a JVM."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

class RecursiveWalk(unittest.TestCase):
    @unittest.skipUnless(shutil.which('javac'), 'JVM coverage runs in private CI')
    def test_nested_folders_file_limit_folder_limit_and_expired_permission(self):
        src = Path(__file__).with_name('FontsBridge.java.inc').read_text()
        constants = src[src.index('    private static final long EC_FONT_MAX'):src.index('    private static final int EC_FONT_PICK')]
        scan = src[src.index('    private void ecRefreshSharedFonts(boolean manual)'):]
        harness = r'''
import java.io.*;
import java.util.*;
public class FontWalkTest {
 static final int MODE_PRIVATE=0;
 static class Uri {
   final String id;
   Uri(String id) { this.id=id; }
   static Uri parse(String id) { return new Uri(id); }
   public boolean equals(Object other) { return other instanceof Uri && ((Uri)other).id.equals(id); }
   public int hashCode() { return id.hashCode(); }
 }
 static class android { static class content { static class UriPermission {
   Uri getUri() { return Uri.parse("root"); }
   boolean isReadPermission() { return true; }
 } } }
 static class DocumentsContract {
   static class Document {
     static final String COLUMN_DOCUMENT_ID="id",COLUMN_DISPLAY_NAME="name",COLUMN_MIME_TYPE="mime",COLUMN_SIZE="size",MIME_TYPE_DIR="directory";
   }
   static String getTreeDocumentId(Uri uri) { return uri.id; }
   static Uri buildChildDocumentsUriUsingTree(Uri tree,String parent) { return new Uri(parent); }
   static Uri buildDocumentUriUsingTree(Uri tree,String id) { return new Uri(id); }
 }
 static class Cursor implements AutoCloseable {
   List<String[]> rows; int index=-1;
   Cursor(List<String[]> rows) { this.rows=rows; }
   boolean moveToNext() { return ++index < rows.size(); }
   String getString(int i) { return rows.get(index)[i]; }
   boolean isNull(int i) { return rows.get(index)[i] == null; }
   long getLong(int i) { return Long.parseLong(getString(i)); }
   public void close() { }
 }
 class Resolver {
   List<android.content.UriPermission> getPersistedUriPermissions() {
     return granted ? List.of(new android.content.UriPermission()) : List.of();
   }
   Cursor query(Uri uri, String[] fields, Object a,Object b,Object c) {
     queries++;
     return new Cursor(nodes.getOrDefault(uri.id,List.of()));
   }
 }
 static class Preferences { String getString(String key,String fallback) { return "root"; } }
 Preferences getSharedPreferences(String name,int mode) { return new Preferences(); }
 Resolver getContentResolver() { return new Resolver(); }
 Map<String,List<String[]>> nodes = new HashMap<>();
 int copies,queries; boolean granted=true;
 final java.util.concurrent.atomic.AtomicBoolean ecFontBusy = new java.util.concurrent.atomic.AtomicBoolean();
 final java.util.concurrent.ConcurrentLinkedQueue<String> ecFontPaths = new java.util.concurrent.ConcurrentLinkedQueue<>();
 final java.util.concurrent.Executor io = Runnable::run;
 void ecFontMessage(String text) { }
 void ecCopyFont(Uri uri,String name,long[] budget,boolean manual) { copies++; budget[0]+=32; }
 void add(String parent,String id,boolean folder) {
   nodes.computeIfAbsent(parent,k->new ArrayList<>()).add(new String[]{id,folder?id:id+".ttc",folder?"directory":"font","32"});
 }
 static void check(boolean ok) { if(!ok) throw new AssertionError(); }
 public static void main(String[] args) {
   FontWalkTest nested=new FontWalkTest(); String parent="root";
   for(int i=0;i<32;i++) { String child="folder"+i; nested.add(parent,child,true); parent=child; }
   nested.add(parent,"font",false); nested.ecRefreshSharedFonts(true);
   check(nested.copies==1 && nested.queries==33);
   check(nested.ecFontPaths.poll().contains("Detected 1"));
   FontWalkTest many=new FontWalkTest();
   for(int i=0;i<5001;i++) many.add("root","font"+i,false);
   many.ecRefreshSharedFonts(true);
   check(many.copies==5000 && many.ecFontPaths.poll().contains("scan limit reached"));
   FontWalkTest folders=new FontWalkTest();
   for(int i=0;i<6000;i++) folders.add("root","folder"+i,true);
   folders.ecRefreshSharedFonts(true);
   check(folders.queries<=5000 && folders.ecFontPaths.poll().contains("scan limit reached"));
   FontWalkTest expired=new FontWalkTest(); expired.granted=false; expired.ecRefreshSharedFonts(true);
   check(expired.copies==0 && expired.ecFontPaths.poll().contains("permission expired"));
 }
'''
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'FontWalkTest.java'
            p.write_text(harness+constants+scan+'\n}')
            subprocess.run(['javac', str(p)],check=True,capture_output=True)
            subprocess.run(['java','-cp',folder,'FontWalkTest'],check=True,capture_output=True)

if __name__ == '__main__':
    unittest.main()
