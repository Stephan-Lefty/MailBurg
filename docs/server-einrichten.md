[Übersicht](../README.md) | [Anleitungen](README.md) | [Der Entwurf dahinter](server.md)

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../assets/server/banner-dark-1600.png">
    <img src="../assets/server/banner-1600.png" alt="MailBurg im Browser – E-Mails. Sicher bewahrt." width="620">
  </picture>
</p>

# Das Archiv im Browser einrichten

Vom leeren Server bis zum Archiv im Browser. Rechnen Sie mit einer
halben Stunde.

**Was am Ende steht:** Ein Dienst, der ein Archiv im Netz bereitstellt.
Mehrere Menschen melden sich an und sehen jeweils die Postfächer, die
ihnen zugeordnet sind. Post geholt wird weiterhin im Hintergrund.

**Was noch nicht geht:** Schreiben. Einstufen, Löschen und das
Zurücklegen ins Postfach bleiben vorerst der Kommandozeile und dem
Fenster vorbehalten.

> **Stand der Erprobung.** Für Debian ist dieser Ablauf durchgespielt.
> Unter Windows Server 2025 lief er am 02.10.2026 zum ersten Mal – und
> förderte zwei Fehler zutage, die inzwischen behoben sind. Ungeprüft
> bleibt, ob der Dienst einen Neustart übersteht und ob er als
> LocalSystem an den Tresor kommt.

> **Für Windows gibt es eine eigene Seite.**
> [MailBurg auf einem Windows Server](server-windows.md) – vom leeren
> Server bis zum Archiv im Browser, am 02.10.2026 auf Windows Server
> 2025 durchgespielt. Diese Seite hier beschreibt den Weg unter Debian
> und anderen Linux-Systemen, wo der Dienst über systemd läuft.

## Unter Windows geht es auch ohne Befehle

Es gibt ein Fenster, das alles von dieser Seite abfragt, prüft und
einrichtet:

```
mailburg-server-einrichten
```

Oder, wenn Sie die fertige Datei geladen haben, ein Doppelklick auf
`MailBurg-Server-Einrichten.exe` – **mit Rechtsklick → »Als
Administrator ausführen«**, sonst bleiben Dienst und systemweite
Einstellungen gesperrt.

Das Fenster zeigt eine Prüfliste: Betriebssystem, Python, Pakete,
Rechte, Archiv, Zugänge, Dienst, Weboberfläche. Wo etwas fehlt, steht
der Knopf daneben, der es behebt. Und es holt die Meldungen des Dienstes
aus dem Windows-Ereignisprotokoll – dort steht, warum ein Start
fehlschlägt, und bis dahin musste man wissen, dass es dieses Protokoll
überhaupt gibt.

Für Skripte und Fehlerberichte gibt es dieselbe Liste als Text:

```
MailBurg-Server-Einrichten.exe --pruefen
```

### Der Suchindex gehört beiden

**Das ist der Punkt, an dem ein Serverbetrieb still scheitert.** Der
Suchindex liegt nicht im Archiv, sondern in einem Ordner, der am
*Benutzer* hängt. Auf einem Arbeitsplatz ist das richtig. Auf einem
Server legt aber ein Mensch das Archiv an, und ein Dienst liest es – und
unter Windows läuft der als `LocalSystem`, mit einem eigenen Profil tief
unter `C:\Windows\System32`.

Die Folge: Der Dienst findet einen leeren Index. Die Anmeldung geht, denn
die Zugänge liegen im Archiv. Jede Suche bleibt leer. **Nichts daran
sieht nach einem Fehler aus** – es sieht aus wie ein Archiv, in dem
nichts ist.

Deshalb gibt es `MAILBURG_DATEN`. Wer sie setzt, legt den Index-Ort fest,
und zwar für beide:

```
MAILBURG_DATEN=C:\MailBurg-Daten
```

Diese Zeile gehört zu den Umgebungsvariablen des Dienstes. Und wer
danach `mailburg neuaufbau` laufen lässt, setzt sie vorher auch in seiner
eigenen Sitzung – sonst baut er den Index wieder an seinen eigenen Platz.

