[Übersicht](../README.md) | [Anleitungen](README.md) | [Entwurf der Server Edition](server.md)

# Die Server Edition einrichten

Vom leeren Server bis zum Archiv im Browser. Rechnen Sie mit einer
halben Stunde.

**Was am Ende steht:** Ein Dienst, der ein Archiv im Netz bereitstellt.
Mehrere Menschen melden sich an und sehen jeweils die Postfächer, die
ihnen zugeordnet sind. Post geholt wird weiterhin im Hintergrund.

**Was noch nicht geht:** Schreiben. Einstufen, Löschen und das
Zurücklegen ins Postfach bleiben vorerst der Kommandozeile und dem
Fenster vorbehalten.

> **Der Windows-Teil ist ungeprüft.** Für Debian ist dieser Ablauf
> durchgespielt; unter Windows Server steht er hier nach bestem Wissen,
> aber niemand hat ihn ausgeführt. Die Prüfung ist für Oktober 2026
> verabredet.

## Vorweg: Wo das Archiv herkommt

Der Server legt kein Archiv an – er stellt eines bereit. Zwei Wege:

**Ein neues Archiv** auf dem Server selbst:

```bash
mailburg anlegen /var/lib/mailburg/Archiv --modus geschaeftlich
```

**Oder ein vorhandenes** vom Arbeitsplatz hinüberkopieren. Ein Archiv
ist ein gewöhnlicher Ordner; kopieren genügt. Der Suchindex kommt nicht
mit – er liegt außerhalb und wird auf dem Server neu erzeugt:

```bash
mailburg neuaufbau /var/lib/mailburg/Archiv
```

Zum Ausprobieren tut es auch ein Archiv mit erfundener Post:

```bash
python werkzeuge/vorfuehrarchiv.py ~/Probearchiv
```

## 1. Installieren

```bash
git clone https://github.com/Stephan-Lefty/MailBurg.git
cd MailBurg
pip install ".[server,imap,anhaenge,packen]"
```

**Ohne `oberflaeche`.** Das sind hundertfünfzig Megabyte Qt für ein
Fenster, das auf einem Server niemand öffnet.

## 2. Der Tresor: Passwörter ohne Schlüsselbund

**Dieser Schritt ist nicht optional**, wenn der Server Post holen soll.
Der Schlüsselbund des Betriebssystems hängt an einer Anmeldesitzung –
ein Dienst läuft ohne. Ohne Tresor läuft MailBurg, holt aber nichts.

```bash
mailburg tresor schluessel
```

Der Befehl gibt einen Schlüssel aus und sagt, wohin damit. Kurz gefasst:

```bash
sudo install -d -o root -g mailburg -m 750 /etc/mailburg
mailburg tresor schluessel | tail -n +3 | head -1 | sudo tee /etc/mailburg/schluessel
sudo chmod 640 /etc/mailburg/schluessel
sudo chown root:mailburg /etc/mailburg/schluessel
export MAILBURG_SCHLUESSELDATEI=/etc/mailburg/schluessel
```

> **Bewahren Sie den Schlüssel zusätzlich außerhalb des Servers auf.**
> Ohne ihn sind die abgelegten Passwörter verloren, und alle Postfächer
> müssen neu eingerichtet werden.

**Die Postfächer** richten Sie danach wie gewohnt ein
(`mailburg konten hinzufuegen …`) – die Passwörter landen dann von
selbst im Tresor statt im Schlüsselbund.

Wer sie schon auf einem Arbeitsplatz eingerichtet hat, übernimmt sie
dort:

```bash
mailburg tresor uebernehmen      # auf dem Arbeitsplatz
```

Die entstandene Datei (`~/.config/mailburg/tresor.json`) gehört dann auf
den Server. **Sie und der Schlüssel nicht denselben Weg schicken** – wer
beides zusammen abfängt, hat die Postfächer.

Zum Schluss die Probe:

```bash
mailburg tresor pruefen
```

## 3. Zugänge anlegen

Ohne Zugang kommt niemand über die Anmeldeseite hinaus.

```bash
mailburg zugaenge /var/lib/mailburg/Archiv hinzufuegen chef \
    --anzeigename "Vorname Nachname" --alle --verwalter
```

Das Passwort wird abgefragt, nie als Argument übergeben – sonst stünde
es in der Prozessliste und im Verlauf der Shell.

Weitere Zugänge mit eingeschränkter Sicht:

```bash
mailburg zugaenge /var/lib/mailburg/Archiv hinzufuegen anna \
    --anzeigename "Anna Feldmann" --postfach buchhaltung --postfach einkauf
```

**Zwei Rechte, die nicht dasselbe sind.** `--verwalter` darf Zugänge
anlegen und Rechte vergeben. `--alle` darf jede Post lesen. Wer die
Technik betreut, muss keine Geschäftspost lesen dürfen.

