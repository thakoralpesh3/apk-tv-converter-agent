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
import android.os.Handler;
import android.os.Looper;
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
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.lang.ref.WeakReference;

/**
 * Universal Native Android TV Desktop Mouse Cursor Engine.
 * Injected at bytecode level to display an active desktop mouse pointer on 16:9 TV screens.
 * Features:
 *  - Multi-channel click delivery (SOURCE_MOUSE, SOURCE_TOUCHSCREEN, direct performClick & focus)
 *  - Continuous focus synchronization (highlights TV elements under the cursor)
 *  - Self-healing Window.Callback interception (survives AppCompat / Compose / dynamic activity callbacks)
 *  - Dual-mode Mouse Toggle (Press MENU / PLAY_PAUSE to switch between Mouse Mode & D-Pad Mode)
 *  - Enforces horizontal 16:9 orientation across smartphone apps (including Jetpack Compose & JioTV)
 */
public class TvDesktopCursorOverlay {
    private static final String TAG_CURSOR_OVERLAY = "tv_desktop_cursor_overlay_tag";
    private static final float BASE_SPEED = 24.0f;
    private static boolean sInitialized = false;
    private static boolean sCursorEnabled = true;

    private static final Handler sMainHandler = new Handler(Looper.getMainLooper());

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

    public static void toggleCursorMode(Activity activity, CursorPointerView pointerView) {
        sCursorEnabled = !sCursorEnabled;
        if (pointerView != null) {
            pointerView.setVisibility(sCursorEnabled ? View.VISIBLE : View.GONE);
        }
        if (activity != null) {
            String msg = sCursorEnabled 
                    ? "Virtual Mouse Active (D-Pad Moves Cursor, OK Clicks)" 
                    : "TV Remote D-Pad Active (Direct Navigation)";
            try {
                Toast.makeText(activity.getApplicationContext(), msg, Toast.LENGTH_SHORT).show();
            } catch (Throwable ignored) {}
        }
    }

    private static boolean isConfirmKey(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_DPAD_CENTER ||
               keyCode == KeyEvent.KEYCODE_ENTER ||
               keyCode == KeyEvent.KEYCODE_NUMPAD_ENTER ||
               keyCode == KeyEvent.KEYCODE_BUTTON_A ||
               keyCode == KeyEvent.KEYCODE_BUTTON_SELECT ||
               keyCode == KeyEvent.KEYCODE_BUTTON_START ||
               keyCode == KeyEvent.KEYCODE_BUTTON_X;
    }

    private static boolean isNavKey(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_DPAD_UP ||
               keyCode == KeyEvent.KEYCODE_DPAD_DOWN ||
               keyCode == KeyEvent.KEYCODE_DPAD_LEFT ||
               keyCode == KeyEvent.KEYCODE_DPAD_RIGHT;
    }

    private static boolean isToggleKey(int keyCode) {
        return keyCode == KeyEvent.KEYCODE_MENU ||
               keyCode == KeyEvent.KEYCODE_INFO ||
               keyCode == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE ||
               keyCode == KeyEvent.KEYCODE_PROG_RED;
    }

