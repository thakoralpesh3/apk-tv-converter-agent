package com.tv.cursor;

import android.app.Activity;
import android.app.Application;
import android.app.Dialog;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.SharedPreferences;
import android.content.pm.ActivityInfo;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.os.Build;
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
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;

/**
 * Universal Native Android TV Desktop Mouse Cursor Engine.
 * Features:
 *  - Persistent Multi-Window & Dialog Event Interception via WindowManagerGlobal & OnKeyListeners
 *  - Dynamic Floating Overlay: auto-attaches to topmost visible window or modal dialog
 *  - Unbreakable continuous cursor movement & interaction across all screens, activities, dialogs
 *  - Cross-Activity & Cross-Window Shared State (never resets during activity transitions)
 *  - Native Touch-Event Lifecycle (Accurate DOWN -> MOVE -> UP with human press duration)
 *  - Full Jetpack Compose & Android View interaction (single clean channel, zero cancellation)
 *  - Hold-to-drag scrolling & scrub bar seek navigation
 *  - Dual-mode Mouse Toggle (Press MENU / PLAY_PAUSE to switch between Mouse Mode & D-Pad Mode)
 *  - Built-in Smartphone Compatibility & Auto-Bypass for JioTV & streaming apps
 */
public class TvDesktopCursorOverlay {
    private static final String TAG_CURSOR_OVERLAY = "tv_desktop_cursor_overlay_tag";
    private static final float BASE_SPEED = 26.0f;
    private static boolean sInitialized = false;
    private static boolean sCursorEnabled = true;

    private static final Handler sMainHandler = new Handler(Looper.getMainLooper());
    private static Application sApplication;
    private static WeakReference<Activity> sCurrentActivityRef = new WeakReference<>(null);
    private static final CopyOnWriteArrayList<WeakReference<Activity>> sActiveActivities = new CopyOnWriteArrayList<>();

    // Global unified cursor coordinates & screen boundaries
    private static final float[] sCoords = new float[]{ 960.0f, 540.0f };
    private static float sScreenWidth = 1920.0f;
    private static float sScreenHeight = 1080.0f;

    // Active cursor views
    private static CursorPointerView sPointerView;
    private static FrameLayout sOverlayLayout;
    private static WeakReference<ViewGroup> sAttachedDecorRef = new WeakReference<>(null);

    // Interaction state
    private static int sRepeatCount = 0;
    private static boolean sIsPointerDown = false;
    private static long sDownTime = 0;
    private static float sDownX = 0;
    private static float sDownY = 0;
    private static boolean sHasDragged = false;

    // Deduplication state for key events intercepted across Window.Callback and View.OnKeyListener
    private static long sLastHandledEventTime = -1;
    private static int sLastHandledCode = -1;
    private static int sLastHandledAction = -1;

    // Self-healing continuous heartbeat (runs every 100ms)
    private static final Runnable sHeartbeatRunnable = new Runnable() {
        @Override
        public void run() {
            try {
                ensureAllWindowCallbacksWrapped();
                ensureOverlayAttachedToTopmost();
            } catch (Throwable ignored) {}
            sMainHandler.postDelayed(this, 100);
        }
    };

