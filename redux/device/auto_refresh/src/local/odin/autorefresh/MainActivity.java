package local.odin.autorefresh;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private RefreshPolicy policy;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        policy = new RefreshPolicy(this);
    }

    @Override protected void onResume() {
        super.onResume();
        // Opening this settings screen is itself leaving the emulator.
        policy.restore();
        render();
    }

    private TextView text(LinearLayout column, String value, int size) {
        TextView view = new TextView(this);
        view.setText(value); view.setTextSize(size); view.setTextColor(Color.rgb(230, 235, 243));
        view.setPadding(0, 10, 0, 16); column.addView(view); return view;
    }

    private void button(LinearLayout column, String title, View.OnClickListener action) {
        Button view = new Button(this); view.setText(title); view.setAllCaps(false);
        view.setOnClickListener(action); column.addView(view);
    }

    private void render() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(20, 25, 34));
        LinearLayout column = new LinearLayout(this); column.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(24 * getResources().getDisplayMetrics().density);
        column.setPadding(pad, pad, pad, pad); scroll.addView(column); setContentView(scroll);
        text(column, "Odin Auto Refresh", 28);
        text(column, "WatermelonDS  ·  60 Hz\nOther apps  ·  your previous refresh setting", 20);
        text(column, "Switches automatically when you open or leave WatermelonDS, including its menus. "
            + "Your usual refresh rate returns when you go Home or open another app.", 16);
        String services = Settings.Secure.getString(getContentResolver(), Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        boolean connected = services != null && services.contains(getPackageName() + "/");
        boolean permission = policy.allowed();
        text(column, policy.enabled() && connected && permission ? "Automatic switching is on" : "Automatic switching needs setup or is off", 19);
        button(column, policy.enabled() ? "Turn off and restore normal refresh" : "Turn on automatic switching", v -> {
            policy.setEnabled(!policy.enabled()); render();
        });
        if (!permission) text(column, "The Odin settings service is unavailable on this device.", 16);
        if (!connected) button(column, "Enable foreground app detection", v ->
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        button(column, "Open WatermelonDS", v -> startActivity(new Intent(Intent.ACTION_MAIN)
            .addCategory(Intent.CATEGORY_LAUNCHER)
            .setComponent(new ComponentName(RefreshPolicy.TARGET, RefreshPolicy.TARGET + ".DefaultIcon"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED)));
        text(column, "Only the foreground app name is used. No screen text, screenshots, ROMs, saves or internet access.", 14);
        if (!policy.error().isEmpty()) text(column, "Setup message: " + policy.error(), 14);
    }
}