Nachsehen, was gilt:

```bash
mailburg zugaenge /var/lib/mailburg/Archiv liste
```

Die Liste benennt ausdrücklich zwei Fälle, die sonst niemandem
auffallen: **»sieht nichts«** (angelegt, aber ohne Postfächer) und
**»KEIN PASSWORT«**. Beide sehen in einer Aufzählung aus wie fertige
Zugänge.

## 4. Den Dienst starten

Erst von Hand, um die Einstellungen zu prüfen:

```bash
MAILBURG_ARCHIV=/var/lib/mailburg/Archiv mailburg server
```

Dann im Browser `http://127.0.0.1:8383/`. Unter `/zustand` steht, was
der Dienst über sich weiß – und was ihm fehlt.

**In der Vorgabe lauscht er nur auf dem eigenen Rechner.** Das ist
Absicht: Ein Archivdienst, der beim ersten Start ungefragt im ganzen
Netz steht, wäre eine böse Überraschung.

## 5. Als Dienst einrichten

### Debian

Die Vorlage liegt bei:

```bash
sudo adduser --system --group --home /var/lib/mailburg mailburg
sudo cp werkzeuge/mailburg-server.service /etc/systemd/system/
sudoedit /etc/systemd/system/mailburg-server.service   # Pfade anpassen
sudo systemctl daemon-reload
sudo systemctl enable --now mailburg-server
systemctl status mailburg-server
```

Darin steckt mehr als der Start: ein eigener Benutzer statt root,
`ProtectSystem=strict`, `Restart=on-failure` – und der Hauptschlüssel
über `LoadCredential=`, so dass er weder in der Prozessliste noch im
Dateisystem des Dienstes steht.

### Windows Server 2025

*Ungeprüft – siehe den Hinweis oben.*

```
pip install "mailburg[server-windows]"
setx /M MAILBURG_ARCHIV C:\MailBurg\Archiv
setx /M MAILBURG_SCHLUESSELDATEI C:\MailBurg\schluessel
python -m mailburg.server.windows_dienst install
python -m mailburg.server.windows_dienst start
```

Der Dienst erscheint danach in `services.msc` als *MailBurg Server
Edition*. Neustart nach einem Absturz richtet man dort ein oder mit
`sc failure MailBurgServer reset= 86400 actions= restart/10000`.

**Lassen Sie beim ersten Mal `mailburg server` von Hand danebenlaufen.**
Ein Dienst, der nicht startet, sagt in `services.msc` nur, dass er nicht
startet.

## 6. Erreichbar machen

Bis hierher lauscht der Dienst nur lokal. Für das Firmennetz:

```
MAILBURG_ADRESSE=0.0.0.0
```

**Aber nicht ohne das Folgende.** Der Dienst spricht HTTP, nicht HTTPS.
Ohne Verschlüsselung gehen Anmeldename und Passwort im Klartext über
das Netz.

Davor gehört ein Reverse Proxy mit TLS – nginx oder Caddy unter Debian,
IIS unter Windows. Caddy besorgt sich das Zertifikat von selbst:

```
archiv.example.org {
    reverse_proxy 127.0.0.1:8383
}
```

Der Dienst bleibt dabei auf `127.0.0.1`; nur der Proxy ist von außen
erreichbar.

> **Für den Zugang von unterwegs ist ein VPN der bessere Weg** als eine
> Portfreigabe im Router. Ein Archiv mit zwanzig Jahren Geschäftspost
> ist ein lohnenderes Ziel als das, was sonst so im Netz steht. Wenn es
> doch öffentlich sein muss: HTTPS erzwingen, HSTS setzen, und die
> Anmeldeseite hinter eine zusätzliche Hürde stellen.

## Wenn etwas klemmt

**»Auf 127.0.0.1:8383 lauscht schon etwas«** – ein zweiter Server läuft
noch. `ss -ltnp | grep :8383` zeigt, welcher.

**»In … liegt kein MailBurg-Archiv«** – der Pfad zeigt auf einen Ordner
ohne `archive.json`. Häufig eine Ebene zu hoch oder zu tief.

**Die Anmeldung klappt, aber es gibt keine Treffer** – der Zugang ist
angelegt, aber ohne Postfächer. `mailburg zugaenge … liste` zeigt dann
»sieht nichts«.

**Der Dienst läuft, holt aber keine Post** – der Tresor fehlt oder der
Hauptschlüssel stimmt nicht. `/zustand` sagt es, `mailburg tresor
pruefen` auch.

**Nach einem Neustart sind alle abgemeldet** – so gedacht. Der
Sitzungsschlüssel entsteht beim Start und wird nicht aufbewahrt.
