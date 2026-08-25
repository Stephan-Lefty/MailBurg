#!/usr/bin/env bash
# MailBurg: Einrichtung auf diesem Rechner (Debian- und Arch-basierte
# Systeme, Fedora, openSUSE und macOS).
#
# Aufruf aus dem MailBurg-Ordner heraus:
#
#     ./install.sh                        Programm einrichten
#     ./install.sh --ohne-pakete          Systempakete überspringen
#     ./install.sh --nur-kern             ohne die Kür (IMAP, Anhänge, Packen)
#     ./install.sh --zeitsteuerung ~/Archiv
#                                         laufenden Abruf einrichten, alle 30 min
#     ./install.sh --zeitsteuerung ~/Archiv --alle 10
#                                         ... stattdessen alle 10 Minuten
#     ./install.sh --entfernen            alles wieder abbauen
#
# Nicht als root ausführen – sudo wird nur für die Systempakete gefragt,
# und auch das nur nach Rückfrage.
#
# Das Archiv selbst rührt dieses Skript nie an. Auch --entfernen nimmt nur
# das Programm weg; die Mails bleiben, wo sie sind.
set -euo pipefail

QUELLE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZIEL="$HOME/.local/share/mailburg"
VENV="$ZIEL/venv"
BIN="$HOME/.local/bin"
DIENSTE="$HOME/.config/systemd/user"

MIT_PAKETEN=1
MIT_KUER=1
ZEITSTEUERUNG=""
ENTFERNEN=0

#: Wie oft die Postfächer abgefragt werden. Dreißig Minuten sind der
#: Kompromiss: kurz genug, dass eine Aufräumregel im Mailclient nichts
#: wegräumt, was noch nicht archiviert ist, und lang genug, dass kein
#: Anbieter die häufigen Anmeldungen für einen Angriff hält.
INTERVALL=30

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ohne-pakete) MIT_PAKETEN=0; shift ;;
        --nur-kern) MIT_KUER=0; shift ;;
        --zeitsteuerung) ZEITSTEUERUNG="${2:-}"; shift 2 ;;
        --alle) INTERVALL="${2:-}"; shift 2 ;;
        --entfernen) ENTFERNEN=1; shift ;;
        -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
    esac
done

case "$INTERVALL" in
    10|30|60|90) ;;
    *) echo "Fehler: --alle nimmt 10, 30, 60 oder 90 (Minuten), nicht '$INTERVALL'." >&2; exit 2 ;;
esac