    public static synchronized void init(Application application) {
        if (sInitialized || application == null) return;
        sInitialized = true;
        sApplication = application;

        // 1. Proactively exempt Android hidden API restrictions for Android 9 - 15
        exemptHiddenApiRestrictions();

        // 2. Proactively disable app security/debug restrictions (e.g. JioTV SecurityUtils)
        bypassAppSecurityRestrictions();

        // 3. Pre-seed preferences to suppress mobile onboarding popups & modal blocks
        preSeedAppSettings(application);

        // 4. Start continuous multi-window heartbeat
        sMainHandler.post(sHeartbeatRunnable);

        // 5. Register lifecycle listener to track active activities & orientation
        application.registerActivityLifecycleCallbacks(new Application.ActivityLifecycleCallbacks() {
            @Override
            public void onActivityCreated(Activity activity, Bundle savedInstanceState) {
                sActiveActivities.add(new WeakReference<>(activity));
                sCurrentActivityRef = new WeakReference<>(activity);
                enforceLandscape(activity);
                preSeedAppSettings(activity);
                handleSpecialAppStartup(activity);
                sMainHandler.post(new Runnable() {
                    @Override
                    public void run() {
                        ensureAllWindowCallbacksWrapped();
                        ensureOverlayAttachedToTopmost();
                    }
                });
            }

            @Override
            public void onActivityStarted(Activity activity) {
                sCurrentActivityRef = new WeakReference<>(activity);
                enforceLandscape(activity);
                ensureAllWindowCallbacksWrapped();
                ensureOverlayAttachedToTopmost();
            }

            @Override
            public void onActivityResumed(Activity activity) {
                sCurrentActivityRef = new WeakReference<>(activity);
                enforceLandscape(activity);
                ensureAllWindowCallbacksWrapped();
                ensureOverlayAttachedToTopmost();
                handleSpecialAppStartup(activity);
            }

            @Override
            public void onActivityPaused(Activity activity) {}

            @Override
            public void onActivityStopped(Activity activity) {}

            @Override
            public void onActivitySaveInstanceState(Activity activity, Bundle outState) {}

            @Override
            public void onActivityDestroyed(Activity activity) {
                for (WeakReference<Activity> ref : sActiveActivities) {
                    if (ref.get() == activity || ref.get() == null) {
                        sActiveActivities.remove(ref);
                    }
                }
                if (sCurrentActivityRef.get() == activity) {
                    Activity next = getTopmostActivity();
                    if (next != null) {
                        sCurrentActivityRef = new WeakReference<>(next);
                    } else {
                        ViewGroup nextTop = getTopmostDecorView();
                        Activity fromCtx = nextTop != null ? getActivityFromContext(nextTop.getContext()) : null;
                        sCurrentActivityRef = new WeakReference<>(fromCtx);
                    }
                }
            }
        });
    }

    /**
     * Bypasses Android 9+ hidden API restrictions using VMRuntime.setHiddenApiExemptions.
     * Guarantees reflection on DecorView.mWindow and WindowManagerGlobal works on Android 9 through 15.
     */
    private static void exemptHiddenApiRestrictions() {
        if (Build.VERSION.SDK_INT >= 28) {
            try {
                Method getDeclaredMethod = Class.class.getDeclaredMethod("getDeclaredMethod", String.class, Class[].class);
                Class<?> vmRuntimeClass = Class.forName("dalvik.system.VMRuntime");
                Method getRuntime = (Method) getDeclaredMethod.invoke(vmRuntimeClass, "getRuntime", null);
                Object vmRuntime = getRuntime.invoke(null);
                Method setHiddenApiExemptions = (Method) getDeclaredMethod.invoke(vmRuntimeClass, "setHiddenApiExemptions", new Class[]{String[].class});
                setHiddenApiExemptions.invoke(vmRuntime, new Object[]{new String[]{"L"}});
            } catch (Throwable ignored) {}
        }
    }

    private static void bypassAppSecurityRestrictions() {
        try {
            Class<?> secClass = Class.forName("com.jio.jioplay.tv.utils.SecurityUtils");
            Field isDebugField = secClass.getDeclaredField("isDebug");
            isDebugField.setAccessible(true);
            isDebugField.setBoolean(null, true);
        } catch (Throwable ignored) {}
    }

    public static Activity getActivityFromContext(Context ctx) {
        while (ctx instanceof ContextWrapper) {
            if (ctx instanceof Activity) return (Activity) ctx;
            ctx = ((ContextWrapper) ctx).getBaseContext();
        }
        return null;
    }

    public static Activity getTopmostActivity() {
        for (int i = sActiveActivities.size() - 1; i >= 0; i--) {
            WeakReference<Activity> ref = sActiveActivities.get(i);
            Activity a = ref.get();
            if (a != null && !a.isFinishing() && !a.isDestroyed()) {
                return a;
            }
        }
        return null;
    }