    private static View findTopViewUnder(View view, float x, float y) {
        if (view == null || view.getVisibility() != View.VISIBLE) return null;
        if (TAG_CURSOR_OVERLAY.equals(view.getTag())) return null;

        int[] location = new int[2];
        view.getLocationOnScreen(location);
        int vx = location[0];
        int vy = location[1];
        int vw = view.getWidth();
        int vh = view.getHeight();

        if (x < vx || x >= vx + vw || y < vy || y >= vy + vh) {
            return null;
        }

        if (view instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) view;
            int childCount = group.getChildCount();
            for (int i = childCount - 1; i >= 0; i--) {
                View child = group.getChildAt(i);
                View hit = findTopViewUnder(child, x, y);
                if (hit != null) {
                    return hit;
                }
            }
        }
        return view;
    }

    private static View findClickableTarget(View view) {
        View curr = view;
        while (curr != null) {
            if (TAG_CURSOR_OVERLAY.equals(curr.getTag())) {
                return null;
            }
            if (curr.isClickable() || curr.isLongClickable() || curr.isFocusable() ||
                curr instanceof android.widget.Checkable ||
                curr instanceof android.widget.Button ||
                curr instanceof android.widget.ImageButton ||
                curr instanceof EditText) {
                return curr;
            }
            if (curr.getParent() instanceof View) {
                curr = (View) curr.getParent();
            } else {
                break;
            }
        }
        return view;
    }

    private static void syncFocusUnderPointer(ViewGroup decorView, float x, float y) {
        if (decorView == null) return;
        try {
            View hit = findTopViewUnder(decorView, x, y);
            if (hit != null) {
                View clickable = findClickableTarget(hit);
                if (clickable != null && clickable.isFocusable() && !clickable.isFocused()) {
                    clickable.requestFocus();
                }
            }
        } catch (Throwable ignored) {}
    }

    private static void performSmartClick(final Activity activity, final ViewGroup decorView, final CursorPointerView pointerView, final float x, final float y) {
        if (activity == null || decorView == null) return;

        if (pointerView != null) {
            pointerView.triggerClickAnimation();
        }

        // 1. Find View under pointer
        final View hitView = findTopViewUnder(decorView, x, y);
        final View clickable = (hitView != null) ? findClickableTarget(hitView) : null;

        // 2. Direct View Click execution if view found
        if (clickable != null) {
            try {
                clickable.requestFocus();
            } catch (Throwable ignored) {}

            try {
                clickable.performClick();
                clickable.sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_CLICKED);
            } catch (Throwable ignored) {}

            // If EditText, pop up soft keyboard
            if (clickable instanceof EditText) {
                try {
                    InputMethodManager imm = (InputMethodManager) activity.getSystemService(Context.INPUT_METHOD_SERVICE);
                    if (imm != null) {
                        imm.showSoftInput(clickable, InputMethodManager.SHOW_IMPLICIT);
                    }
                } catch (Throwable ignored) {}
            }
        }

        // 3. Multi-Channel Pointer & Touch Event Dispatch (For Jetpack Compose, WebView & Custom Canvas)
        final long downTime = SystemClock.uptimeMillis();
        final long upTime = downTime + 50;

        // Channel A: InputDevice.SOURCE_MOUSE (Standard Android TV pointer click)
        try {
            MotionEvent mousePress = MotionEvent.obtain(downTime, downTime, MotionEvent.ACTION_DOWN, x, y, 0);
            mousePress.setSource(InputDevice.SOURCE_MOUSE);
            decorView.dispatchTouchEvent(mousePress);

            MotionEvent mouseRelease = MotionEvent.obtain(downTime, upTime, MotionEvent.ACTION_UP, x, y, 0);
            mouseRelease.setSource(InputDevice.SOURCE_MOUSE);
            decorView.dispatchTouchEvent(mouseRelease);
        } catch (Throwable ignored) {}

        // Channel B: InputDevice.SOURCE_TOUCHSCREEN (Dispatched to decorView)
        try {
            MotionEvent touchDown = MotionEvent.obtain(downTime, downTime, MotionEvent.ACTION_DOWN, x, y, 0);
            touchDown.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(touchDown);

            MotionEvent touchUp = MotionEvent.obtain(downTime, upTime, MotionEvent.ACTION_UP, x, y, 0);
            touchUp.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(touchUp);
        } catch (Throwable ignored) {}

        // Channel C: Local coordinate SOURCE_TOUCHSCREEN directly to hitView (e.g. Compose AndroidComposeView)
        if (hitView != null && hitView != decorView) {
            try {
                int[] loc = new int[2];
                hitView.getLocationOnScreen(loc);
                float localX = x - loc[0];
                float localY = y - loc[1];

                MotionEvent localDown = MotionEvent.obtain(downTime, downTime, MotionEvent.ACTION_DOWN, localX, localY, 0);
                localDown.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                hitView.dispatchTouchEvent(localDown);

                MotionEvent localUp = MotionEvent.obtain(downTime, upTime, MotionEvent.ACTION_UP, localX, localY, 0);
                localUp.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                hitView.dispatchTouchEvent(localUp);
            } catch (Throwable ignored) {}
        }
    }

    private static void attachCursorToActivity(final Activity activity) {
        if (activity == null || activity.isFinishing()) return;
        final Window window = activity.getWindow();
        if (window == null) return;

        final View decorViewRaw = window.getDecorView();
        if (!(decorViewRaw instanceof ViewGroup)) return;
        final ViewGroup decorView = (ViewGroup) decorViewRaw;

        DisplayMetrics dm = activity.getResources().getDisplayMetrics();
        final float screenWidth = dm.widthPixels;
        final float screenHeight = dm.heightPixels;

        // Check if overlay is already attached
        FrameLayout existing = (FrameLayout) decorView.findViewWithTag(TAG_CURSOR_OVERLAY);
        final FrameLayout overlayLayout;
        final CursorPointerView pointerView;
        final float[] coords;

        if (existing != null) {
            overlayLayout = existing;
            pointerView = (CursorPointerView) overlayLayout.getChildAt(0);
            coords = new float[]{ pointerView.getTranslationX(), pointerView.getTranslationY() };
            overlayLayout.bringToFront();
        } else {
            pointerView = new CursorPointerView(activity);
            pointerView.setFocusable(false);
            pointerView.setClickable(false);
            pointerView.setElevation(999999.0f);

            // Overlay layout is completely transparent to touch
            overlayLayout = new FrameLayout(activity) {
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
            coords = new float[]{
                screenWidth > 0 ? screenWidth / 2.0f : 960.0f,
                screenHeight > 0 ? screenHeight / 2.0f : 540.0f
            };
            pointerView.setTranslationX(coords[0]);
            pointerView.setTranslationY(coords[1]);

            decorView.addView(overlayLayout);
            overlayLayout.bringToFront();

            try {
                decorView.getViewTreeObserver().addOnGlobalLayoutListener(new ViewTreeObserver.OnGlobalLayoutListener() {
                    @Override
                    public void onGlobalLayout() {
                        overlayLayout.bringToFront();
                    }
                });
            } catch (Throwable ignored) {}
        }

        // Install Self-Healing Window.Callback
        ensureCallbackAttached(activity, window, decorView, pointerView, overlayLayout, coords, screenWidth, screenHeight);
    }

    private static void ensureCallbackAttached(
            final Activity activity,
            final Window window,
            final ViewGroup decorView,
            final CursorPointerView pointerView,
            final FrameLayout overlayLayout,
            final float[] coords,
            final float screenWidth,
            final float screenHeight
    ) {
        Window.Callback current = window.getCallback();
        if (current instanceof TvWindowCallbackWrapper) {
            return; // Already wrapped
        }

        TvWindowCallbackWrapper wrapper = new TvWindowCallbackWrapper(
                current, activity, window, decorView, pointerView, overlayLayout, coords, screenWidth, screenHeight
        );
        window.setCallback(wrapper);

        // Schedule periodic self-healing watchdog check
        sMainHandler.postDelayed(new Runnable() {
            @Override
            public void run() {
                if (!activity.isFinishing()) {
                    Window.Callback cb = window.getCallback();
                    if (!(cb instanceof TvWindowCallbackWrapper)) {
                        window.setCallback(new TvWindowCallbackWrapper(
                                cb, activity, window, decorView, pointerView, overlayLayout, coords, screenWidth, screenHeight
                        ));
                    }
                    sMainHandler.postDelayed(this, 1000);
                }
            }
        }, 1000);
    }

    private static void simulateSwipe(ViewGroup decorView, float startX, float startY, float endX, float endY) {
        try {
            long now = SystemClock.uptimeMillis();
            MotionEvent down = MotionEvent.obtain(now, now, MotionEvent.ACTION_DOWN, startX, startY, 0);
            down.setSource(InputDevice.SOURCE_MOUSE);
            decorView.dispatchTouchEvent(down);

            long moveTime = now + 100;
            float midX = (startX + endX) / 2.0f;
            float midY = (startY + endY) / 2.0f;
            MotionEvent move = MotionEvent.obtain(now, moveTime, MotionEvent.ACTION_MOVE, midX, midY, 0);
            move.setSource(InputDevice.SOURCE_MOUSE);
            decorView.dispatchTouchEvent(move);

            long upTime = now + 200;
            MotionEvent up = MotionEvent.obtain(now, upTime, MotionEvent.ACTION_UP, endX, endY, 0);
            up.setSource(InputDevice.SOURCE_MOUSE);
            decorView.dispatchTouchEvent(up);
        } catch (Throwable ignored) {}
    }

    /**
     * Self-healing Window.Callback wrapper that intercepts TV remote D-Pad, OK, and Toggle keys.
     */
    private static class TvWindowCallbackWrapper implements Window.Callback {
        private final Window.Callback mOriginal;
        private final WeakReference<Activity> mActivityRef;
        private final Window mWindow;
        private final ViewGroup mDecorView;
        private final CursorPointerView mPointerView;
        private final FrameLayout mOverlayLayout;
        private final float[] mCoords;
        private final float mScreenWidth;
        private final float mScreenHeight;

        private int mRepeatCount = 0;
        private long mDownTime = 0;
        private boolean mIsDragging = false;

        public TvWindowCallbackWrapper(
                Window.Callback original,
                Activity activity,
                Window window,
                ViewGroup decorView,
                CursorPointerView pointerView,
                FrameLayout overlayLayout,
                float[] coords,
                float screenWidth,
                float screenHeight
        ) {
            this.mOriginal = original;
            this.mActivityRef = new WeakReference<>(activity);
            this.mWindow = window;
            this.mDecorView = decorView;
            this.mPointerView = pointerView;
            this.mOverlayLayout = overlayLayout;
            this.mCoords = coords;
            this.mScreenWidth = screenWidth;
            this.mScreenHeight = screenHeight;
        }

        @Override
        public boolean dispatchKeyEvent(KeyEvent event) {
            int code = event.getKeyCode();
            int action = event.getAction();
            Activity activity = mActivityRef.get();

            // 0. Toggle Mouse Mode / D-Pad Mode on Menu, Play/Pause, or Info key
            if (isToggleKey(code) && action == KeyEvent.ACTION_DOWN) {
                toggleCursorMode(activity, mPointerView);
                return true;
            }

            // If user has toggled cursor OFF, pass all keys directly to native Android TV app
            if (!sCursorEnabled) {
                return mOriginal != null && mOriginal.dispatchKeyEvent(event);
            }

            float curW = mDecorView.getWidth() > 0 ? (float) mDecorView.getWidth() : mScreenWidth;
            float curH = mDecorView.getHeight() > 0 ? (float) mDecorView.getHeight() : mScreenHeight;

            // 1. D-Pad Navigation: Move Desktop Cursor Pointer
            if (isNavKey(code)) {
                if (action == KeyEvent.ACTION_DOWN) {
                    mRepeatCount = Math.min(mRepeatCount + 1, 10);
                    float speed = BASE_SPEED + (mRepeatCount * 4.0f);

                    if (code == KeyEvent.KEYCODE_DPAD_UP) mCoords[1] -= speed;
                    else if (code == KeyEvent.KEYCODE_DPAD_DOWN) mCoords[1] += speed;
                    else if (code == KeyEvent.KEYCODE_DPAD_LEFT) mCoords[0] -= speed;
                    else if (code == KeyEvent.KEYCODE_DPAD_RIGHT) mCoords[0] += speed;

                    mCoords[0] = Math.max(5.0f, Math.min(mCoords[0], curW - 15.0f));
                    mCoords[1] = Math.max(5.0f, Math.min(mCoords[1], curH - 15.0f));

                    mPointerView.setTranslationX(mCoords[0]);
                    mPointerView.setTranslationY(mCoords[1]);
                    mOverlayLayout.bringToFront();

                    // Synchronize Android TV focus marker to view under cursor
                    syncFocusUnderPointer(mDecorView, mCoords[0], mCoords[1]);

                    // If user is holding OK while moving D-pad, dispatch drag/move!
                    if (mIsDragging) {
                        long now = SystemClock.uptimeMillis();
                        MotionEvent move = MotionEvent.obtain(mDownTime, now, MotionEvent.ACTION_MOVE, mCoords[0], mCoords[1], 0);
                        move.setSource(InputDevice.SOURCE_MOUSE);
                        mDecorView.dispatchTouchEvent(move);
                    }
                } else if (action == KeyEvent.ACTION_UP) {
                    mRepeatCount = 0;
                }
                return true; // Consume navigation so cursor moves smoothly
            }

            // 2. D-Pad Center / Enter / Button A: Dispatch Multi-Channel Smart Click
            if (isConfirmKey(code)) {
                if (action == KeyEvent.ACTION_DOWN) {
                    mIsDragging = true;
                    // Only click on initial press (prevent cancelAndClearTouchTargets from key repeat)
                    if (event.getRepeatCount() == 0) {
                        mDownTime = SystemClock.uptimeMillis();
                        performSmartClick(activity, mDecorView, mPointerView, mCoords[0], mCoords[1]);
                    }
                } else if (action == KeyEvent.ACTION_UP) {
                    mIsDragging = false;
                    mDownTime = 0;
                }
                return true;
            }

            // 3. Fast Page / Channel Up & Down Scroll
            if (code == KeyEvent.KEYCODE_PAGE_DOWN || code == KeyEvent.KEYCODE_CHANNEL_DOWN) {
                if (action == KeyEvent.ACTION_DOWN) {
                    simulateSwipe(mDecorView, curW / 2.0f, curH * 0.75f, curW / 2.0f, curH * 0.25f);
                }
                return true;
            }
            if (code == KeyEvent.KEYCODE_PAGE_UP || code == KeyEvent.KEYCODE_CHANNEL_UP) {
                if (action == KeyEvent.ACTION_DOWN) {
                    simulateSwipe(mDecorView, curW / 2.0f, curH * 0.25f, curW / 2.0f, curH * 0.75f);
                }
                return true;
            }

            // Pass all other keys (BACK, VOLUME, HOME, etc.) to the app
            return mOriginal != null ? mOriginal.dispatchKeyEvent(event) : false;
        }

        @Override
        public boolean dispatchKeyShortcutEvent(KeyEvent event) {
            return mOriginal != null && mOriginal.dispatchKeyShortcutEvent(event);
        }

        @Override
        public boolean dispatchTouchEvent(MotionEvent event) {
            if (event.getAction() == MotionEvent.ACTION_DOWN || event.getAction() == MotionEvent.ACTION_MOVE) {
                mCoords[0] = event.getX();
                mCoords[1] = event.getY();
                mPointerView.setTranslationX(mCoords[0]);
                mPointerView.setTranslationY(mCoords[1]);
            }
            return mOriginal != null && mOriginal.dispatchTouchEvent(event);
        }

        @Override
        public boolean dispatchTrackballEvent(MotionEvent event) {
            return mOriginal != null && mOriginal.dispatchTrackballEvent(event);
        }

        @Override
        public boolean dispatchGenericMotionEvent(MotionEvent event) {
            if (event.getAction() == MotionEvent.ACTION_HOVER_MOVE) {
                mCoords[0] = event.getX();
                mCoords[1] = event.getY();
                mPointerView.setTranslationX(mCoords[0]);
                mPointerView.setTranslationY(mCoords[1]);
            }
            return mOriginal != null && mOriginal.dispatchGenericMotionEvent(event);
        }

        @Override
        public boolean dispatchPopulateAccessibilityEvent(AccessibilityEvent event) {
            return mOriginal != null && mOriginal.dispatchPopulateAccessibilityEvent(event);
        }

        @Override
        public View onCreatePanelView(int featureId) {
            return mOriginal != null ? mOriginal.onCreatePanelView(featureId) : null;
        }

        @Override
        public boolean onCreatePanelMenu(int featureId, Menu menu) {
            return mOriginal != null && mOriginal.onCreatePanelMenu(featureId, menu);
        }

        @Override
        public boolean onPreparePanel(int featureId, View view, Menu menu) {
            return mOriginal != null && mOriginal.onPreparePanel(featureId, view, menu);
        }

        @Override
        public boolean onMenuOpened(int featureId, Menu menu) {
            return mOriginal != null && mOriginal.onMenuOpened(featureId, menu);
        }

        @Override
        public boolean onMenuItemSelected(int featureId, MenuItem item) {
            return mOriginal != null && mOriginal.onMenuItemSelected(featureId, item);
        }

        @Override
        public void onWindowAttributesChanged(WindowManager.LayoutParams attrs) {
            if (mOriginal != null) mOriginal.onWindowAttributesChanged(attrs);
        }

        @Override
        public void onContentChanged() {
            if (mOriginal != null) mOriginal.onContentChanged();
        }

        @Override
        public void onWindowFocusChanged(boolean hasFocus) {
            if (mOriginal != null) mOriginal.onWindowFocusChanged(hasFocus);
        }

        @Override
        public void onAttachedToWindow() {
            if (mOriginal != null) mOriginal.onAttachedToWindow();
        }

        @Override
        public void onDetachedFromWindow() {
            if (mOriginal != null) mOriginal.onDetachedFromWindow();
        }

        @Override
        public void onPanelClosed(int featureId, Menu menu) {
            if (mOriginal != null) mOriginal.onPanelClosed(featureId, menu);
        }

        @Override
        public boolean onSearchRequested() {
            return mOriginal != null && mOriginal.onSearchRequested();
        }

        @Override
        public boolean onSearchRequested(SearchEvent searchEvent) {
            return mOriginal != null && mOriginal.onSearchRequested(searchEvent);
        }

        @Override
        public ActionMode onWindowStartingActionMode(ActionMode.Callback callback) {
            return mOriginal != null ? mOriginal.onWindowStartingActionMode(callback) : null;
        }

        @Override
        public ActionMode onWindowStartingActionMode(ActionMode.Callback callback, int type) {
            return mOriginal != null ? mOriginal.onWindowStartingActionMode(callback, type) : null;
        }

        @Override
        public void onActionModeStarted(ActionMode mode) {
            if (mOriginal != null) mOriginal.onActionModeStarted(mode);
        }

        @Override
        public void onActionModeFinished(ActionMode mode) {
            if (mOriginal != null) mOriginal.onActionModeFinished(mode);
        }
    }

    /**
     * Standalone custom View that draws the classic desktop arrow mouse pointer
     * and animated cyan click ripple with zero external asset dependencies.
     */
    public static class CursorPointerView extends View {
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
                mRippleRadius += 4.0f;
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
