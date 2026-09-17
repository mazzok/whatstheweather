# WeatherPi

Batteriebetriebenes e-Ink-Wetterdisplay auf Raspberry Pi Zero 2 W mit WittyPi 4 L3V7
Power-Management und Waveshare 7.5" e-Paper Display. Läuft off-grid: bootet alle 2h,
holt Wetterdaten von der GeoSphere-Austria-API (kein API-Key nötig), aktualisiert das
Display, fährt komplett herunter (0.3mA Standby).

## Installation (Neuaufsetzen)

Diese Anleitung fasst alle Schritte zusammen, um die WeatherPi-App von einer frisch
geflashten SD-Karte bis zum laufenden Betrieb auf der Hardware einzurichten.

### Hardware

- Raspberry Pi Zero 2 W
- WittyPi 4 L3V7 (RTC + Power Management, Chip: PCF85063A, MCU-Adresse I2C `0x08`)
- Waveshare 7.5" e-Paper HAT, Treiber `epd7in5_V2`
- 3.7V LiPo-Akku, 5000mAh, PH2.0-Stecker (an WittyPi)
- 7x Jumper-Kabel (Male-to-Female, 10cm) für WittyPi ↔ Pi
- 9-adriges SPI-Kabel für e-Paper ↔ Pi

### 1. Verkabelung

Siehe [`docs/pinout.html`](docs/pinout.html) (im Browser öffnen) für das vollständige,
interaktive Pinout-Diagramm.

**Wichtig — GPIO-17-Konflikt:** WittyPi's `SYS_UP`-Pin (Witty-Pin 11) und e-Paper `RST`
wollen beide GPIO 17. Der `SYS_UP`-Jumper muss stattdessen auf **Pi Pin 13 (GPIO 27)**
gesteckt und WittyPi per Menü auf das neue Pin umkonfiguriert werden (siehe Schritt 9,
Menüpunkt "Change the GPIO pin used to detect system status"). Ohne diesen Schritt
funktioniert entweder die Shutdown-Erkennung oder das Display nicht zuverlässig.

Kurzreferenz der 7 Jumper (WittyPi-Pin → Pi-Pin):

| Jumper | Funktion | WittyPi-Pin | Pi-Pin |
|--------|----------|-------------|--------|
| J1 | 5V | 2 | 2 |
| J2 | SDA (I2C) | 3 | 3 |
| J3 | SCL (I2C) | 5 | 5 |
| J4 | GND | 6 | 6 |
| J5 | HALT (GPIO4) | 7 | 7 |
| J6 | TXD (GPIO14) | 8 | 8 |
| J7 | SYS_UP → **umgemappt** | 11 | **13 (GPIO27)** |

e-Paper HAT wird per 9-adrigem SPI-Flachbandkabel direkt auf die Pi-Pins gesteckt
(kein Umbau nötig, siehe Farbzuordnung in `pinout.html`).

### 2. Basis-Setup (Raspberry Pi Imager)

**Image:** Raspberry Pi OS **Lite (64-bit)** — kein Desktop nötig (headless, einziges
Display ist das e-Paper), Lite schont das begrenzte RAM (512MB) des Pi Zero 2 W. 64-bit
wird von der Raspberry Pi Foundation mittlerweile für alle kompatiblen Boards empfohlen;
nichts in diesem Projekt hängt von 32-bit-only-Bibliotheken ab.

**WLAN:** Der Pi Zero 2 W funkt **nur auf 2.4GHz** (Broadcom/Synaptics 43430-Chip, kein
5GHz-Support). Falls dein Router getrennte SSIDs für 2.4/5GHz nutzt, unbedingt die
2.4GHz-SSID verwenden — sonst verbindet sich der Pi nie.

Beim Flashen der SD-Karte im Raspberry Pi Imager (Advanced Options / Zahnrad-Icon):

- Hostname: z.B. `weatherpi`
- SSH aktivieren (Passwort- oder Key-Auth)
- WLAN-Zugangsdaten für die **Erstinstallation** eintragen — 2.4GHz-Netz auswählen
  (wird später ggf. durch die QR-Code-Provisionierung ersetzt/ergänzt, siehe Schritt 10)
- Zeitzone: `Europe/Vienna`, Locale nach Bedarf

Nach dem ersten Boot per SSH verbinden: `ssh pi@weatherpi.local`