    private static void preSeedAppSettings(Context context) {
        if (context == null) return;
        try {
            // 1. JioTV Default Launch Screen popup suppression
            SharedPreferences pDefault = context.getSharedPreferences("DEFAULT_LAUNCH", 0);
            pDefault.edit()
                .putBoolean("dialogShown", true)
                .putBoolean("default_launch", true)
                .apply();

            // 2. JioTV General Preferences (language onboarding & aspect ratio popups)
            SharedPreferences pGeneral = context.getSharedPreferences("GENERAL", 0);
            pGeneral.edit()
                .putBoolean("dialogShown", true)
                .putBoolean("default_launch", true)
                .putString("userLangPref", "All")
                .putString("user_lang_pref", "All")
                .putBoolean("isLanguageOnBoardingEnabled", false)
                .putBoolean("IS_ASPECT_RATIO_LAYOUT_VISIBLE", false)
                .apply();

            // 3. HomeActivity specific prefs
            SharedPreferences pHome = context.getSharedPreferences("com.jio.jioplay.tv.activities.HomeActivity", 0);
            pHome.edit().putBoolean("dialogShown", true).apply();

            // 4. Generic shared prefs fallback
            SharedPreferences pShared = context.getSharedPreferences("shared_preference", 0);
            pShared.edit()
                .putBoolean("dialogShown", true)
                .putBoolean("default_launch", true)
                .putBoolean("isLanguageOnBoardingEnabled", false)
                .apply();

            // 5. User pref
            SharedPreferences pUser = context.getSharedPreferences("user_pref", 0);
            pUser.edit().putBoolean("isLanguageSelected", true).apply();
        } catch (Throwable ignored) {}
    }

    private static void handleSpecialAppStartup(final Activity activity) {
        if (activity == null || activity.isFinishing()) return;
        String name = activity.getClass().getName();
        preSeedAppSettings(activity);

        // 1. JioTV Permission / Splash Auto-Progression
        if (name.contains("PermissionActivity")) {
            sMainHandler.postDelayed(new Runnable() {
                @Override
                public void run() {
                    if (activity.isFinishing()) return;
                    try {
                        // Dismiss security warning / unsupported device dialog if shown
                        ViewGroup top = getTopmostDecorView();
                        if (top != null && top != activity.getWindow().peekDecorView()) {
                            dismissDialogIfPresent(top);
                        }

                        // Invoke proceedApplication to bypass blocks and start HomeActivity
                        Method proceedMethod = activity.getClass().getDeclaredMethod("proceedApplication");
                        proceedMethod.setAccessible(true);
                        proceedMethod.invoke(activity);
                    } catch (Throwable ignored) {}
                }
            }, 300);
        }

        // 2. JioTV HomeActivity Onboarding, Language Selection & Modal Dialog Auto-Handling
        if (name.contains("HomeActivity")) {
            // Auto-dismiss or confirm any startup onboarding dialogs (e.g. DefaultLaunchDialog, LanguageOnBoardingDialog, DarkMode popup)
            for (int delay : new int[]{ 250, 600, 1100, 1800, 2800, 4200 }) {
                sMainHandler.postDelayed(new Runnable() {
                    @Override
                    public void run() {
                        if (activity.isFinishing()) return;
                        try {
                            ViewGroup top = getTopmostDecorView();
                            if (top != null && top != activity.getWindow().peekDecorView()) {
                                autoConfirmDialog(top, activity);
                            }
                        } catch (Throwable ignored) {}
                    }
                }, delay);
            }
        }
    }

    private static void autoConfirmDialog(ViewGroup top, Activity activity) {
        if (top == null) return;
        String pkg = activity != null ? activity.getPackageName() : "com.jio.jioplay.tv";

        // Clickable confirmation button identifiers across TV streaming apps
        String[] buttonIds = new String[]{
            "confirmBtnId", "btn_continue", "btn_save", "no_thanks",
            "btnDialogPositive", "btnPositive", "button1", "ok"
        };
        for (String idName : buttonIds) {
            int id = activity != null ? activity.getResources().getIdentifier(idName, "id", pkg) : 0;
            if (id != 0) {
                View btn = top.findViewById(id);
                if (btn != null && btn.isClickable()) {
                    btn.performClick();
                    return;
                }
            }
        }
    }

