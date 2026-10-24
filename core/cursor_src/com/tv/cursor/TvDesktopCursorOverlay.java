package com.tv.cursor;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.content.pm.ActivityInfo;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.os.Bundle;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.view.ActionMode;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.Menu;
import android.view.MenuItem;
import android.view.MotionEvent;
import android.view.SearchEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewTreeObserver;
import android.view.Window;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.widget.FrameLayout;

/**
 * Universal Native Android TV Desktop Mouse Cursor Engine.
 * Injected at bytecode level to display an active desktop mouse pointer on 16:9 TV screens.
 * Intercepts TV Remote D-Pad & OK keys to move the pointer and dispatch real hardware touch events.
 * Enforces horizontal 16:9 orientation across smartphone apps (including Jetpack Compose & JioTV).
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
            public void onActivityCreated(Activity activity, Bundle savedInstanceState) {
                enforceLandscape(activity);
            }

            @Override
            public void onActivityStarted(Activity activity) {
                enforceLandscape(activity);
            }

            @Override
            public void onActivityResumed(Activity activity) {
                enforceLandscape(activity);
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

    private static void enforceLandscape(Activity activity) {
        if (activity == null) return;
        try {
            // Overrides hardcoded portrait calls from smartphone code (e.g. JioTV HomeActivity)
            activity.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE);
        } catch (Throwable ignored) {}
    }

    private static void attachCursorToActivity(final Activity activity) {
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
        pointerView.setFocusable(false);
        pointerView.setClickable(false);
        pointerView.setElevation(999999.0f);

        // Overlay layout is completely transparent to touch (never intercepts touch events)
        final FrameLayout overlayLayout = new FrameLayout(activity) {
            @Override
            public boolean onInterceptTouchEvent(MotionEvent ev) {
                return false;
            }

            @Override
            public boolean dispatchTouchEvent(MotionEvent ev) {
                return false; // Transparent: pass through to real app views below
            }
        };

        overlayLayout.setTag(TAG_CURSOR_OVERLAY);
        overlayLayout.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
        ));
        overlayLayout.setFocusable(false);
        overlayLayout.setClickable(false);
        overlayLayout.setClipChildren(false);
        overlayLayout.setClipToPadding(false);
        overlayLayout.setElevation(999999.0f);
        overlayLayout.addView(pointerView);

        // Center cursor initially on screen
        final float[] coords = new float[]{
            screenWidth > 0 ? screenWidth / 2.0f : 960.0f,
            screenHeight > 0 ? screenHeight / 2.0f : 540.0f
        };
        pointerView.setTranslationX(coords[0]);
        pointerView.setTranslationY(coords[1]);

        decorView.addView(overlayLayout);
        overlayLayout.bringToFront();

        // Keep overlay on top if views are dynamically added or layout changes
        try {
            decorView.getViewTreeObserver().addOnGlobalLayoutListener(new ViewTreeObserver.OnGlobalLayoutListener() {
                @Override
                public void onGlobalLayout() {
                    overlayLayout.bringToFront();
                }
            });
        } catch (Throwable ignored) {}

        // Wrap Window Callback for remote D-Pad & click interception
        final Window.Callback originalCallback = window.getCallback();
        window.setCallback(new Window.Callback() {
            private int mRepeatCount = 0;
            private long mDownTime = 0;
            private boolean mIsDragging = false;

            @Override
            public boolean dispatchKeyEvent(KeyEvent event) {
                int code = event.getKeyCode();
                int action = event.getAction();

                float curW = decorView.getWidth() > 0 ? (float)decorView.getWidth() : screenWidth;
                float curH = decorView.getHeight() > 0 ? (float)decorView.getHeight() : screenHeight;

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

                        coords[0] = Math.max(5.0f, Math.min(coords[0], curW - 15.0f));
                        coords[1] = Math.max(5.0f, Math.min(coords[1], curH - 15.0f));

                        pointerView.setTranslationX(coords[0]);
                        pointerView.setTranslationY(coords[1]);
                        overlayLayout.bringToFront();

                        // If user is holding OK while moving D-pad, dispatch drag/move!
                        if (mIsDragging) {
                            long now = SystemClock.uptimeMillis();
                            MotionEvent move = MotionEvent.obtain(mDownTime, now, MotionEvent.ACTION_MOVE, coords[0], coords[1], 0);
                            move.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                            decorView.dispatchTouchEvent(move);
                            move.recycle();
                        }
                    } else if (action == KeyEvent.ACTION_UP) {
                        mRepeatCount = 0;
                    }
                    return true; // Consume navigation so underlying view does not jump
                }

                // 2. D-Pad Center / Enter: Dispatch Real Touch Events At Cursor Coordinates
                if (code == KeyEvent.KEYCODE_DPAD_CENTER ||
                    code == KeyEvent.KEYCODE_ENTER ||
                    code == KeyEvent.KEYCODE_NUMPAD_ENTER) {

                    if (action == KeyEvent.ACTION_DOWN) {
                        mIsDragging = true;
                        pointerView.triggerClickAnimation();
                        long now = SystemClock.uptimeMillis();
                        mDownTime = now;
                        MotionEvent down = MotionEvent.obtain(now, now, MotionEvent.ACTION_DOWN, coords[0], coords[1], 0);
                        down.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                        decorView.dispatchTouchEvent(down);
                        down.recycle();
                    } else if (action == KeyEvent.ACTION_UP) {
                        mIsDragging = false;
                        long now = SystemClock.uptimeMillis();
                        long dt = mDownTime > 0 ? mDownTime : (now - 50);
                        MotionEvent up = MotionEvent.obtain(dt, now, MotionEvent.ACTION_UP, coords[0], coords[1], 0);
                        up.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                        decorView.dispatchTouchEvent(up);
                        up.recycle();
                        mDownTime = 0;
                    }
                    return true;
                }

                // 3. Fast Page / Channel Up & Down Scroll
                if (code == KeyEvent.KEYCODE_PAGE_DOWN || code == KeyEvent.KEYCODE_CHANNEL_DOWN) {
                    if (action == KeyEvent.ACTION_DOWN) {
                        simulateSwipe(decorView, curW / 2.0f, curH * 0.75f, curW / 2.0f, curH * 0.25f);
                    }
                    return true;
                }
                if (code == KeyEvent.KEYCODE_PAGE_UP || code == KeyEvent.KEYCODE_CHANNEL_UP) {
                    if (action == KeyEvent.ACTION_DOWN) {
                        simulateSwipe(decorView, curW / 2.0f, curH * 0.25f, curW / 2.0f, curH * 0.75f);
                    }
                    return true;
                }

                // Pass all other keys (BACK, VOLUME, MEDIA, etc.) to the app
                return originalCallback != null ? originalCallback.dispatchKeyEvent(event) : false;
            }

            @Override
            public boolean dispatchKeyShortcutEvent(KeyEvent event) {
                return originalCallback != null && originalCallback.dispatchKeyShortcutEvent(event);
            }

            @Override
            public boolean dispatchTouchEvent(MotionEvent event) {
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
    }

    private static void simulateSwipe(ViewGroup decorView, float startX, float startY, float endX, float endY) {
        try {
            long now = SystemClock.uptimeMillis();
            MotionEvent down = MotionEvent.obtain(now, now, MotionEvent.ACTION_DOWN, startX, startY, 0);
            down.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(down);
            down.recycle();

            long moveTime = now + 100;
            float midX = (startX + endX) / 2.0f;
            float midY = (startY + endY) / 2.0f;
            MotionEvent move = MotionEvent.obtain(now, moveTime, MotionEvent.ACTION_MOVE, midX, midY, 0);
            move.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(move);
            move.recycle();

            long upTime = now + 200;
            MotionEvent up = MotionEvent.obtain(now, upTime, MotionEvent.ACTION_UP, endX, endY, 0);
            up.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(up);
            up.recycle();
        } catch (Throwable ignored) {}
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
