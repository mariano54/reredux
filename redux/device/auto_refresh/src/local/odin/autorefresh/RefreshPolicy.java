package local.odin.autorefresh;

import android.content.Context;
import android.content.SharedPreferences;
import android.provider.Settings;
import android.util.Log;

final class RefreshPolicy {
    static final String TARGET = "me.magnum.melondualds";
    static final String MIN = "min_refresh_rate", PEAK = "peak_refresh_rate";
    private final Context context;
    private final SharedPreferences state;

    RefreshPolicy(Context context) {
        this.context = context.getApplicationContext();
        state = this.context.getSharedPreferences("refresh", Context.MODE_PRIVATE);
    }

    boolean enabled() { return state.getBoolean("enabled", true); }
    boolean active() { return state.getBoolean("active", false); }
    String value(String key) { return Settings.System.getString(context.getContentResolver(), key); }
    String error() { return state.getString("error", ""); }
    boolean allowed() { return OdinSettings.available(); }

    void setEnabled(boolean enabled) {
        state.edit().putBoolean("enabled", enabled).commit();
        if (!enabled) restore();
    }

    private void put(String key, String value) {
        OdinSettings.writeRefresh(key, value);
        String actual = value(key);
        if (value == null ? actual != null : !value.equals(actual))
            throw new IllegalStateException("Could not verify " + key);
    }

    void enter() {
        if (!enabled()) return;
        if (active() && "60.0".equals(value(MIN)) && "60.0".equals(value(PEAK))) return;
        if (!allowed()) {
            failure(new IllegalStateException("Odin settings service is unavailable."));
            return;
        }
        try { OdinSettings.validate(value(MIN)); OdinSettings.validate(value(PEAK)); }
        catch (RuntimeException exception) { failure(exception); return; }
        // Persist the exact previous strings before either write. A restarted
        // service can restore the journal; an unset value is restored as unset.
        if (!active() && !state.edit().putString("normal_min", value(MIN))
                .putString("normal_peak", value(PEAK)).putBoolean("active", true)
                .remove("error").commit()) return;
        try {
            put(MIN, "60.0");
            put(PEAK, "60.0");
            state.edit().remove("error").apply();
            Log.i("OdinAutoRefresh", "ENTER WatermelonDS -> 60 Hz");
        } catch (RuntimeException exception) {
            failure(exception);
            restore();
        }
    }

    void restore() {
        if (!active()) return;
        try {
            put(PEAK, state.getString("normal_peak", null));
            put(MIN, state.getString("normal_min", null));
            state.edit().putBoolean("active", false).commit();
            Log.i("OdinAutoRefresh", "EXIT -> previous refresh settings restored");
        } catch (RuntimeException exception) {
            // Keep the journal so restoration can be retried after permission
            // returns. Never substitute a guessed default for a saved value.
            failure(exception);
        }
    }

    private void failure(RuntimeException exception) {
        state.edit().putString("error", exception.getMessage()).commit();
        Log.e("OdinAutoRefresh", "Refresh setting failed", exception);
    }
}
