package com.artcraft.updater;

import android.app.Activity;

/** Integration builds do not check the reference fork's builder releases.
 * Release-native app-scoped updaters must be ported from each recorded baseline
 * before this branch can produce replacement APKs.
 */
public final class UpdateCheck {
    private UpdateCheck() {}
    public static void start(final Activity activity) {
        // Intentionally no network request in compiler-only integration builds.
    }
}
