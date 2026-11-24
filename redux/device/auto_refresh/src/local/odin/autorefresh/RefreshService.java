package local.odin.autorefresh;

import android.accessibilityservice.AccessibilityService;
import android.app.KeyguardManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;

public final class RefreshService extends AccessibilityService {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private RefreshPolicy policy;
    private final Runnable update = this::inspectForeground;
    private final Runnable watchdog = new Runnable() {
        @Override public void run() {
            inspectForeground();
            handler.postDelayed(this, 5000);
        }
    };
    private final BroadcastReceiver screen = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (Intent.ACTION_SCREEN_OFF.equals(intent.getAction())) policy.restore();
            else handler.postDelayed(update, 350);
        }
    };

    @Override protected void onServiceConnected() {
        policy = new RefreshPolicy(this);
        policy.restore(); // Recover an interrupted session before identifying the foreground app again.
        IntentFilter filter = new IntentFilter(Intent.ACTION_SCREEN_OFF);
        filter.addAction(Intent.ACTION_SCREEN_ON);
        filter.addAction(Intent.ACTION_USER_PRESENT);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(screen, filter, RECEIVER_NOT_EXPORTED);
        else registerReceiver(screen, filter);
        handler.post(watchdog);
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {
        handler.removeCallbacks(update);
        handler.postDelayed(update, 100);
    }

    private void inspectForeground() {
        if (policy == null) return;
        PowerManager power = (PowerManager)getSystemService(POWER_SERVICE);
        KeyguardManager lock = (KeyguardManager)getSystemService(KEYGUARD_SERVICE);
        if (!policy.enabled() || !power.isInteractive() || lock.isKeyguardLocked()) {
            policy.restore();
            return;
        }
        AccessibilityNodeInfo root = getRootInActiveWindow();
        if (root == null) return; // A window transition is inconclusive; retry on the next event/watchdog.
        CharSequence name = root.getPackageName();
        String foreground = name == null ? "" : name.toString();
        root.recycle();
        // The root's package is the only window property read. Do not traverse
        // nodes or retrieve text. System UI temporarily covers an app (shade,
        // volume controls); do not treat that as leaving the underlying app.
        if (foreground.isEmpty() || foreground.equals("com.android.systemui")) return;
        if (RefreshPolicy.TARGET.equals(foreground)) policy.enter();
        else policy.restore();
    }

    @Override public void onInterrupt() { if (policy != null) policy.restore(); }

    @Override public void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if (policy != null) {
            unregisterReceiver(screen);
            policy.restore();
        }
        super.onDestroy();
    }
}
