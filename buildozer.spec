[app]
title = JARVIS
package.name = jarvis
package.domain = com.selim
source.dir = .
source.include_exts = py,png,jpg,json
version = 0.1
requirements = python3,kivy,plyer,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET
android.archs = arm64-v8a
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
