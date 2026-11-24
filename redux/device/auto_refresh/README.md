# Odin Auto Refresh

Installed and enabled on the connected Odin 3 on 2026-10-22. Open WatermelonDS normally: the
helper selects 60 Hz while that app is in front and restores the exact previous minimum/peak
refresh settings when another app is opened or the screen sleeps. This covers all WatermelonDS
ROMs and its menus (`me.magnum.melondualds`), rather than a particular game file. Transient
System UI overlays such as the notification shade keep the underlying app's rule.

The usual settings on this device are currently 120 Hz. Apps can still request a lower mode:
iiSU selects 60 Hz with the helper both enabled and disabled. That is independent of this rule.
If the normal settings are changed later, the next session remembers and restores those values.

The helper runs on the Odin, without a Mac connection. Android manages its enabled accessibility
service; window events trigger checks, with a five-second recovery check and sleep/wake handling.
Only the foreground window's package name is read, without traversing nodes or reading text. The
manifest declares no internet, storage, screenshot, input injection, or settings-write permissions.
Refresh writes use the Odin's existing `PServerBinder` service, with a fixed allowlist of only
`min_refresh_rate` and `peak_refresh_rate`. Values must be numeric; arbitrary commands and paths
are not accepted. The vendor protocol is also used by
[ClusterTune](https://github.com/AurelioB/ClusterTune/blob/v0.3.1/app/src/main/java/com/aure/clustertune/root/RootExec.kt).

To disable it, open **Odin Auto Refresh** and choose **Turn off and restore normal refresh**.
Use that before uninstalling. Launching this helper's settings screen also restores normal refresh.
A journal is saved before applying an override so an interrupted session can be recovered when
the service reconnects. Removing the accessibility permission or force-stopping the helper prevents
automatic switching until it is enabled again; reopening its settings restores a pending session.

## Build and install

Requires a local JDK and Android SDK platform/build-tools 35. No Gradle or downloaded dependencies:

```sh
python3 redux/device/auto_refresh/build.py
adb install --no-incremental -r redux/build/odin/auto-refresh/OdinAutoRefresh.apk
```

On a fresh installation, open the helper, select **Enable foreground app detection**, and enable
**Odin Auto Refresh** in Android Accessibility settings. No recurring permission prompt is needed.
Keep `redux/build/odin/auto-refresh/local-helper.jks` to sign future updates with the same local
identity. The key and all APK/build products stay in the ignored build directory.

## Device verification

`redux/build/odin/refresh/switching-checks.json` retains the on-device observations. Verified:

- Helper off: WatermelonDS physically runs at 120 Hz with the original normal settings.
- Helper on: three repeated WatermelonDS/Android Settings round trips physically switch 60/120 Hz.
- Sleep restores the normal settings; waking into WatermelonDS selects 60 Hz again.
- A different normal minimum/peak pair round-trips exactly.
- Disconnecting/reconnecting the helper's accessibility binding restores/reapplies the rule.
- The existing Game Assistant and handheld-miner accessibility services remain enabled.
- The final helper settings screen runs at 120 Hz, with automatic switching enabled.
- ClusterTune Large Underclock caps remain 1,785,600 / 1,958,400 kHz.

No reboot was performed during verification, to preserve the existing emulator session. Actual
hardware display modes were inspected, not inferred only from the settings database. The original
failed Home assertion is retained as `initial-home-observation.json`: the later disabled-helper
control established that iiSU's own 60 Hz request explains that observation.