Die Statusseite meldet es inzwischen von selbst: Ist der Index leer,
während im Journal Einträge stehen, erscheint das unter »Sorgen«.

**Der Rest dieser Seite beschreibt denselben Weg von Hand.** Er gilt
weiterhin: unter Linux, wo der Dienst über systemd läuft, und überall
dort, wo jemand lieber sieht, was passiert.

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
sudo install -d -o root -g mailburg -m 750 /etc/mailburg
sudo mailburg tresor schluessel --datei /etc/mailburg/schluessel
sudo chown root:mailburg /etc/mailburg/schluessel
sudo chmod 640 /etc/mailburg/schluessel
export MAILBURG_SCHLUESSELDATEI=/etc/mailburg/schluessel
```

**`--datei` statt abtippen oder durchleiten**, und das aus zwei Gründen.
Ein `echo 'ZW4PjJ…' > datei` hinterlässt den Hauptschlüssel im Klartext
in `~/.bash_history` – in einer Datei, die mitgesichert wird und neben
der die Tresordatei nichts mehr schützt. Und ein
`… | tail -n +3 | head -1 | sudo tee …`, wie es hier bis zum 02.10.2026
stand, hängt daran, in welcher Zeile der Schlüssel steht: Kommt ein Satz
dazu, schreibt derselbe Befehl stillschweigend etwas anderes in die
Datei.

Der Befehl legt die Datei mit `600` an; die beiden Zeilen danach nehmen
die Gruppe `mailburg` hinzu, damit der Dienst mitlesen darf. Einen
vorhandenen Schlüssel überschreibt er nicht – damit wären alle
abgelegten Passwörter auf einen Schlag unlesbar.

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

**Für Postfächer mit OAuth2 ist das der einzige Weg.** Eine
OAuth2-Anmeldung führt über einen Browser auf demselben Rechner, den es
auf einem Server nicht gibt. `uebernehmen` nimmt diese Anmeldungen
deshalb mit – **dafür braucht der Arbeitsplatz mindestens Fassung
1.3.1**, ältere lassen sie liegen. Läuft eine Anmeldung später ab, wird
sie am Arbeitsplatz erneuert und der Tresor erneut übertragen; für ein
Postfach, das dauerhaft hier archiviert wird, ist ein App-Passwort der
ruhigere Weg – **außer bei Microsoft**, wo es keines mehr gibt und die
erneuerte Anmeldung der einzige Weg bleibt. Siehe [oauth2.md](oauth2.md).

Zum Schluss die Probe:

```bash
mailburg tresor pruefen
```

### Wenn das Archiv verschlüsselt ist

Dann braucht der Dienst außerdem das Archivpasswort – **sonst läuft er
und liefert nichts aus.** Auf einem Server sitzt niemand, den er fragen
könnte.

Als der Benutzer, unter dem der Dienst läuft:

```bash
mailburg passwort hinterlegen /var/lib/mailburg/Archiv
```

Das legt es in denselben Tresor. Wo das nicht passt – etwa unter systemd
mit `LoadCredential=` –, geht es auch über eine Datei:

```bash
MAILBURG_ARCHIVPASSWORTDATEI=/etc/mailburg/archivpasswort
```

**Nachsehen lässt sich das später unter `/zustand`**: Ist das Archiv
verschlüsselt und kein Passwort hinterlegt, steht dort die deutlichste
Sorge, die diese Seite kennt.

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

**In der Vorgabe lauscht er nur auf dem eigenen Rechner** – auf
`127.0.0.1`, Anschluss 8383. Das ist Absicht: Ein Archivdienst, der beim
ersten Start ungefragt im ganzen Netz steht, wäre eine böse
Überraschung.

### Und wie sieht man ihn dann?

Auf einem Server ohne Bildschirm gibt es weder Arbeitsumgebung noch
Browser. `127.0.0.1` ist dort zwar erreichbar – nur eben von niemandem.

**Der SSH-Tunnel ist der Weg.** Der Befehl läuft auf dem *eigenen*
Rechner, nicht auf dem Server:

```bash
ssh -L 8383:127.0.0.1:8383 benutzer@server
```

Solange diese Verbindung offen ist, führt `http://127.0.0.1:8383/` im
eigenen Browser auf den Dienst des Servers. Unter `/zustand` steht, was
er über sich weiß – und was ihm fehlt.