    private static void dismissDialogIfPresent(ViewGroup top) {
        if (top == null) return;
        try {
            Window w = getWindowFromView(top);
            if (w != null && w.getCallback() instanceof Dialog) {
                ((Dialog) w.getCallback()).dismiss();
            }
        } catch (Throwable ignored) {}
    }

    private static void enforceLandscape(Activity activity) {
        if (activity == null) return;
        try {
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

    /**
     * Resolves the list of all active window roots in the process using WindowManagerGlobal.
     */
    public static List<View> getAllWindowViews() {
        try {
            Class<?> wmgClass = Class.forName("android.view.WindowManagerGlobal");
            Method getInstance = wmgClass.getMethod("getInstance");
            Object wmg = getInstance.invoke(null);
            Field viewsField = wmgClass.getDeclaredField("mViews");
            viewsField.setAccessible(true);
            @SuppressWarnings("unchecked")
            List<View> views = (List<View>) viewsField.get(wmg);
            return views;
        } catch (Throwable ignored) {}
        return null;
    }

    /**
     * Resolves the Window reference from a DecorView or sub-window view.
     * Uses unsealed reflection (exempted on Android 9-15) and context hierarchy traversal.
     */
    public static Window getWindowFromView(View decorView) {
        if (decorView == null) return null;
        Class<?> clazz = decorView.getClass();
        while (clazz != null && clazz != Object.class) {
            try {
                Field f = clazz.getDeclaredField("mWindow");
                f.setAccessible(true);
                Object obj = f.get(decorView);
                if (obj instanceof Window) return (Window) obj;
            } catch (Throwable ignored) {}
            try {
                Field f = clazz.getDeclaredField("this$0");
                f.setAccessible(true);
                Object obj = f.get(decorView);
                if (obj instanceof Window) return (Window) obj;
                if (obj instanceof Dialog) return ((Dialog) obj).getWindow();
            } catch (Throwable ignored) {}
            clazz = clazz.getSuperclass();
        }

        Context ctx = decorView.getContext();
        Activity act = getActivityFromContext(ctx);
        if (act != null && act.getWindow() != null) {
            return act.getWindow();
        }
        return null;
    }

    /**
     * Resolves the currently active topmost visible DecorView (modal dialog, popup, or activity).
     * Filters out 0x0 unrendered / detached views.
     */
    public static ViewGroup getTopmostDecorView() {
        List<View> views = getAllWindowViews();
        if (views != null && !views.isEmpty()) {
            for (int i = views.size() - 1; i >= 0; i--) {
                View v = views.get(i);
                if (v instanceof ViewGroup && v.isShown() && v.getVisibility() == View.VISIBLE && v.getWidth() > 0 && v.getHeight() > 0) {
                    return (ViewGroup) v;
                }
            }
            // Fallback: any visible ViewGroup in mViews
            for (int i = views.size() - 1; i >= 0; i--) {
                View v = views.get(i);
                if (v instanceof ViewGroup && v.getVisibility() == View.VISIBLE) {
                    return (ViewGroup) v;
                }
            }
        }

        Activity act = sCurrentActivityRef.get();
        if (act == null || act.isFinishing()) {
            act = getTopmostActivity();
        }
        if (act != null && act.getWindow() != null) {
            View decor = act.getWindow().peekDecorView();
            if (decor instanceof ViewGroup && decor.getVisibility() == View.VISIBLE) {
                return (ViewGroup) decor;
            }
        }
        return null;
    }

    /**
     * Wraps a window callback with TvWindowCallbackWrapper to intercept remote key events.
     */
    private static void wrapWindowCallback(final Window window, final View decorView) {
        if (window == null) return;
        Window.Callback current = window.getCallback();
        if (current instanceof TvWindowCallbackWrapper) {
            return;
        }
        TvWindowCallbackWrapper wrapper = new TvWindowCallbackWrapper(current, window, decorView);
        window.setCallback(wrapper);
    }

    /**
     * Attaches View.OnKeyListener to a window root to guarantee remote keys are intercepted
     * even if the framework dispatches directly to ViewRootImpl without Window.Callback.
     */
    private static void attachViewKeyListener(final View v) {
        if (v == null) return;
        try {
            v.setOnKeyListener(new View.OnKeyListener() {
                @Override
                public boolean onKey(View view, int keyCode, KeyEvent event) {
                    ViewGroup active = (v instanceof ViewGroup) ? (ViewGroup) v : getTopmostDecorView();
                    return processKeyEvent(event, active);
                }
            });
        } catch (Throwable ignored) {}
    }

    /**
     * Scans and wraps the Window.Callback of all active activities, Dialogs, Popups, and Sub-window roots.
     */
    public static void ensureAllWindowCallbacksWrapped() {
        // 1. Wrap the current active activity window
        Activity act = sCurrentActivityRef.get();
        if (act == null || act.isFinishing()) {
            act = getTopmostActivity();
            if (act != null) {
                sCurrentActivityRef = new WeakReference<>(act);
            }
        }
        if (act != null && act.getWindow() != null) {
            wrapWindowCallback(act.getWindow(), act.getWindow().peekDecorView());
            attachViewKeyListener(act.getWindow().peekDecorView());
        }

        // 2. Wrap all active Dialog, Popup, and Sub-window roots in WindowManagerGlobal
        List<View> views = getAllWindowViews();
        if (views != null) {
            for (View v : views) {
                if (v == null) continue;
                Window w = getWindowFromView(v);
                if (w != null) {
                    wrapWindowCallback(w, v);
                }
                attachViewKeyListener(v);
            }
        }
    }

    /**
     * Ensures the cursor overlay layout is attached to the topmost visible DecorView
     * (e.g. migrating seamlessly between Activity and modal Dialogs).
     */
    public static synchronized void ensureOverlayAttachedToTopmost() {
        ViewGroup topmost = getTopmostDecorView();
        if (topmost == null) return;

        // Update active screen dimensions
        if (topmost.getWidth() > 0 && topmost.getHeight() > 0) {
            sScreenWidth = topmost.getWidth();
            sScreenHeight = topmost.getHeight();
        } else {
            Activity act = sCurrentActivityRef.get();
            if (act != null) {
                DisplayMetrics dm = act.getResources().getDisplayMetrics();
                if (dm != null && dm.widthPixels > 0) {
                    sScreenWidth = dm.widthPixels;
                    sScreenHeight = dm.heightPixels;
                }
            }
        }

        Context ctx = topmost.getContext();

        // 1. Create Pointer View if needed
        if (sPointerView == null) {
            sPointerView = new CursorPointerView(ctx != null ? ctx : sApplication);
            sPointerView.setFocusable(false);
            sPointerView.setClickable(false);
            sPointerView.setElevation(999999.0f);
        }

        // 2. Create Overlay Layout if needed
        if (sOverlayLayout == null) {
            sOverlayLayout = new FrameLayout(ctx != null ? ctx : sApplication) {
                @Override
                public boolean onInterceptTouchEvent(MotionEvent ev) {
                    return false;
                }

                @Override
                public boolean dispatchTouchEvent(MotionEvent ev) {
                    return false; // Transparent pass-through
                }
            };
            sOverlayLayout.setTag(TAG_CURSOR_OVERLAY);
            sOverlayLayout.setLayoutParams(new ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT
            ));
            sOverlayLayout.setFocusable(false);
            sOverlayLayout.setClickable(false);
            sOverlayLayout.setClipChildren(false);
            sOverlayLayout.setClipToPadding(false);
            sOverlayLayout.setElevation(999999.0f);
            sOverlayLayout.addView(sPointerView);
        }

        // 3. Move overlay to the topmost DecorView if not already attached
        ViewGroup currentParent = (ViewGroup) sOverlayLayout.getParent();
        if (currentParent != topmost) {
            if (currentParent != null) {
                currentParent.removeView(sOverlayLayout);
            }
            topmost.addView(sOverlayLayout);
            sAttachedDecorRef = new WeakReference<>(topmost);

            topmost.getViewTreeObserver().addOnPreDrawListener(new ViewTreeObserver.OnPreDrawListener() {
                @Override
                public boolean onPreDraw() {
                    if (sOverlayLayout != null && sOverlayLayout.getParent() != null) {
                        ViewGroup p = (ViewGroup) sOverlayLayout.getParent();
                        if (p.getChildAt(p.getChildCount() - 1) != sOverlayLayout) {
                            sOverlayLayout.bringToFront();
                        }
                    }
                    return true;
                }
            });
        }

        // 4. Ensure overlay stays on top without thrashing layout
        if (topmost.getChildAt(topmost.getChildCount() - 1) != sOverlayLayout) {
            sOverlayLayout.bringToFront();
        }
        sPointerView.setTranslationX(sCoords[0]);
        sPointerView.setTranslationY(sCoords[1]);
        sPointerView.setVisibility(sCursorEnabled ? View.VISIBLE : View.GONE);
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
            if (curr.isClickable() || curr.isLongClickable() ||
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
        return null;
    }

    private static void simulateSwipe(ViewGroup decorView, float startX, float startY, float endX, float endY) {
        if (decorView == null) return;
        try {
            long now = SystemClock.uptimeMillis();
            MotionEvent down = MotionEvent.obtain(now, now, MotionEvent.ACTION_DOWN, startX, startY, 0);
            down.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(down);

            long moveTime = now + 120;
            float midX = (startX + endX) / 2.0f;
            float midY = (startY + endY) / 2.0f;
            MotionEvent move = MotionEvent.obtain(now, moveTime, MotionEvent.ACTION_MOVE, midX, midY, 0);
            move.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(move);

            long upTime = now + 240;
            MotionEvent up = MotionEvent.obtain(now, upTime, MotionEvent.ACTION_UP, endX, endY, 0);
            up.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            decorView.dispatchTouchEvent(up);
        } catch (Throwable ignored) {}
    }

    /**
     * Shared key event processor used by both TvWindowCallbackWrapper and View.OnKeyListener.
     * Prevents duplicate handling via exact timestamp/action/code tracking.
     */
    public static boolean processKeyEvent(KeyEvent event, ViewGroup activeDecor) {
        if (event == null) return false;
        long eTime = event.getEventTime();
        int code = event.getKeyCode();
        int action = event.getAction();

        if (eTime == sLastHandledEventTime && code == sLastHandledCode && action == sLastHandledAction) {
            return isNavKey(code) || isConfirmKey(code) || isToggleKey(code);
        }

        final Activity activity = sCurrentActivityRef.get() != null ? sCurrentActivityRef.get() : getTopmostActivity();

        // 0. Toggle Mouse Mode / D-Pad Mode on Menu, Play/Pause, or Info key
        if (isToggleKey(code) && action == KeyEvent.ACTION_DOWN) {
            sLastHandledEventTime = eTime;
            sLastHandledCode = code;
            sLastHandledAction = action;
            toggleCursorMode(activity, sPointerView);
            return true;
        }

        // If user has toggled cursor OFF, let the native app handle keys directly
        if (!sCursorEnabled) {
            return false;
        }

        if (activeDecor == null) {
            activeDecor = getTopmostDecorView();
        }
        if (activeDecor == null) {
            return false;
        }

        float curW = activeDecor.getWidth() > 0 ? (float) activeDecor.getWidth() : sScreenWidth;
        float curH = activeDecor.getHeight() > 0 ? (float) activeDecor.getHeight() : sScreenHeight;

        // 1. D-Pad Navigation: Move Desktop Cursor Pointer
        if (isNavKey(code)) {
            sLastHandledEventTime = eTime;
            sLastHandledCode = code;
            sLastHandledAction = action;

            if (action == KeyEvent.ACTION_DOWN) {
                sRepeatCount = Math.min(sRepeatCount + 1, 10);
                float speed = BASE_SPEED + (sRepeatCount * 4.5f);

                if (code == KeyEvent.KEYCODE_DPAD_UP) sCoords[1] -= speed;
                else if (code == KeyEvent.KEYCODE_DPAD_DOWN) sCoords[1] += speed;
                else if (code == KeyEvent.KEYCODE_DPAD_LEFT) sCoords[0] -= speed;
                else if (code == KeyEvent.KEYCODE_DPAD_RIGHT) sCoords[0] += speed;

                sCoords[0] = Math.max(5.0f, Math.min(sCoords[0], curW - 15.0f));
                sCoords[1] = Math.max(5.0f, Math.min(sCoords[1], curH - 15.0f));

                ensureOverlayAttachedToTopmost();

                if (sPointerView != null) {
                    sPointerView.setTranslationX(sCoords[0]);
                    sPointerView.setTranslationY(sCoords[1]);
                }

                if (sIsPointerDown) {
                    sHasDragged = true;
                    long now = SystemClock.uptimeMillis();
                    try {
                        int[] loc = new int[2];
                        activeDecor.getLocationOnScreen(loc);
                        float localX = Math.max(0.0f, Math.min(sCoords[0] - loc[0], (float) (activeDecor.getWidth() - 1)));
                        float localY = Math.max(0.0f, Math.min(sCoords[1] - loc[1], (float) (activeDecor.getHeight() - 1)));

                        MotionEvent move = MotionEvent.obtain(sDownTime, now, MotionEvent.ACTION_MOVE, localX, localY, 0);
                        move.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                        activeDecor.dispatchTouchEvent(move);
                    } catch (Throwable ignored) {}
                }
            } else if (action == KeyEvent.ACTION_UP) {
                sRepeatCount = 0;
            }
            return true;
        }

        // 2. D-Pad Center / Enter: Accurate Local Touch Event Dispatching
        if (isConfirmKey(code)) {
            sLastHandledEventTime = eTime;
            sLastHandledCode = code;
            sLastHandledAction = action;

            int[] loc = new int[2];
            activeDecor.getLocationOnScreen(loc);
            float localX = Math.max(0.0f, Math.min(sCoords[0] - loc[0], activeDecor.getWidth() > 0 ? (float) (activeDecor.getWidth() - 1) : sCoords[0]));
            float localY = Math.max(0.0f, Math.min(sCoords[1] - loc[1], activeDecor.getHeight() > 0 ? (float) (activeDecor.getHeight() - 1) : sCoords[1]));

            if (action == KeyEvent.ACTION_DOWN) {
                if (event.getRepeatCount() == 0 && !sIsPointerDown) {
                    sIsPointerDown = true;
                    sDownTime = SystemClock.uptimeMillis();
                    sDownX = sCoords[0];
                    sDownY = sCoords[1];
                    sHasDragged = false;

                    if (sPointerView != null) {
                        sPointerView.triggerClickAnimation();
                    }

                    try {
                        MotionEvent down = MotionEvent.obtain(sDownTime, sDownTime, MotionEvent.ACTION_DOWN, localX, localY, 0);
                        down.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                        activeDecor.dispatchTouchEvent(down);
                    } catch (Throwable ignored) {}
                }
            } else if (action == KeyEvent.ACTION_UP) {
                if (sIsPointerDown) {
                    sIsPointerDown = false;
                    long now = SystemClock.uptimeMillis();
                    long upTime = Math.max(now, sDownTime + 65);

                    boolean upHandled = false;
                    try {
                        MotionEvent up = MotionEvent.obtain(sDownTime, upTime, MotionEvent.ACTION_UP, localX, localY, 0);
                        up.setSource(InputDevice.SOURCE_TOUCHSCREEN);
                        upHandled = activeDecor.dispatchTouchEvent(up);
                    } catch (Throwable ignored) {}

                    // Fallback to direct performClick only if synthetic touch was unhandled and not dragged
                    if (!sHasDragged && !upHandled) {
                        final View hit = findTopViewUnder(activeDecor, sCoords[0], sCoords[1]);
                        final View clickable = (hit != null) ? findClickableTarget(hit) : null;

                        if (clickable instanceof EditText) {
                            clickable.requestFocus();
                            try {
                                InputMethodManager imm = (InputMethodManager) activeDecor.getContext().getSystemService(Context.INPUT_METHOD_SERVICE);
                                if (imm != null) {
                                    imm.showSoftInput(clickable, InputMethodManager.SHOW_IMPLICIT);
                                }
                            } catch (Throwable ignored) {}
                        } else if (clickable != null && clickable.isClickable()) {
                            sMainHandler.postDelayed(new Runnable() {
                                @Override
                                public void run() {
                                    try {
                                        clickable.performClick();
                                        clickable.sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_CLICKED);
                                    } catch (Throwable ignored) {}
                                }
                            }, 60);
                        }
                    }
                }
            }
            return true;
        }

        // 3. Fast Page / Channel Up & Down Scroll
        if (code == KeyEvent.KEYCODE_PAGE_DOWN || code == KeyEvent.KEYCODE_CHANNEL_DOWN) {
            sLastHandledEventTime = eTime;
            sLastHandledCode = code;
            sLastHandledAction = action;
            if (action == KeyEvent.ACTION_DOWN) {
                simulateSwipe(activeDecor, curW / 2.0f, curH * 0.75f, curW / 2.0f, curH * 0.25f);
            }
            return true;
        }
        if (code == KeyEvent.KEYCODE_PAGE_UP || code == KeyEvent.KEYCODE_CHANNEL_UP) {
            sLastHandledEventTime = eTime;
            sLastHandledCode = code;
            sLastHandledAction = action;
            if (action == KeyEvent.ACTION_DOWN) {
                simulateSwipe(activeDecor, curW / 2.0f, curH * 0.25f, curW / 2.0f, curH * 0.75f);
            }
            return true;
        }

        return false;
    }

    /**
     * Self-healing Window.Callback wrapper that intercepts TV remote D-Pad, OK, and Toggle keys.
     */
    private static class TvWindowCallbackWrapper implements Window.Callback {
        private final Window.Callback mOriginal;
        private final WeakReference<Window> mWindowRef;
        private final WeakReference<View> mDecorRef;

        public TvWindowCallbackWrapper(Window.Callback original, Window window, View decorView) {
            this.mOriginal = original;
            this.mWindowRef = new WeakReference<>(window);
            this.mDecorRef = new WeakReference<>(decorView);
        }

        private ViewGroup getActiveDecor() {
            ViewGroup top = getTopmostDecorView();
            if (top != null) return top;
            View decor = mDecorRef.get();
            if (decor instanceof ViewGroup) return (ViewGroup) decor;
            return null;
        }

        @Override
        public boolean dispatchKeyEvent(KeyEvent event) {
            final ViewGroup activeDecor = getActiveDecor();
            boolean handled = processKeyEvent(event, activeDecor);
            if (handled) {
                return true;
            }
            return mOriginal != null ? mOriginal.dispatchKeyEvent(event) : false;
        }

        @Override
        public boolean dispatchKeyShortcutEvent(KeyEvent event) {
            return mOriginal != null && mOriginal.dispatchKeyShortcutEvent(event);
        }

        @Override
        public boolean dispatchTouchEvent(MotionEvent event) {
            if (event.getAction() == MotionEvent.ACTION_DOWN || event.getAction() == MotionEvent.ACTION_MOVE) {
                sCoords[0] = event.getX();
                sCoords[1] = event.getY();
                if (sPointerView != null) {
                    sPointerView.setTranslationX(sCoords[0]);
                    sPointerView.setTranslationY(sCoords[1]);
                }
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
                sCoords[0] = event.getX();
                sCoords[1] = event.getY();
                if (sPointerView != null) {
                    sPointerView.setTranslationX(sCoords[0]);
                    sPointerView.setTranslationY(sCoords[1]);
                }
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
            ensureAllWindowCallbacksWrapped();
            ensureOverlayAttachedToTopmost();
            if (mOriginal != null) mOriginal.onContentChanged();
        }

        @Override
        public void onWindowFocusChanged(boolean hasFocus) {
            if (hasFocus) {
                ensureAllWindowCallbacksWrapped();
                ensureOverlayAttachedToTopmost();
            }
            if (mOriginal != null) mOriginal.onWindowFocusChanged(hasFocus);
        }

        @Override
        public void onAttachedToWindow() {
            ensureAllWindowCallbacksWrapped();
            ensureOverlayAttachedToTopmost();
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
