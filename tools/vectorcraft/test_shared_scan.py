"""Exercise VectorCraft's actual scanner with a fake SAF provider on the JVM."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).parents[2]
JAVA=ROOT/'adapters/vectorcraft/java/com/artcraft/vectorcraft/VectorCraftExtras.java'

class SharedScan(unittest.TestCase):
    def test_partial_scan_merges_instead_of_rejecting(self):
        s=JAVA.read_text()
        self.assertNotIn('Incomplete shared font scan; previous fonts preserved',s)
        for token in ('MAX_FONTS = 5000','MAX_FOLDERS = 5000','MAX_FONT = 64L',
                      'MAX_SCAN_BYTES = 2L * 1024 * 1024 * 1024','fontDigest(file)',
                      'Previous fonts kept; refreshing font catalog', '"ttcf".equals(s)'):
            self.assertIn(token,s)

    @unittest.skipUnless(shutil.which('javac'),'JVM required in private CI')
    def test_bad_file_does_not_abort_valid_fonts_or_erase_previous_cache(self):
        s=JAVA.read_text()
        helpers=s[s.index('    private static String extension('):s.index('    private void importFont(')]
        scanner=s[s.index('    private void scanFontFolder('):s.index('    void checkForUpdates()')]
        harness=r'''
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
public class VectorScanTest {
 static final long MAX_FONT=64L*1024*1024,MAX_SCAN_BYTES=2L*1024*1024*1024;
 static final int MAX_FONTS=5000,MAX_FOLDERS=5000;
 static final String TAG="test";
 static class Log { static void w(String tag,String text) {} static void w(String tag,String text,Exception e) {} }
 static class Uri {
   String id; Uri(String id){this.id=id;}
   public boolean equals(Object o){return o instanceof Uri && ((Uri)o).id.equals(id);}
   public int hashCode(){return id.hashCode();}
 }
 static class android {static class content {static class UriPermission {
   Uri getUri(){return new Uri("root");} boolean isReadPermission(){return true;}
 }}}
 static class DocumentsContract {
   static class Document {static final String COLUMN_DOCUMENT_ID="id",COLUMN_DISPLAY_NAME="name",COLUMN_MIME_TYPE="mime",COLUMN_SIZE="size",MIME_TYPE_DIR="directory";}
   static String getTreeDocumentId(Uri u){return u.id;}
   static Uri buildChildDocumentsUriUsingTree(Uri t,String p){return new Uri(p);}
   static Uri buildDocumentUriUsingTree(Uri t,String p){return new Uri(p);}
 }
 static class Cursor implements AutoCloseable {
   List<String[]> rows; int pos=-1; Cursor(List<String[]> r){rows=r;}
   boolean moveToNext(){return ++pos<rows.size();}
   String getString(int i){return rows.get(pos)[i];}
   boolean isNull(int i){return rows.get(pos)[i]==null;}
   long getLong(int i){return Long.parseLong(getString(i));}
   public void close(){}
 }
 class Resolver {
   List<android.content.UriPermission> getPersistedUriPermissions(){return List.of(new android.content.UriPermission());}
   Cursor query(Uri uri,String[] fields,Object a,Object b,Object c){return new Cursor(nodes.getOrDefault(uri.id,List.of()));}
   InputStream openInputStream(Uri uri){return new ByteArrayInputStream(data.get(uri.id));}
 }
 class Activity {Resolver getContentResolver(){return new Resolver();}}
 final Activity activity=new Activity();
 final java.util.concurrent.Executor fontIo=Runnable::run;
 final File root;
 final Map<String,List<String[]>> nodes=new HashMap<>();
 final Map<String,byte[]> data=new HashMap<>();
 String status,message;int reported;
 VectorScanTest(File dir){root=dir;dir.mkdirs();}
 File files(){return root;}
 File fonts(){return new File(root,"Fonts");}
 void report(long id,String kind,String state,String text,int count){status=state;message=text;reported=count;}
 void add(String parent,String id,String name,boolean dir,boolean valid){
   nodes.computeIfAbsent(parent,k->new ArrayList<>()).add(new String[]{id,name,dir?"directory":"font","32"});
   byte[] bytes=new byte[32];if(valid){bytes[0]='t';bytes[1]='t';bytes[2]='c';bytes[3]='f';}data.put(id,bytes);
 }
 static void check(boolean ok){if(!ok)throw new AssertionError();}
 public static void main(String[] args)throws Exception{
   VectorScanTest t=new VectorScanTest(new File(args[0]));
   File shared=new File(t.fonts(),"Shared");shared.mkdirs();
   Path old=shared.toPath().resolve("previous.ttf");Files.write(old,new byte[]{1,2,3});
   t.add("root","nested","nested",true,false);
   t.add("nested","broken","broken.ttf",false,false);
   t.add("nested","good","good.TTC",false,true);
   t.scanFontFolder(1,new Uri("root"));
   check("ok".equals(t.status) && t.reported==1 && t.message.contains("skipped 1"));
   check(Files.exists(old) && shared.list().length==2);
   t.scanFontFolder(2,new Uri("root"));
   check("ok".equals(t.status) && t.reported==0 && shared.list().length==2);
   check(!Arrays.stream(t.root.list()).anyMatch(n->n.startsWith("pending-shared")));
   VectorScanTest many=new VectorScanTest(new File(args[0],"many"));
   for(int i=0;i<201;i++)many.add("root","font"+i,"font"+i+".ttf",false,true);
   many.scanFontFolder(3,new Uri("root"));
   check("ok".equals(many.status) && many.message.contains("201 font files"));
 }
'''
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'VectorScanTest.java';p.write_text(harness+helpers+scanner+'\n}')
            subprocess.run(['javac',str(p)],check=True,capture_output=True)
            subprocess.run(['java','-cp',folder,'VectorScanTest',str(Path(folder)/'cache')],check=True,capture_output=True)

if __name__=='__main__':unittest.main()