Das ist nicht nur ein Notbehelf für den ersten Start: Es ist verschlüsselt,
es braucht kein Zertifikat, und **auf dem Server bleibt nichts offen.** Ist
die SSH-Sitzung beendet, ist auch der Zugang wieder zu. Wer den Dienst nur
selten und allein braucht, kommt damit dauerhaft aus und kann Abschnitt 6
überspringen.

**Ganz ohne Browser** beantwortet auch der Server selbst die Frage, ob
etwas läuft:

```bash
curl -s http://127.0.0.1:8383/zustand.json
```

Dieselben Angaben, maschinenlesbar – für ein Überwachungssystem ist das
die richtige Adresse. Was es nicht beantwortet: ob die Anmeldeseite
aussieht wie gedacht.

> **Nicht als erste Probe:** `MAILBURG_ADRESSE=0.0.0.0`. Damit lauscht
> der Dienst auf allen Netzwerkadressen und ist ohne Tunnel erreichbar –
> aber er spricht HTTP. Anmeldename und Passwort gingen im Klartext
> übers Netz. Das ist der Weg aus Abschnitt 6, und dort gehört ein
> Reverse Proxy mit TLS davor.

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

In einer PowerShell **als Administrator**, nach `git clone` und im
entstandenen Verzeichnis:

```
py -m pip install ".[server-windows,imap,anhaenge,packen]"
py Scripts\pywin32_postinstall.py -install
setx /M MAILBURG_ARCHIV C:\MailBurg\Archiv
setx /M MAILBURG_SCHLUESSELDATEI C:\MailBurg\schluessel
py -m mailburg.server.windows_dienst install
py -m mailburg.server.windows_dienst start
```

**Der Punkt vor dem Schrägstrich ist auch hier wichtig** – MailBurg liegt
nicht auf PyPI, ein `pip install "mailburg[…]"` findet nichts. Die zweite
Zeile meldet die DLLs von pywin32 systemweit an; ohne sie startet
erfahrungsgemäß kein Dienst.

**`setx` wirkt erst in neu geöffneten Fenstern.** Zwischen den beiden
`setx`-Zeilen und `install` gehört deshalb ein frisches
Administrator-Fenster – sonst sucht der Dienst ein Archiv, von dem er
nichts weiß.

Der Dienst erscheint danach in `services.msc` als *MailBurg Server
Edition*. Neustart nach einem Absturz richtet man dort ein oder mit
`sc failure MailBurgServer reset= 86400 actions= restart/10000`.

**Lassen Sie beim ersten Mal `mailburg server` von Hand danebenlaufen.**
Ein Dienst, der nicht startet, sagt in `services.msc` nur, dass er nicht
startet.

## 6. Erreichbar machen

Bis hierher lauscht der Dienst nur auf dem Rechner, auf dem er läuft.
Wer ihn von woanders erreichen will, hat fünf Wege – und welcher richtig
ist, hängt davon ab, woher »woanders« ist und für wie viele Menschen.

| Weg | Wofür | Dagegen spricht |
|---|---|---|
| **SSH-Tunnel** | eine Person, die ohnehin SSH hat | für jeden Zugriff erst eine Sitzung aufbauen; für ein Team untauglich |
| **Reverse Proxy im Firmennetz** | alle sitzen im selben Netz | von außerhalb nicht erreichbar |
| **Vorhandenes Firmen-VPN** | es gibt schon eines | MailBurg ändert nichts daran – aber jemand muss es betreuen |
| **Tailscale** | in einer Minute eingerichtet, auch von unterwegs | hängt an einem Anbieter; ab etwa fünf Zugängen kostenpflichtig |
| **Öffentlich im Internet** | von überall, ohne Zutun der Nutzer | jede Lücke ist weltweit erreichbar |