> **Kritisch — vor JEDEM Reboot/Shutdown auf cloud-init warten:** Aktuelle Raspberry Pi
> OS Images (Trixie+) nutzen cloud-init für die Erstkonfiguration. Direkt nach dem ersten
> Boot läuft cloud-init im Hintergrund noch weiter — u.a. wird die Root-Partition auf die
> volle SD-Karten-Größe vergrößert (`growpart`/`resize2fs`) und `/etc/fstab` geschrieben.
> SSH wird bereits nutzbar, **bevor** dieser Prozess fertig ist (SSH wird von cloud-init
> selbst als einer der ersten Schritte aktiviert). Ein `sudo reboot`/`shutdown`, das
> mitten in diesen Prozess platzt, hinterlässt ein Root-Filesystem, das beim nächsten
> Boot nicht mehr mountet — der Pi bleibt dann mit dauerhaft grüner LED (keine
> SD-Karten-Aktivität) hängen und ist über SSH nicht mehr erreichbar. Siehe auch
> Stolperstein weiter unten.
>
> Nach jedem ersten Login (und vor jedem Neustart) daher zuerst:
>
> ```bash
> cloud-init status --wait
> ```
>
> Das Kommando blockiert, bis cloud-init fertig ist, und meldet dann `status: done`
> (ein `status: error` ist in der Praxis oft harmlos — siehe Stolperstein weiter unten).
> Erst danach mit dem nächsten Schritt fortfahren.
>
> **Kritisch — niemals `sudo reboot` verwenden, auf diesem Board von Anfang an:**
> WittyPi's TXD-Pin (GPIO 14) ist bereits ab Schritt 1 fest verkabelt. WittyPi's
> MCU-Firmware überwacht diesen Pin **unabhängig davon, ob die WittyPi-Software auf dem
> Pi installiert ist** (das passiert erst in Schritt 9) — die Firmware läuft immer auf
> dem WittyPi-Board selbst. Ein `sudo reboot` erzeugt kurzzeitig genau das gleiche
> TXD-Signal wie ein abgeschlossener Shutdown; WittyPi kappt daraufhin mitten im Reboot
> die Stromversorgung, was die FAT32-Boot-Partition beschädigt (siehe Stolperstein
> "4x blinkende LED" weiter unten — durch Test bestätigt: auch ein reiner `reboot` ganz
> ohne vorheriges apt-Upgrade führt zuverlässig zur Beschädigung).
>
> **Immer stattdessen:**
> ```bash
> sudo shutdown -h now
> ```
> abwarten, bis die grüne LED aus ist, dann manuell Strom neu verbinden (USB-Kabel
> ziehen/wieder einstecken, oder WittyPi-Taste drücken). Das gilt für **jeden** Neustart
> in dieser Anleitung, auch vor Schritt 9.

### 3. System aktualisieren

Vor allem anderen: Paketindex und installierte Pakete auf den aktuellen Stand bringen
(das Image kann Wochen/Monate alt sein — betrifft Kernel, Firmware, Sicherheitsupdates):

```bash
cloud-init status --wait   # falls noch nicht geschehen, siehe Hinweis in Schritt 2
sudo apt update
sudo apt full-upgrade -y
sudo shutdown -h now
```

Grüne LED abwarten bis aus, dann Strom manuell trennen/neu verbinden (siehe Hinweis in
Schritt 2 — **nicht** `sudo reboot` verwenden).

### 4. System-Interfaces aktivieren

SPI (für e-Paper) und I2C (für WittyPi) müssen aktiviert sein:

```bash
cloud-init status --wait   # nach jedem Neustart erneut abwarten
sudo raspi-config nonint do_spi 0
sudo raspi-config nonint do_i2c 0
sudo timedatectl set-ntp true
sudo shutdown -h now
```

Grüne LED abwarten bis aus, dann Strom manuell trennen/neu verbinden (**nicht**
`sudo reboot` — siehe Hinweis in Schritt 2).

Nach dem Reboot prüfen:

```bash
ls /dev/spidev0.0 /dev/i2c-1
i2cdetect -y 1   # sollte 0x08 (WittyPi MCU) zeigen
```

> **Hinweis zur Uhrzeit/RTC:** WittyPi 4 L3V7 hat eine eigene RTC (PCF85063A), die
> **nicht** über den Linux-Kernel-RTC-Mechanismus (`dtoverlay=i2c-rtc,...`) läuft,
> sondern ausschließlich über die WittyPi-eigene Software (`wittyPi.sh`, Schritt 9)
> per I2C-Protokoll mit der MCU kommuniziert. **Keinen** `i2c-rtc`-Overlay in
> `/boot/firmware/config.txt` eintragen — das ist für ein separates DS3231-Modul
> gedacht (Vorgänger-Hardware vor dem WittyPi-Upgrade) und kollidiert mit WittyPi.
> `sudo hwclock -r` wird daher immer "Cannot access the
> Hardware Clock" melden — das ist erwartet und kein Fehler. Die Zeit wird
> stattdessen über NTP (System) und WittyPi's eigenen Sync (Schritt 9) korrekt gehalten.

