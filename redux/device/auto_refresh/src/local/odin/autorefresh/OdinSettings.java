package local.odin.autorefresh;

import android.os.IBinder;
import android.os.Parcel;

/** The Odin vendor settings broker, also used by ClusterTune. No root install. */
final class OdinSettings {
    private static IBinder service() {
        try {
            return (IBinder)Class.forName("android.os.ServiceManager")
                .getMethod("getService", String.class).invoke(null, "PServerBinder");
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Odin settings service is unavailable.", exception);
        }
    }

    static boolean available() {
        try { IBinder binder = service(); return binder != null && binder.isBinderAlive(); }
        catch (RuntimeException exception) { return false; }
    }

    static void validate(String value) {
        if (value != null && (!value.matches("[+]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
                || !Double.isFinite(Double.parseDouble(value)) || Double.parseDouble(value) > 1000))
            throw new IllegalStateException("The existing refresh setting is not a valid refresh rate.");
    }

    static void writeRefresh(String key, String value) {
        if (!RefreshPolicy.MIN.equals(key) && !RefreshPolicy.PEAK.equals(key))
            throw new IllegalArgumentException("Only refresh settings can be changed.");
        validate(value);
        // Keys are fixed above, values are strictly numeric. No externally
        // supplied command or path reaches the broker.
        String command = "/system/bin/settings " + (value == null ? "delete" : "put")
            + " system " + key + (value == null ? "" : " '" + value + "'");
        IBinder binder = service();
        if (binder == null) throw new IllegalStateException("Odin settings service is unavailable.");
        Parcel request = Parcel.obtain(), response = Parcel.obtain();
        try {
            request.writeStringArray(new String[]{command, "1"});
            if (!binder.transact(0, request, response, 0))
                throw new IllegalStateException("Odin settings service rejected the change.");
        } catch (android.os.RemoteException exception) {
            throw new IllegalStateException("Odin settings service disconnected.", exception);
        } finally {
            request.recycle(); response.recycle();
        }
    }
}