**Die kurze Antwort:** Für sich allein der SSH-Tunnel aus Abschnitt 4 –
er ist schon da. Im Firmennetz der Reverse Proxy. Von unterwegs ein VPN
– das vorhandene, sonst Tailscale. Öffentlich nur, wenn alles andere
ausscheidet.

### Im Firmennetz

Der einfache Fall. Der Dienst lauscht auf allen Adressen:

```
MAILBURG_ADRESSE=0.0.0.0
```

**Aber nicht ohne TLS davor.** Der Dienst spricht HTTP; ohne
Verschlüsselung gehen Anmeldename und Passwort im Klartext über das
Netz – und in einem Firmennetz sitzt nicht nur, wer dort hingehört.

Davor gehört ein Reverse Proxy: nginx oder Caddy unter Debian, IIS unter
Windows. Mit Caddy sind es drei Zeilen:

```
archiv.firma.intern {
    reverse_proxy 127.0.0.1:8383
}
```

**Dann bleibt der Dienst auf `127.0.0.1`** und `MAILBURG_ADRESSE` bleibt
unangetastet – nur der Proxy ist erreichbar. Das ist die bessere
Aufteilung: Der Proxy kümmert sich um Zertifikate, Protokoll und
Anfragenbegrenzung, MailBurg um das Archiv.

**Dafür:** Nichts zu installieren auf den Arbeitsplätzen, kein Konto bei
Dritten, keine laufenden Kosten. Die Nutzer merken nichts – sie tippen
eine Adresse ein.

**Dagegen:** Von außerhalb des Netzes geht gar nichts. Wer im
Homeoffice sitzt oder beim Kunden, kommt nicht heran. Und im internen
Netz braucht ein Zertifikat entweder eine eigene Zertifizierungsstelle
oder einen öffentlichen Namen, den die Firma besitzt – sonst warnt
jeder Browser.

### Von unterwegs: über ein VPN

**Das ist der empfohlene Weg.** Der Dienst bleibt, wo er ist; das VPN
bringt die Menschen hinein, statt das Archiv hinaus.

Hat die Firma schon ein VPN, ändert sich an MailBurg gar nichts.

Sonst ist **Tailscale** in einer Minute eingerichtet. Ein Befehl auf dem
Server:

```bash
tailscale serve 8383
```

Danach ist das Archiv unter `https://servername.tailnet.ts.net`
erreichbar – **nur für Geräte im eigenen Tailnet**, mit HTTPS ohne
eigenes Zertifikat und ohne eine Portfreigabe im Router. Der Dienst
selbst bleibt auf `127.0.0.1`; von außen ist nichts offen. Beim ersten
Aufruf führt der Befehl durch das Einschalten der Zertifikate.

Zwei Dinge, bevor das für eine Firma entschieden wird:

**Es hängt an einem Anbieter.** Der Datenverkehr läuft verschlüsselt und
direkt zwischen den Geräten, aber die Vermittlung übernimmt ein Dienst
Dritter. Bei Geschäftspost ist das eine Überlegung wert. Wer denselben
Aufbau selbst betreiben will, nimmt **Headscale**.

**Und es kostet ab einer gewissen Zahl von Nutzern.** Bei fünfzig
Zugängen ist der kostenlose Bereich verlassen; die Preisstufen ändern
sich, das gehört vorher nachgerechnet.

> **Nicht verwechseln:** `tailscale funnel` stellt denselben Dienst ins
> offene Internet. Für ein Mailarchiv ist das der falsche Befehl.

