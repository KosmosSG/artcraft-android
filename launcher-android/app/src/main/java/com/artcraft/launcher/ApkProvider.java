package com.artcraft.launcher;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.database.Cursor;
import android.net.Uri;
import android.os.Environment;
import android.os.ParcelFileDescriptor;
import java.io.File;
import java.io.FileNotFoundException;

/** Read-only content URI grant for a verified, app-owned downloaded APK. */
public final class ApkProvider extends ContentProvider {
    static final String AUTHORITY="com.artcraft.launcher.apks";
    @Override public boolean onCreate() { return true; }
    @Override public String getType(Uri uri) { return "application/vnd.android.package-archive"; }
    @Override public ParcelFileDescriptor openFile(Uri uri,String mode) throws FileNotFoundException {
        if(!"r".equals(mode) || !AUTHORITY.equals(uri.getAuthority()))
            throw new FileNotFoundException("Read-only APK URI");
        String name=uri.getLastPathSegment();
        if(name==null || !name.matches("ArtCraft-[A-Za-z0-9.-]+\\.apk"))
            throw new FileNotFoundException("Invalid APK filename");
        File folder=getContext().getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if(folder==null) throw new FileNotFoundException("No downloads directory");
        File apk=new File(folder,name);
        try {
            if(!apk.getCanonicalFile().getParentFile().equals(folder.getCanonicalFile()))
                throw new FileNotFoundException("Invalid APK path");
        } catch(java.io.IOException e) { throw new FileNotFoundException(e.getMessage()); }
        return ParcelFileDescriptor.open(apk,ParcelFileDescriptor.MODE_READ_ONLY);
    }
    @Override public Cursor query(Uri uri,String[] projection,String selection,String[] selectionArgs,String sortOrder) { return null; }
    @Override public Uri insert(Uri uri,ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri,String selection,String[] selectionArgs) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri,ContentValues values,String selection,String[] selectionArgs) { throw new UnsupportedOperationException(); }
}
