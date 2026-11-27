"""settings.py -- pengaturan yang disimpan ke options.json di folder game."""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parent.parent / "options.json"

DEFAULTS = {
    "day_night": True,       # siklus siang/malam + lampu jalan
    "cars": True,            # mobil lalu-lalang
    "emotes": True,          # bubble emote di atas warga
    "floaters": True,        # teks melayang (+Rp, BOOM!, CRASH!, ...)
    "names": False,          # selalu tampilkan nama warga
    "population": 60,        # penduduk awal (20-140)
    "fullscreen": False,
}


class Settings:
    def __init__(self):
        self.data = dict(DEFAULTS)
        try:
            raw = json.loads(PATH.read_text(encoding="utf-8"))
            for k in DEFAULTS:
                if k in raw and type(raw[k]) is type(DEFAULTS[k]):
                    self.data[k] = raw[k]
        except (OSError, ValueError):
            pass

    def __getattr__(self, k):
        try:
            return self.__dict__["data"][k]
        except KeyError:
            raise AttributeError(k)

    def set(self, k, v):
        self.data[k] = v
        self.save()

    def save(self):
        try:
            PATH.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        except OSError:
            pass