### 5. Basis-Softwarepakete installieren

`python3` ist auf Raspberry Pi OS vorinstalliert — `git` und `pip3` **nicht**
(zumindest nicht auf dem Lite-Image), daher zuerst per apt nachinstallieren:

```bash
sudo apt install -y git python3-pip python3-smbus i2c-tools
```

Die apt-Spiegelserver für Raspberry Pi OS sind gelegentlich inkonsistent
(`raspbian.raspberrypi.com` liefert 404 auf Pakete, die `debian.anexia.at` hat — trifft
in der Praxis eher Pakete mit größerer Abhängigkeitskette wie `python3-pil`/`python3-qrcode`,
kann aber jedes Paket treffen). Bei 404-Fehlern hilft `sudo apt update` erneut ausführen
oder — bei Python-Paketen mit PyPI-Äquivalent — direkt auf `pip3 install ... --break-system-packages`
ausweichen (siehe Schritt 7).

### 6. Projekt deployen

```bash
cd ~
git clone <repo-url> whatstheweather
cd whatstheweather
```

`config.yaml` prüfen/anpassen:

```yaml
debug: false
interval: 7200
# city: Wien    # Optional: überschreibt den per IP-Geolocation ermittelten Stadtnamen
provisioning_ssid: "WeatherDisplay"
provisioning_password: "weather123"
```

### 7. Python-Abhängigkeiten installieren

```bash
cd ~/whatstheweather
pip3 install -r requirements.txt --break-system-packages
```

`requirements.txt` enthält bereits: `Pillow`, `requests`, `PyYAML`, `smbus2`, `qrcode[pil]`.
Fonts (`Inter-*.ttf`, `DejaVuSansMono*.ttf`) sind im Repo unter `fonts/` bereits enthalten —
kein separater Download nötig.

### 8. Waveshare e-Paper Treiber installieren

Nicht Teil von `requirements.txt` (kein PyPI-Standardpaket) — offizielles Waveshare-Repo:

```bash
cd ~
git clone https://github.com/waveshare/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python
sudo python3 setup.py install
```

Test (optional, HAT muss angeschlossen sein):

```bash
python3 -c "from waveshare_epd import epd7in5_V2; print('OK')"
```

### 9. WittyPi Software installieren