**Dafür:** Nichts steht offen im Netz – der Dienst bleibt auf
`127.0.0.1`, es gibt keine Portfreigabe im Router und kein Zertifikat zu
verwalten. Wer keinen Zugang zum Netz hat, sieht die Anmeldeseite gar
nicht erst. Und ein VPN schützt auch dann noch, wenn in MailBurg selbst
einmal eine Lücke steckt.

**Dagegen:** Auf jedem Gerät muss etwas installiert und eingerichtet
werden – bei fünfzig Menschen ist das eine Ansage. Bei Tailscale kommt
die Abhängigkeit von einem Anbieter dazu und, ab einer gewissen Zahl,
die Rechnung. Ein selbst betriebenes VPN kostet stattdessen Arbeit:
Es muss jemand pflegen, aktualisieren und im Zweifel nachts wieder
zum Laufen bringen.

### Öffentlich – nur wenn es sein muss

Technisch derselbe Reverse Proxy wie im Firmennetz, nur mit einem Namen,
den die ganze Welt auflösen kann.

**Davon ist abzuraten, solange einer der beiden anderen Wege möglich
ist.** Nicht weil MailBurg schlecht wäre, sondern weil dann jede Lücke
in Starlette, uvicorn oder MailBurg selbst aus dem ganzen Internet
erreichbar ist – vor einem Archiv mit zwanzig Jahren Geschäftspost. Das
ist ein lohnenderes Ziel als das meiste, was sonst im Netz steht.

Wenn es doch sein muss, gehört dazu:

* **HTTPS erzwingen**, HTTP nur als Weiterleitung, HSTS setzen.
* **Anmeldeversuche auch auf Proxy-Ebene bremsen.** MailBurg begrenzt
  sie je Anmeldename; der Proxy sollte es je Herkunftsadresse tun.
* **Updates nicht schleifen lassen** – auch die von Starlette und
  uvicorn, nicht nur die von MailBurg.
* Und die Überlegung, ob das Archiv wirklich öffentlich erreichbar sein
  muss oder ob ein VPN für die drei Leute genügt, die es von unterwegs
  brauchen.

**Dafür:** Es funktioniert von überall, ohne dass jemand etwas
installiert. Ein Link genügt, auch auf einem fremden Rechner. Für
Menschen, die selten und von wechselnden Orten zugreifen, ist das der
einzige bequeme Weg.

**Dagegen:** Alles, was am Dienst offensteht, steht der ganzen Welt
offen – MailBurg, Starlette, uvicorn, der Proxy. Wer eine dieser
Schichten nicht zeitnah aktualisiert, hat irgendwann ein Problem, von
dem er nichts weiß. Dazu kommen ständige Anmeldeversuche von Fremden:
Sie sind erwartbar, sie kommen ab dem ersten Tag, und sie hören nicht
mehr auf.

**Ein Zwischenweg, der beides mildert:** öffentlich erreichbar, aber
hinter einer zweiten Hürde – Client-Zertifikate im Proxy, eine
zusätzliche Anmeldung auf Proxy-Ebene oder eine Beschränkung auf
bekannte Herkunftsadressen. Dann ist der Dienst nicht mehr ohne
weiteres auffindbar, und die Anmeldeseite von MailBurg ist nicht das
Einzige zwischen einem Fremden und dem Archiv.

## Wenn etwas klemmt

**»Auf 127.0.0.1:8383 lauscht schon etwas«** – ein zweiter Server läuft
noch. `ss -ltnp | grep :8383` zeigt, welcher.

**»Verbindung abgelehnt«, obwohl der Dienst läuft** – der Browser sitzt
auf einem anderen Rechner als der Dienst. In der Vorgabe nimmt der
Dienst nur Anfragen vom eigenen Rechner an; dafür ist der SSH-Tunnel aus
Abschnitt 4 da. Läuft der Tunnel und es klemmt trotzdem, sehen Sie **auf
dem Server** mit `ss -ltnp | grep mailburg` nach, auf welchem Anschluss
er wirklich lauscht – steht `MAILBURG_PORT` auf etwas anderem als 8383,
muss die rechte Hälfte des `-L` dieselbe Nummer nennen.

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
