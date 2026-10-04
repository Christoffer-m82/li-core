package com.lios.browserlauncher;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Toast;

/** A browser launcher only: no WebView, credentials, network client or local data. */
public final class MainActivity extends Activity {
    private static final String LI_URL = "https://li-os-web-7gyegrz7vq-ew.a.run.app/";

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        // Never use incoming intent data, extras or a configurable destination.
        Intent browser = new Intent(Intent.ACTION_VIEW, Uri.parse(LI_URL));
        browser.addCategory(Intent.CATEGORY_BROWSABLE);
        browser.setPackage("com.android.chrome");
        try {
            startActivity(browser);
        } catch (ActivityNotFoundException missingChrome) {
            browser.setPackage(null);
            try {
                startActivity(Intent.createChooser(browser, "Open Li in your browser"));
            } catch (ActivityNotFoundException missingBrowser) {
                Toast.makeText(this, "Install a trusted browser to open Li.", Toast.LENGTH_LONG).show();
            }
        } finally {
            finish();
        }
    }
}