Offizielles UUGear-Installationsskript ([Quelle](https://github.com/uugear/Witty-Pi-4)):

```bash
cd ~
wget https://www.uugear.com/repo/WittyPi4/install.sh
sudo sh install.sh
```

Installiert nach `~/wittypi/` (u.a. `wittyPi.sh`). Danach WittyPi konfigurieren:

```bash
cd ~/wittypi
sudo ./wittyPi.sh
```

Im Menü:

1. **GPIO-Pin für SYS_UP ändern** auf GPIO 27 (siehe
   [UUGear-Anleitung](https://www.uugear.com/portfolio/change-the-pin-that-used-by-witty-pi/)) —
   behebt den Pin-17-Konflikt aus Schritt 1
2. **"Startup when USB power is connected"** aktivieren — nötig für die Charger-Wake-Funktion
   (Pi bootet automatisch, sobald ein Ladegerät angeschlossen wird, siehe Verifikation in Schritt 12).
   Falls die Option im Menü fehlt, Firmware-Version prüfen (`cat ~/wittypi/firmware/version`)
   und im WittyPi-4-L3V7-Handbuch den passenden `wittyPi.sh`-Befehl bzw. das I2C-Register nachschlagen.
3. Schedule-Script laden:
   ```bash
   cp ~/whatstheweather/setup/schedule.wpi ~/wittypi/schedule.wpi
   sudo ./wittyPi.sh
   # Menüpunkt: Schedule Script laden/anwenden
   ```
   (2h-Zyklus: 5 Min. ON, 1h55 OFF — feste Slots ab 00:00)

   > **Wichtig — Schedule-Script erst ganz am Ende aktivieren:** Sobald das
   > Schedule-Script angewendet wird, berechnet WittyPi sofort den nächsten
   > Shutdown-Zeitpunkt und kappt dann zuverlässig die Stromversorgung — auch
   > mitten in einer laufenden SSH-Session oder während weiterer Setup-Schritte
   > (WiFi-Connect, systemd-Service, Verifikation). Ein unsauberer Abbruch
   > mitten in einem laufenden `apt`/Deployment-Vorgang kann dieselbe Art von
   > Schaden anrichten wie ein `sudo reboot` (siehe Stolperstein weiter unten) —
   > FAT32-Boot-Partition-Korruption. Erst Zeit synchronisieren (Menüpunkt 1)
   > und danach mit den restlichen Schritten (10–12) fortfahren; das
   > Schedule-Script erst laden/aktivieren, wenn alles andere fertig
   > eingerichtet ist und ein Shutdown zu jedem Zeitpunkt unproblematisch wäre.

### 10. WiFi Connect (QR-Code-Provisionierung) installieren

Für den Fall, dass die App beim Boot kein bekanntes WLAN findet:

```bash
sudo bash setup/install_wifi_connect.sh
```

### 11. systemd-Service einrichten

```bash
sudo cp setup/weather-display.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable weather-display.service
```

**`setup/weather-display.timer` NICHT aktivieren** — das ist ein Relikt aus der Zeit
vor der WittyPi-Hardware-Steuerung. Der 2h-Zyklus läuft jetzt komplett über WittyPi's
`schedule.wpi` (Schritt 9): WittyPi bootet den Pi, `weather-display.service` startet
automatisch (`WantedBy=multi-user.target`), die App aktualisiert das Display und
ruft selbst `sudo shutdown -h now` auf. WittyPi kappt danach den Strom.

### 12. Verifikation

Manueller Testlauf (kein automatischer Shutdown im Debug-Modus):

```bash
cd ~/whatstheweather
PYTHONPATH=/home/pi/whatstheweather python3 src/main.py --debug
```

Prüfen:
- Keine `ModuleNotFoundError` (qrcode, waveshare_epd, smbus2)
- Standort/Wetterdaten werden geladen
- `preview.png` wird erzeugt, Frage "Display aktualisieren? [j/N]" — mit `j` bestätigen
- Display zeigt aktuelles Datum/Uhrzeit korrekt an (siehe Zeit-Hinweis in Schritt 4)

Danach echten Boot-Zyklus testen:
```bash
sudo systemctl start weather-display.service
sudo journalctl -u weather-display.service -f
```

Charger-Wake-Funktion end-to-end testen:
1. Pi normal herunterfahren: `sudo shutdown -h now`
2. Warten bis die grüne Pi-LED aus ist
3. Ladegerät einstecken
4. Innerhalb von ~15s sollte der Pi booten (LED an)
5. Innerhalb von ~60s sollte sich das Display aktualisieren
6. Ladegerät abziehen → nach dem nächsten 2h-Poll ein letztes Update, dann Shutdown

### Laufzeit-Dateien

Die App legt zur Laufzeit auf dem Pi eigene State-/Log-Dateien im Home-Verzeichnis an
(nicht Teil des Repos, kein manuelles Setup nötig):

| Datei | Zweck |
|-------|-------|
| `~/.weather_cache.json` | Letzter erfolgreicher Wetter-Fetch (Fallback bei API-/Netzwerkfehler) |
| `~/.weather_recharge` | Datum + Batterie-% des letzten Ladevorgangs (Off-Grid-Tage-Zähler) |
| `~/.weather_battery_log.csv` | Ein Eintrag pro Boot: Timestamp, Batterie-V/%, USB-V, Charging |
| `~/.weather_display.log` | Log-Datei im Produktionsmodus (Debug-Modus loggt nach stdout) |

### Bekannte Stolpersteine (aus der Praxis)

- **`ModuleNotFoundError: No module named 'src'`** — `python3 src/main.py` ohne
  `PYTHONPATH=/home/pi/whatstheweather` gestartet, oder nicht aus dem Projekt-Root heraus.
  Alternative: `python3 -m src.main --debug` aus dem Projekt-Root.
- **apt 404 auf `raspbian.raspberrypi.com`** — Mirror-Sync-Lücke, kein Warten hilft;
  stattdessen `pip3 install ... --break-system-packages`.
- **`FileNotFoundError` bei `SPI.open(0, 0)`** — SPI nicht aktiviert (Schritt 4).
- **`hwclock: Cannot access the Hardware Clock`** — erwartet, siehe Hinweis in Schritt 4.
- **Service killt die SSH-Session während der Fehlersuche** — `main.py` ruft im
  Normalbetrieb `sudo shutdown -h now` auf. Vor manuellen Debugging-Sessions:
  ```bash
  sudo systemctl stop weather-display.service
  sudo systemctl disable weather-display.service
  ```
  Nach Abschluss wieder mit `sudo systemctl enable weather-display.service` aktivieren.
- **Pi bleibt nach `reboot`/Neustart mit dauerhaft grüner LED hängen, keine SD-Karten-
  Aktivität, SSH nicht erreichbar** — root-Filesystem wurde durch einen Reboot mitten in
  cloud-init's Erstboot-Prozess (Partitions-/Filesystem-Resize) beschädigt, siehe Hinweis
  in Schritt 2. Zur Bestätigung: SD-Karte in einen Reader stecken und mit einem
  Linux-fähigen Tool (z.B. DiskInternals Linux Reader) die Root-Partition prüfen — fehlt
  `/etc/fstab` und ist `/var/log/journal/` leer, wurde die Erstkonfiguration nie
  abgeschlossen. In diesem Zustand hilft nur Neuflashen; **Fix ist Prävention**, nicht
  Reparatur: nach jedem ersten Login und vor jedem `reboot`/`shutdown` erst
  `cloud-init status --wait` abwarten (Schritt 2).
- **WittyPi cuttet die Stromversorgung kurz nach einem `sudo reboot`** (gilt ab Schritt 1,
  sobald der TXD-Jumper gesteckt ist — **nicht** erst ab Schritt 9/Software-Installation,
  siehe Bestätigung im vorherigen Stolperstein) — beim Reboot geht der TXD-Pin
  (GPIO-14) kurzzeitig auf LOW, bevor der Kernel wieder hochfährt. WittyPi's
  MCU-Firmware läuft unabhängig von jeder Pi-seitigen Software und wertet das als
  "System heruntergefahren", kappt den Strom, obwohl der Reboot eigentlich noch lief.
  Bekanntes UUGear-Verhalten, kein Bug in diesem Projekt. **Nie `sudo reboot`
  verwenden** — nur `sudo shutdown -h now` gefolgt von manueller Stromneuverbindung
  (Kabel ziehen/stecken oder WittyPi-Taste; ab Schritt 9 auch Schedule/Charger-Wake).
  Ein echter Shutdown durchläuft den TXD-Übergang genau einmal und ohne den
  Zwischenzustand, den ein Reboot erzeugt.
- **Pi bleibt nach `sudo reboot` mit 4x wiederholt blinkender grüner LED hängen** — das
  ist Raspberry Pis offizieller Bootloader-Fehlercode "start\*.elf not found" (0 lange,
  4 kurze Blinks), sichtbar als fehlende `start.elf`/`start4.elf`, fehlende
  `fixup4.dat` oder verstümmelte Dateinamen (z.B. `start4cd.elf` erscheint plötzlich als
  `START4CD.ELF`) sowie kryptische Ordnereinträge mit unmöglichen Größen — klassische
  FAT32-Verzeichnistabellen-Beschädigung.
  **Bestätigte Root Cause:** Das ist **nicht** in erster Linie ein Timing-/Cache-Problem
  (ein früherer Verdacht — `sync`/`sleep 5` vor dem Reboot half **nicht**, das Problem
  trat auch bei einem reinen `reboot` ganz ohne vorheriges apt-Upgrade zuverlässig auf).
  Ursache ist WittyPi selbst: `sudo reboot` erzeugt kurz das gleiche TXD-Signal wie ein
  abgeschlossener Shutdown, WittyPi's MCU-Firmware (läuft immer, unabhängig von der
  Software-Installation aus Schritt 9) kappt daraufhin mitten im Reboot-Vorgang die
  Stromversorgung und beschädigt dabei die FAT32-Boot-Partition. Siehe ausführliche
  Erklärung in Schritt 2.
  **Fix ist Prävention, nicht Timing:** ab Schritt 1 **nie** `sudo reboot` verwenden,
  ausschließlich `sudo shutdown -h now` + manueller Stromneuverbindung (siehe Schritt 2).
  Zur Bestätigung eines bereits eingetretenen Falls: SD-Karte in einen Reader stecken
  und `chkdsk E: /f /r` auf der Boot-Partition laufen lassen — meldet es "Ungültiger
  langer Ordnereintrag" oder wiederhergestellte "verlorene Ketten", ist das die
  Bestätigung. Repariert werden kann die Boot-Partition selbst nicht zuverlässig —
  SD-Karte neuflashen.