melde()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
hinweis() { printf '  %s\n' "$*"; }
fehler() { printf '\033[31mFehler:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ $EUID -eq 0 ]]; then
    fehler "Bitte nicht als root ausführen. MailBurg wird ins Benutzerverzeichnis eingerichtet."
fi

# ----------------------------------------------------------------- Abbauen

if [[ $ENTFERNEN -eq 1 ]]; then
    melde "MailBurg abbauen"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl --user disable --now mailburg-abruf.timer 2>/dev/null || true
    fi
    rm -f "$DIENSTE/mailburg-abruf.service" "$DIENSTE/mailburg-abruf.timer"
    rm -f "$BIN/mailburg"
    rm -rf "$VENV"
    hinweis "Programm entfernt."
    hinweis "Geblieben sind: Ihr Archiv, die Kontenliste und der Suchindex."
    hinweis "  Kontenliste: ~/.config/mailburg/konten.json"
    hinweis "  Suchindex:   ~/.local/share/mailburg/index/"
    hinweis "Die Passwörter im Schlüsselbund bleiben ebenfalls stehen."
    exit 0
fi

# ------------------------------------------------------------ Systempakete

paketverwaltung() {
    for werkzeug in apt-get pacman dnf zypper brew; do
        if command -v "$werkzeug" >/dev/null 2>&1; then
            echo "$werkzeug"
            return
        fi
    done
    echo ""
}

if [[ $MIT_PAKETEN -eq 1 ]]; then
    melde "Systempakete"
    # Zwei Dinge kann pip nicht liefern, weil sie nicht aus Python bestehen:
    # pdftotext aus poppler (holt Text aus PDF deutlich schneller als pypdf)
    # und einen Schlüsselbund für die Passwörter.
    case "$(paketverwaltung)" in
        apt-get) PAKETE=(poppler-utils gnome-keyring python3-venv) ; BEFEHL="sudo apt-get install -y" ;;
        pacman)  PAKETE=(poppler gnome-keyring)                    ; BEFEHL="sudo pacman -S --needed" ;;
        dnf)     PAKETE=(poppler-utils gnome-keyring)              ; BEFEHL="sudo dnf install -y" ;;
        zypper)  PAKETE=(poppler-tools gnome-keyring)              ; BEFEHL="sudo zypper install -y" ;;
        brew)    PAKETE=(poppler)                                  ; BEFEHL="brew install" ;;
        *)       PAKETE=()                                         ; BEFEHL="" ;;
    esac

    if [[ ${#PAKETE[@]} -eq 0 ]]; then
        hinweis "Keine bekannte Paketverwaltung gefunden – übersprungen."
        hinweis "Von Hand nachrüsten lohnt: poppler (für pdftotext) und einen Schlüsselbund."
    else
        hinweis "Vorgesehen: ${PAKETE[*]}"
        hinweis "Befehl:     $BEFEHL ${PAKETE[*]}"
        read -r -p "  Installieren? [J/n] " antwort
        if [[ ! "$antwort" =~ ^([nN]|[nN]ein)$ ]]; then
            $BEFEHL "${PAKETE[@]}"
        else
            hinweis "Übersprungen. MailBurg läuft auch ohne, nur langsamer bei PDF."
        fi
    fi
fi

# ---------------------------------------------------------------- Programm

melde "MailBurg einrichten"

command -v python3 >/dev/null 2>&1 || fehler "Python 3 ist nicht installiert."
python3 - <<'PY' || fehler "MailBurg braucht Python 3.11 oder neuer."
import sys
sys.exit(0 if sys.version_info >= (3, 11) else 1)
PY
hinweis "Python $(python3 -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])') gefunden."

# Eine eigene Umgebung statt Installation ins System: Viele Distributionen
# lassen pip gar nicht mehr an die Systempakete (PEP 668), und ein Archiv-
# programm hat in den Systemverzeichnissen ohnehin nichts verloren.
mkdir -p "$ZIEL"
python3 -m venv --upgrade-deps "$VENV" >/dev/null
hinweis "Eigene Python-Umgebung unter $VENV"

if [[ $MIT_KUER -eq 1 ]]; then
    "$VENV/bin/pip" install -q "$QUELLE[alles]"
    hinweis "MailBurg mit allem eingerichtet: IMAP, Anhänge im Volltext, Zstandard."
else
    "$VENV/bin/pip" install -q "$QUELLE"
    hinweis "MailBurg im Kern eingerichtet – ohne IMAP-Schlüsselbund und PDF-Text."
fi

mkdir -p "$BIN"
ln -sf "$VENV/bin/mailburg" "$BIN/mailburg"
hinweis "Befehl 'mailburg' liegt in $BIN"

if [[ ":$PATH:" != *":$BIN:"* ]]; then
    hinweis ""
    hinweis "Achtung: $BIN steht nicht im Suchpfad. Diese Zeile hilft:"
    hinweis "    echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc"
fi

# ----------------------------------------------------------- Zeitsteuerung

if [[ -n "$ZEITSTEUERUNG" ]]; then
    melde "Laufender Abruf"

    ARCHIV="$(cd "$(dirname "$ZEITSTEUERUNG")" 2>/dev/null && pwd)/$(basename "$ZEITSTEUERUNG")" \
        || fehler "Das Verzeichnis $ZEITSTEUERUNG gibt es nicht."
    [[ -f "$ARCHIV/archive.json" ]] \
        || fehler "In $ARCHIV liegt kein Archiv. Erst anlegen: mailburg anlegen '$ARCHIV'"

    command -v systemctl >/dev/null 2>&1 \
        || fehler "Ohne systemd keine Zeitsteuerung. Unter macOS geht das über launchd, siehe docs/zeitsteuerung.md."

    mkdir -p "$DIENSTE"
    cat > "$DIENSTE/mailburg-abruf.service" <<EOF
[Unit]
Description=MailBurg: neue Mails ins Archiv holen
# Ohne Netz braucht der Abruf gar nicht erst anzulaufen.
After=network-online.target

[Service]
Type=oneshot
ExecStart=$BIN/mailburg abrufen --leise "$ARCHIV"
# Der Schlüsselbund hängt an der angemeldeten Sitzung. Läuft der Abruf,
# während niemand angemeldet ist, kommt er nicht an die Passwörter.
Environment=PYTHONUNBUFFERED=1
EOF

    cat > "$DIENSTE/mailburg-abruf.timer" <<EOF
[Unit]
Description=MailBurg alle $INTERVALL Minuten abrufen

[Timer]
# Nicht sofort beim Anmelden: Erst soll der Rechner hochkommen.
OnBootSec=5min
# Gerechnet ab dem Ende des letzten Laufs. Damit überholt sich der Abruf
# nie selbst, auch wenn ein Durchgang einmal länger dauert als das
# Intervall - systemd startet die Unit nicht neu, solange sie läuft.
OnUnitActiveSec=${INTERVALL}min
# Damit nicht dreißig Postfächer auf die Sekunde genau gleichzeitig
# angefragt werden.
RandomizedDelaySec=2m
Persistent=true

[Install]
WantedBy=timers.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable --now mailburg-abruf.timer
    hinweis "Eingerichtet für $ARCHIV, alle $INTERVALL Minuten."
    hinweis "Nachsehen:  systemctl --user list-timers mailburg-abruf.timer"
    hinweis "Protokoll:  journalctl --user -u mailburg-abruf.service"
    hinweis "Jetzt gleich: systemctl --user start mailburg-abruf.service"
    hinweis ""
    hinweis "Zweierlei ist dabei zu wissen:"
    hinweis ""
    hinweis "1. Der Abruf kommt nur an die Passwörter, solange Ihr"
    hinweis "   Schlüsselbund entsperrt ist – also während Sie angemeldet sind."
    hinweis "   Nach einem Neustart läuft er erst wieder, wenn Sie sich anmelden."
    hinweis ""
    hinweis "2. Damit der Rechner das auch nachts tut, darf er nicht in den"
    hinweis "   Ruhezustand gehen. Sonst holt MailBurg beim Aufwachen nach –"
    hinweis "   was genügt, solange Ihr Mailclient nicht zwischendurch"
    hinweis "   aufräumt."
fi

# ------------------------------------------------------------------ Fertig

melde "Fertig"
hinweis "Erste Schritte:"
hinweis "    mailburg anlegen ~/Archiv --modus privat"
hinweis "    mailburg konten hinzufuegen Firma --server imap.example.org --benutzer post@example.org"
hinweis "    mailburg abrufen ~/Archiv"
hinweis ""
hinweis "Anleitungen liegen in docs/, die Suchsprache erklärt 'mailburg suchhilfe'."
