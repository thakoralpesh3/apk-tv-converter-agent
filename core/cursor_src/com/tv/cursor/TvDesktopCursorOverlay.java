package com.tv.cursor;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.view.ActionMode;
import android.view.KeyEvent;
import android.view.Menu;
import android.view.MenuItem;
import android.view.MotionEvent;
import android.view.SearchEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.FrameLayout;

/**
 * Universal Native Android TV Desktop Mouse Cursor Engine.
 * Injected at bytecode level to display an active desktop mouse pointer on 16:9 TV screens.
 * Intercepts TV Remote D-Pad & OK keys to move the pointer and dispatch real touch events.
 */
public class TvDesktopCursorOverlay {
    private static final String TAG_CURSOR_OVERLAY = "tv_desktop_cursor_overlay_tag";
    private static final float BASE_SPEED = 24.0f;
    private static boolean sInitialized = false;

    public static synchronized void init(Application application) {
        if (sInitialized || application == null) return;
        sInitialized = true;

        application.registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
            @Override
            public void onActivityCreated(Activity activity, Bundle savedInstanceState) {}

            @Override
            public void onActivityStarted(Activity activity) {}

            @Override
            public void onActivityResumed(Activity activity) {
                attachCursorToActivity(activity);
            }

            @Override
            public void onActivityPaused(Activity activity) {}

            @Override
            public void onActivityStopped(Activity activity) {}

            @Override
            public void onActivitySaveInstanceState(Activity activity, Bundle outState) {}

            @Override
            public void onActivityDestroyed(Activity activity) {}
        });
    }

    private static void attachCursorToActivity(final Activity activity) {
        try {
            if (activity == null || activity.isFinishing()) return;
            final Window window = activity.getWindow();
            if (window == null) return;

            final View decorViewRaw = window.getDecorView();
            if (!(decorViewRaw instanceof ViewGroup)) return;
            final ViewGroup decorView = (ViewGroup) decorViewRaw;

        // Check if overlay is already attached
        View existing = decorView.findViewWithTag(TAG_CURSOR_OVERLAY);
        if (existing != null) {
            existing.bringToFront();
            return;
        }

        DisplayMetrics dm = activity.getResources().getDisplayMetrics();
        final float screenWidth = dm.widthPixels;
        final float screenHeight = dm.heightPixels;

        final CursorPointerView pointerView = new CursorPointerView(activity);
        final FrameLayout overlayLayout = new FrameLayout(activity);
        overlayLayout.setTag(TAG_CURSOR_OVERLAY);
        overlayLayout.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        overlayLayout.setFocusable(false);
        overlayLayout.setClickable(false);
        overlayLayout.setClipChildren(false);
        overlayLayout.setClipToPadding(false);
        overlayLayout.addView(pointerView);

        // Center cursor initially on 16:9 widescreen
        final float[] coords = new float[]{screenWidth / 2.0f, screenHeight / 2.0f};
        pointerView.setTranslationX(coords[0]);
        pointerView.setTranslationY(coords[1]);

        decorView.addView(overlayLayout);
        overlayLayout.bringToFront();

        // Wrap Window Callback for remote D-Pad & click interception
        final Window.Callback originalCallback = window.getCallback();
        window.setCallback(new Window.Callback() {
            private int mRepeatCount = 0;
            private long mDownTime = 0;

            @Override
            public boolean dispatchKeyEvent(KeyEvent event) {
                int code = event.getKeyCode();
                int action = event.getAction();

                // 1. D-Pad Navigation: Move Desktop Cursor Pointer
                if (code == KeyEvent.KEYCODE_DPAD_UP ||
                    code == KeyEvent.KEYCODE_DPAD_DOWN ||
                    code == KeyEvent.KEYCODE_DPAD_LEFT ||
                    code == KeyEvent.KEYCODE_DPAD_RIGHT) {

                    if (action == KeyEvent.ACTION_DOWN) {
                        mRepeatCount = Math.min(mRepeatCount + 1, 10);
                        float speed = BASE_SPEED + (mRepeatCount * 4.0f);

                        if (code == KeyEvent.KEYCODE_DPAD_UP) coords[1] -= speed;
                        else if (code == KeyEvent.KEYCODE_DPAD_DOWN) coords[1] += speed;
                        else if (code == KeyEvent.KEYCODE_DPAD_LEFT) coords[0] -= speed;
                        else if (code == KeyEvent.KEYCODE_DPAD_RIGHT) coords[0] += speed;

                        coords[0] = Math.max(5.0f, Math.min(coords[0], screenWidth - 15.0f));
                        coords[1] = Math.max(5.0f, Math.min(coords[1], screenHeight - 15.0f));

                        pointerView.setTranslationX(coords[0]);
                        pointerView.setTranslationY(coords[1]);
                        overlayLayout.bringToFront();
                    } else if (action == KeyEvent.ACTION_UP) {
                        mRepeatCount = 0;
                    }
                    return true; // Consume navigation so underlying view does not jump
                }

                // 2. D-Pad Center / Enter: Dispatch Real MotionEvents At Cursor Coordinates
                if (code == KeyEvent.KEYCODE_DPAD_CENTER ||
                    code == KeyEvent.KEYCODE_ENTER ||
                    code == KeyEvent.KEYCODE_NUMPAD_ENTER) {

                    if (action == KeyEvent.ACTION_DOWN) {
                        pointerView.triggerClickAnimation();
                        long now = SystemClock.uptimeMillis();
                        mDownTime = now;
                        MotionEvent down = MotionEvent.obtain(now, now, MotionEvent.ACTION_DOWN, coords[0], coords[1], 0);
                        decorView.dispatchTouchEvent(down);
                        down.recycle();
                    } else if (action == KeyEvent.ACTION_UP) {
                        long now = SystemClock.uptimeMillis();
                        MotionEvent up = MotionEvent.obtain(mDownTime, now, MotionEvent.ACTION_UP, coords[0], coords[1], 0);
                        decorView.dispatchTouchEvent(up);
                        up.recycle();
                    }
                    return true;
                }

                return originalCallback != null ? originalCallback.dispatchKeyEvent(event) : false;
            }

            @Override
            public boolean dispatchKeyShortcutEvent(KeyEvent event) {
                return originalCallback != null && originalCallback.dispatchKeyShortcutEvent(event);
            }

            @Override
            public boolean dispatchTouchEvent(MotionEvent event) {
                // If a physical mouse or touch screen is used, track its position
                if (event.getAction() == MotionEvent.ACTION_DOWN || event.getAction() == MotionEvent.ACTION_MOVE) {
                    coords[0] = event.getX();
                    coords[1] = event.getY();
                    pointerView.setTranslationX(coords[0]);
                    pointerView.setTranslationY(coords[1]);
                }
                return originalCallback != null && originalCallback.dispatchTouchEvent(event);
            }

            @Override
            public boolean dispatchTrackballEvent(MotionEvent event) {
                return originalCallback != null && originalCallback.dispatchTrackballEvent(event);
            }

            @Override
            public boolean dispatchGenericMotionEvent(MotionEvent event) {
                if (event.getAction() == MotionEvent.ACTION_HOVER_MOVE) {
                    coords[0] = event.getX();
                    coords[1] = event.getY();
                    pointerView.setTranslationX(coords[0]);
                    pointerView.setTranslationY(coords[1]);
                }
                return originalCallback != null && originalCallback.dispatchGenericMotionEvent(event);
            }

            @Override
            public boolean dispatchPopulateAccessibilityEvent(AccessibilityEvent event) {
                return originalCallback != null && originalCallback.dispatchPopulateAccessibilityEvent(event);
            }

            @Override
            public View onCreatePanelView(int featureId) {
                return originalCallback != null ? originalCallback.onCreatePanelView(featureId) : null;
            }

            @Override
            public boolean onCreatePanelMenu(int featureId, Menu menu) {
                return originalCallback != null && originalCallback.onCreatePanelMenu(featureId, menu);
            }

            @Override
            public boolean onPreparePanel(int featureId, View view, Menu menu) {
                return originalCallback != null && originalCallback.onPreparePanel(featureId, view, menu);
            }

            @Override
            public boolean onMenuOpened(int featureId, Menu menu) {
                return originalCallback != null && originalCallback.onMenuOpened(featureId, menu);
            }

            @Override
            public boolean onMenuItemSelected(int featureId, MenuItem item) {
                return originalCallback != null && originalCallback.onMenuItemSelected(featureId, item);
            }

            @Override
            public void onWindowAttributesChanged(WindowManager.LayoutParams attrs) {
                if (originalCallback != null) originalCallback.onWindowAttributesChanged(attrs);
            }

            @Override
            public void onContentChanged() {
                if (originalCallback != null) originalCallback.onContentChanged();
            }

            @Override
            public void onWindowFocusChanged(boolean hasFocus) {
                if (originalCallback != null) originalCallback.onWindowFocusChanged(hasFocus);
            }

            @Override
            public void onAttachedToWindow() {
                if (originalCallback != null) originalCallback.onAttachedToWindow();
            }

            @Override
            public void onDetachedFromWindow() {
                if (originalCallback != null) originalCallback.onDetachedFromWindow();
            }

            @Override
            public void onPanelClosed(int featureId, Menu menu) {
                if (originalCallback != null) originalCallback.onPanelClosed(featureId, menu);
            }

            @Override
            public boolean onSearchRequested() {
                return originalCallback != null && originalCallback.onSearchRequested();
            }

            @Override
            public boolean onSearchRequested(SearchEvent searchEvent) {
                return originalCallback != null && originalCallback.onSearchRequested(searchEvent);
            }

            @Override
            public ActionMode onWindowStartingActionMode(ActionMode.Callback callback) {
                return originalCallback != null ? originalCallback.onWindowStartingActionMode(callback) : null;
            }

            @Override
            public ActionMode onWindowStartingActionMode(ActionMode.Callback callback, int type) {
                return originalCallback != null ? originalCallback.onWindowStartingActionMode(callback, type) : null;
            }

            @Override
            public void onActionModeStarted(ActionMode mode) {
                if (originalCallback != null) originalCallback.onActionModeStarted(mode);
            }

            @Override
            public void onActionModeFinished(ActionMode mode) {
                if (originalCallback != null) originalCallback.onActionModeFinished(mode);
            }
        });
        } catch (Throwable t) {
            android.util.Log.e("TvDesktopCursorOverlay", "Failed to attach cursor overlay to activity: " + t.getMessage(), t);
        }
    }

    /**
     * Standalone custom View that draws the classic desktop arrow mouse pointer
     * and animated cyan click ripple with zero external asset dependencies.
     */
    private static class CursorPointerView extends View {
        private final Paint mFillPaint;
        private final Paint mStrokePaint;
        private final Paint mShadowPaint;
        private final Paint mRipplePaint;
        private final Path mCursorPath;
        private float mRippleRadius = 0f;
        private float mRippleAlpha = 0f;

        public CursorPointerView(Context context) {
            super(context);
            setLayoutParams(new FrameLayout.LayoutParams(72, 72));

            mFillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
            mFillPaint.setStyle(Paint.Style.FILL);
            mFillPaint.setColor(Color.WHITE);

            mStrokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
            mStrokePaint.setStyle(Paint.Style.STROKE);
            mStrokePaint.setColor(Color.BLACK);
            mStrokePaint.setStrokeWidth(3.0f);
            mStrokePaint.setStrokeJoin(Paint.Join.ROUND);

            mShadowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
            mShadowPaint.setStyle(Paint.Style.FILL);
            mShadowPaint.setColor(Color.argb(120, 0, 0, 0));

            mRipplePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
            mRipplePaint.setStyle(Paint.Style.STROKE);
            mRipplePaint.setColor(Color.parseColor("#00E5FF"));
            mRipplePaint.setStrokeWidth(4.0f);

            // Canonical desktop arrow mouse pointer geometry
            mCursorPath = new Path();
            mCursorPath.moveTo(0f, 0f);
            mCursorPath.lineTo(0f, 32f);
            mCursorPath.lineTo(8f, 24f);
            mCursorPath.lineTo(14f, 36f);
            mCursorPath.lineTo(19f, 33.5f);
            mCursorPath.lineTo(13f, 21.5f);
            mCursorPath.lineTo(23f, 21.5f);
            mCursorPath.close();
        }

        public void triggerClickAnimation() {
            mRippleRadius = 4f;
            mRippleAlpha = 255f;
            postInvalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);

            // Draw expanding click ripple if active
            if (mRippleAlpha > 0) {
                mRipplePaint.setAlpha((int) mRippleAlpha);
                canvas.drawCircle(0, 0, mRippleRadius, mRipplePaint);
                mRippleRadius += 3.5f;
                mRippleAlpha = Math.max(0, mRippleAlpha - 25f);
                if (mRippleAlpha > 0) {
                    postInvalidateOnAnimation();
                }
            }

            // Draw Drop Shadow
            canvas.save();
            canvas.translate(2.5f, 3.5f);
            canvas.drawPath(mCursorPath, mShadowPaint);
            canvas.restore();

            // Draw Outer Black Border
            canvas.drawPath(mCursorPath, mStrokePaint);

            // Draw Inner White Pointer Body
            canvas.drawPath(mCursorPath, mFillPaint);
        }
    }
}
