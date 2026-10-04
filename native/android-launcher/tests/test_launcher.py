"""Offline contract and actual Java control-flow tests; no Android or Li network calls."""

import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = "{http://schemas.android.com/apk/res/android}"
STUBS = {
    "android/os/Bundle.java": "package android.os; public class Bundle {}",
    "android/net/Uri.java": """package android.net;
public class Uri {
    public final String value;
    private Uri(String value) { this.value = value; }
    public static Uri parse(String value) { return new Uri(value); }
}""",
    "android/content/ActivityNotFoundException.java": """package android.content;
public class ActivityNotFoundException extends RuntimeException {}""",
    "android/content/Intent.java": """package android.content;
import android.net.Uri;
public class Intent {
    public static final String ACTION_VIEW = "android.intent.action.VIEW";
    public static final String CATEGORY_BROWSABLE = "android.intent.category.BROWSABLE";
    public final String action;
    public final Uri uri;
    public String category, browserPackage;
    public boolean chooser;
    public Intent(String action, Uri uri) { this.action = action; this.uri = uri; }
    public Intent addCategory(String value) { category = value; return this; }
    public Intent setPackage(String value) { browserPackage = value; return this; }
    public static Intent createChooser(Intent intent, String title) {
        Intent result = new Intent(intent.action, intent.uri);
        result.category = intent.category;
        result.chooser = true;
        return result;
    }
}""",
    "android/app/Activity.java": """package android.app;
import android.os.Bundle;
import android.content.Intent;
import android.content.ActivityNotFoundException;
public class Activity {
    public static boolean chromeMissing, allMissing;
    public static int attempts, finished;
    public static Intent launched;
    public void onCreate(Bundle state) {}
    public Intent getIntent() { throw new AssertionError("incoming intent must not be read"); }
    public void startActivity(Intent intent) {
        attempts++;
        if (allMissing || (chromeMissing && intent.browserPackage != null)) {
            throw new ActivityNotFoundException();
        }
        launched = intent;
    }
    public void finish() { finished++; }
}""",
    "android/widget/Toast.java": """package android.widget;
import android.app.Activity;
public class Toast {
    public static final int LENGTH_LONG = 1;
    public static int shown;
    public static Toast makeText(Activity activity, String text, int duration) { return new Toast(); }
    public void show() { shown++; }
}""",
    "LauncherProbe.java": """import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.widget.Toast;
import com.lios.browserlauncher.MainActivity;
public class LauncherProbe {
    public static void main(String[] args) {
        Activity.chromeMissing = args[0].equals("fallback");
        Activity.allMissing = args[0].equals("missing");
        new MainActivity().onCreate(args[0].equals("restored") ? new Bundle() : null);
        if (Activity.finished != 1) throw new AssertionError("launcher did not finish");
        if (Activity.allMissing) {
            if (Activity.launched != null || Activity.attempts != 2 || Toast.shown != 1)
                throw new AssertionError("missing browser must fail without looping");
        } else {
            Intent target = Activity.launched;
            if (target == null || !target.uri.value.equals("https://li-os-web-7gyegrz7vq-ew.a.run.app/"))
                throw new AssertionError("wrong destination");
            if (!target.action.equals(Intent.ACTION_VIEW) || !target.category.equals(Intent.CATEGORY_BROWSABLE))
                throw new AssertionError("wrong browser action");
            if (Activity.chromeMissing) {
                if (!target.chooser || target.browserPackage != null || Activity.attempts != 2)
                    throw new AssertionError("fallback must show chooser");
            } else if (!"com.android.chrome".equals(target.browserPackage) || Activity.attempts != 1) {
                throw new AssertionError("prefer Chrome without retry");
            }
            if (Toast.shown != 0) throw new AssertionError("unexpected error");
        }
    }
}""",
}


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.manifest = ET.parse(ROOT / "AndroidManifest.xml").getroot()

    def test_no_permissions_or_url_handler(self):
        self.assertEqual(self.manifest.findall("uses-permission"), [])
        self.assertEqual(self.manifest.findall("uses-permission-sdk-23"), [])
        self.assertEqual(self.manifest.findall(".//data"), [])
        self.assertEqual(self.manifest.findall(".//service"), [])
        self.assertEqual(self.manifest.findall(".//provider"), [])
        self.assertEqual(self.manifest.findall(".//receiver"), [])

    def test_non_debuggable_no_backup_or_cleartext(self):
        app = self.manifest.find("application")
        for name in ("debuggable", "allowBackup", "usesCleartextTraffic"):
            self.assertEqual(app.get(ANDROID + name), "false")
        self.assertEqual(len(app.findall("activity")), 1)

    def test_sdk_and_launcher_identity(self):
        sdk = self.manifest.find("uses-sdk")
        self.assertEqual(sdk.get(ANDROID + "minSdkVersion"), "26")
        self.assertEqual(sdk.get(ANDROID + "targetSdkVersion"), "35")
        self.assertEqual(self.manifest.get("package"), "com.lios.browserlauncher")
        self.assertEqual(
            self.manifest.find(".//action").get(ANDROID + "name"),
            "android.intent.action.MAIN",
        )
        self.assertEqual(
            self.manifest.find(".//category").get(ANDROID + "name"),
            "android.intent.category.LAUNCHER",
        )


class JavaFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("javac") or not shutil.which("java"):
            raise RuntimeError("JDK required; do not label unexecuted Java checks as passed")
        cls.temp = tempfile.TemporaryDirectory(prefix="li-launcher-tests-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.work = Path(cls.temp.name)
        sources = []
        for relative, content in STUBS.items():
            path = cls.work / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            sources.append(str(path))
        sources.append(str(ROOT / "src/com/lios/browserlauncher/MainActivity.java"))
        subprocess.run(["javac", "-d", str(cls.work), *sources], check=True, capture_output=True)

    def probe(self, scenario):
        subprocess.run(
            ["java", "-cp", str(self.work), "LauncherProbe", scenario],
            check=True,
            capture_output=True,
        )

    def test_chrome_fixed_url_no_incoming_intent(self):
        self.probe("normal")

    def test_fallback_browser_chooser(self):
        self.probe("fallback")

    def test_no_browser_finishes_without_loop(self):
        self.probe("missing")

    def test_restored_activity_uses_only_fixed_url(self):
        self.probe("restored")


if __name__ == "__main__":
    unittest.main()
