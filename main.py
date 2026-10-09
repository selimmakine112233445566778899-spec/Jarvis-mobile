"""
JARVIS mobil (Android) - Kivy ile yazıldı.

- Komutu yazabilir ya da klavyedeki mikrofon tuşuna basıp konuşabilirsin (Android klavye özelliği).
- Groq anahtarını bir kere kaydetmek için şunu yaz:  anahtar: gsk_...
- Saat, tarih, hava durumu, haberler, kur/bitcoin, hatırlatıcı ve sohbet desteklenir.
"""

import datetime
import json
import math
import os
import re
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, PopMatrix, PushMatrix, Rotate
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

MODEL = "openai/gpt-oss-120b"
CITY = "Izmir"
SYSTEM_PROMPT = "Sen JARVIS adında, Türkçe konuşan bir asistansın. Cevapların kısa ve net olsun, en fazla 3 cümle."
CYAN = (0.22, 0.78, 1, 1)
ORANGE = (1, 0.6, 0.24, 1)
TEXT = (0.75, 0.93, 1, 1)
UA = "JarvisMobile/1.0"


def tr_lower(s):
    return s.replace("İ", "i").replace("I", "ı").lower()


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


class Orb(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.phase = 0.0
        self.speaking = False
        Clock.schedule_interval(self.redraw, 1 / 30)

    def redraw(self, dt):
        self.phase += 0.06
        self.canvas.clear()
        cx, cy = self.center_x, self.center_y
        base = min(self.width, self.height) * 0.2
        pulse = 0.5 + 0.5 * math.sin(self.phase * (6 if self.speaking else 1.5))
        with self.canvas:
            for scale, col in [(1.0, (0.03, 0.13, 0.21)), (0.8, (0.05, 0.22, 0.38)),
                               (0.62, (0.09, 0.4, 0.65)), (0.45, (0.16, 0.65, 0.9)), (0.25, (0.75, 0.93, 1))]:
                r = base * scale * (1 + 0.04 * pulse * math.sin(self.phase * 3 + scale * 10))
                Color(*col)
                Ellipse(pos=(cx - r, cy - r), size=(2 * r, 2 * r))
            rings = [(1.6, 0.5, 1.0, CYAN), (1.8, 0.4, -0.7, ORANGE), (1.4, 1.1, 0.5, CYAN)]
            for k, (rx, ry, spd, col) in enumerate(rings):
                PushMatrix()
                Rotate(angle=math.degrees(self.phase * spd + k), origin=(cx, cy))
                Color(*col)
                Line(ellipse=(cx - base * rx, cy - base * ry, 2 * base * rx, 2 * base * ry), width=1.6)
                PopMatrix()


class JarvisUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=12, spacing=8, **kw)
        self.key_file = os.path.join(App.get_running_app().user_data_dir, "key.json")
        self.api_key = self.load_key()
        self.history = []
        self.log_lines = []

        self.add_widget(Label(text="[color=3ec8ff][b]J.A.R.V.I.S.[/b][/color]", markup=True,
                              font_size="22sp", size_hint_y=None, height=40))
        self.orb = Orb(size_hint_y=0.4)
        self.add_widget(self.orb)
        self.status = Label(text="HAZIR", color=CYAN, size_hint_y=None, height=26)
        self.add_widget(self.status)

        self.log = Label(text="", markup=True, color=TEXT, halign="left", valign="top",
                         font_size="14sp", size_hint_y=None)
        self.log.bind(width=lambda *a: setattr(self.log, "text_size", (self.log.width, None)),
                      texture_size=lambda *a: setattr(self.log, "height", self.log.texture_size[1]))
        scroll = ScrollView(size_hint_y=0.42)
        scroll.add_widget(self.log)
        self.add_widget(scroll)

        row = BoxLayout(size_hint_y=None, height=52, spacing=6)
        self.box = TextInput(hint_text="Komut yaz ya da klavyedeki mikrofona bas",
                             multiline=False, on_text_validate=self.send)
        row.add_widget(self.box)
        row.add_widget(Button(text="GÖNDER", size_hint_x=0.3, on_release=self.send))
        self.add_widget(row)

        self.reply("Sistemler çevrimiçi. Komutunu bekliyorum.")

    # ---------- anahtar saklama ----------
    def load_key(self):
        try:
            with open(self.key_file, encoding="utf-8") as f:
                return json.load(f).get("key", "")
        except Exception:
            return ""

    def save_key(self, key):
        os.makedirs(os.path.dirname(self.key_file), exist_ok=True)
        with open(self.key_file, "w", encoding="utf-8") as f:
            json.dump({"key": key}, f)
        self.api_key = key

    # ---------- arayüz yardımcıları ----------
    @mainthread
    def add_line(self, who, text):
        safe = text.replace("&", "&amp;").replace("[", "&bl;").replace("]", "&br;")
        self.log_lines = (self.log_lines + [f"[color=ff9a3c]{who}[/color]: {safe}"])[-30:]
        self.log.text = "\n\n".join(self.log_lines)

    @mainthread
    def set_status(self, text, speaking=False):
        self.status.text = text
        self.orb.speaking = speaking

    @mainthread
    def reply(self, text):
        self.add_line("Jarvis", text)
        self.set_status("KONUŞUYOR", True)
        try:
            from plyer import tts
            tts.speak(text)
        except Exception:
            pass
        Clock.schedule_once(lambda dt: self.set_status("HAZIR"), max(2, len(text) / 12))

    @mainthread
    def schedule_reminder(self, secs, msg):
        Clock.schedule_once(lambda dt: self.reply(msg), secs)

    # ---------- komut işleme ----------
    def send(self, *args):
        text = self.box.text.strip()
        if not text:
            return
        self.box.text = ""
        self.add_line("Sen", text)
        threading.Thread(target=self.handle, args=(text,), daemon=True).start()

    def handle(self, text):
        self.set_status("DÜŞÜNÜYORUM")
        try:
            answer = self.answer(text)
        except Exception as e:
            answer = f"Bir hata oluştu: {e.__class__.__name__}. İnternetini ve anahtarını kontrol et."
        self.reply(answer)

    def answer(self, text):
        t = tr_lower(text)
        now = datetime.datetime.now()

        if t.startswith("anahtar:"):
            self.save_key(text.split(":", 1)[1].strip())
            return "Anahtarı kaydettim."

        m = re.search(r"(\d+)\s*(saniye|dakika|saat)", t)
        if "hatırlat" in t and m:
            secs = int(m.group(1)) * {"saniye": 1, "dakika": 60, "saat": 3600}[m.group(2)]
            msg = re.sub(r"\d+\s*(saniye|dakika|saat)|sonra|hatırlat\w*|diye|bana", " ", t).strip()
            self.schedule_reminder(secs, f"Hatırlatma: {msg or 'süre doldu'}")
            return f"Tamam, {m.group(1)} {m.group(2)} sonra hatırlatacağım."

        if "saat kaç" in t or t.strip() == "saat":
            return f"Saat {now:%H:%M}."
        if "tarih" in t or "bugün" in t:
            return f"Bugün {now:%d.%m.%Y}."
        if "hava" in t:
            fmt = urllib.parse.quote("%C %t nem %h rüzgar %w")
            return f"{CITY} için hava: " + fetch(f"https://wttr.in/{CITY}?format={fmt}&lang=tr").strip()
        if "haber" in t:
            root = ET.fromstring(fetch("https://feeds.bbci.co.uk/turkce/rss.xml"))
            titles = [i.findtext("title") for i in root.iter("item")][:3]
            return "Son haberler: " + ". ".join(titles)
        if "bitcoin" in t:
            d = json.loads(fetch("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd,try"))
            return f"Bitcoin {d['bitcoin']['usd']:,.0f} dolar, {d['bitcoin']['try']:,.0f} lira."
        if "dolar" in t or "euro" in t:
            r = json.loads(fetch("https://open.er-api.com/v6/latest/USD"))["rates"]
            if "euro" in t:
                return f"Euro {r['TRY'] / r['EUR']:.2f} lira."
            return f"Dolar {r['TRY']:.2f} lira."

        return self.ask_ai(text)

    def ask_ai(self, text):
        if not self.api_key:
            return "Önce Groq anahtarını kaydet. Şöyle yaz: anahtar: gsk_..."
        self.history.append({"role": "user", "content": text})
        body = json.dumps({
            "model": MODEL, "max_tokens": 800,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + self.history[-10:],
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                     "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            ans = json.loads(r.read())["choices"][0]["message"]["content"].strip()
        self.history.append({"role": "assistant", "content": ans})
        return ans


class JarvisApp(App):
    def build(self):
        Window.clearcolor = (0.012, 0.027, 0.05, 1)
        return JarvisUI()


if __name__ == "__main__":
    JarvisApp().run()
