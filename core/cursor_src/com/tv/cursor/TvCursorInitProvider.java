package com.tv.cursor;

import android.app.Application;
import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;

/**
 * Android ContentProvider that automatically initializes the Android TV
 * Desktop Mouse Cursor Engine at application startup before any Activity starts.
 */
public class TvCursorInitProvider extends ContentProvider {
    @Override
    public boolean onCreate() {
        try {
            Context context = getContext();
            if (context != null) {
                Context appCtx = context.getApplicationContext();
                if (appCtx instanceof Application) {
                    TvDesktopCursorOverlay.init((Application) appCtx);
                }
            }
        } catch (Throwable t) {
            android.util.Log.e("TvCursorInitProvider", "Failed to initialize TV cursor overlay (non-fatal): " + t.getMessage(), t);
        }
        return true;
    }

    @Override
    public Cursor query(Uri uri, String[] projection, String selection, String[] selectionArgs, String sortOrder) {
        return null;
    }

    @Override
    public String getType(Uri uri) {
        return null;
    }

    @Override
    public Uri insert(Uri uri, ContentValues values) {
        return null;
    }

    @Override
    public int delete(Uri uri, String selection, String[] selectionArgs) {
        return 0;
    }

    @Override
    public int update(Uri uri, ContentValues values, String selection, String[] selectionArgs) {
        return 0;
    }
}
