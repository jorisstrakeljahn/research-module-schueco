# Review Projektbericht „Forschungsmodul" (Stand: Forschungsmodul.docx, 13.07.2026)

Geprüft wurden: Rechtschreibung/Grammatik, Zahlenkonsistenz (inkl. Abgleich mit dem Code und den
Evaluationsdaten im Repo), roter Faden, innere Widersprüche und formale Vollständigkeit.

---

## Fazit: Kann ich das so abgeben?

**Noch nicht ganz – aber du bist nah dran.** Inhaltlich ist der Bericht stark: Der rote Faden von
Problemstellung → Theorie → System → PoC → Evaluation → Fazit ist sauber durchgezogen, die
Forschungsfrage wird ehrlich (inkl. Limitationen) beantwortet, und praktisch alle technischen
Behauptungen im Bericht sind durch den Code gedeckt (ich habe ~19 Kernaussagen gegen das Repo
geprüft – Details unten). Die Evaluationszahlen (10/11 Relevanz = 5, 5 aktiv / 6 nicht aktiv
beobachtet, 4/5 Gesamtqualität) sind in sich konsistent zwischen Tabellen, Text und Fazit.

**Aber:** Es gibt einen echten Zahlenwiderspruch (11 vs. 18 Trends), eine fehlende Literaturquelle
(Cronau 2026), eine verrutschte Tabellennummerierung und eine Eigenständigkeitserklärung in der
Wir-Form. Diese vier Punkte würde ein Prüfer mit hoher Wahrscheinlichkeit finden. Nach Abarbeitung
der Kategorie A (und idealerweise B) ist der Bericht abgabebereit.

---

## A – Kritisch: Muss vor Abgabe behoben werden

### A1. Widerspruch: 11 vs. 18 Trends (Kapitel 3.5.3 und 3.6.3)

- Der Bericht schreibt zweimal, der Analyselauf habe aus 280 Dokumenten **11 Themen** erzeugt
  (3.5.3: „aus denen das System 11 Themen ableitete", 3.6.3: „erzeugte das System 11 Themencluster").
- Deine **eigenen Screenshots im Bericht** (Abbildung 13, Dashboard) zeigen aber
  **„18 identified trends"** und in der Fußzeile **„280 documents, 18 topics"**.
- Die Repo-Daten bestätigen: Run 7 (`data/demo.sql`, `backend/scripts/eval/_out/chart_data.json`)
  hat 280 Dokumente und **18 Topics**. Die **11 Trends aus Tabelle 5 (Evaluation)** sind eine
  Teilmenge dieser 18 (z. B. fehlen dort „Integrated Solar Solutions", „Smart Buildings",
  „Digital Twins", „IoT/5G").
- **Fix:** Formuliere um, z. B.: „Der Lauf verdichtete 280 Dokumente zu 18 Themenclustern; für die
  Expertenevaluation wurden daraus 11 Trends ausgewählt" (bzw. so, wie die Auswahl tatsächlich
  zustande kam). Betroffen: 3.5.3 (auch der Absatz am Kapitelende mit „11 strukturierten und
  bewerteten Trends"), 3.6.3, und im Fazit prüfen, ob „elf" konsistent als Evaluationsmenge
  bezeichnet wird.
- Randnotiz dazu: Das Detail-Beispiel „Integrated Solar Solutions" (3.5.3, Abb. 15) ist **nicht**
  unter den 11 evaluierten Trends – das ist okay, sollte dir aber bewusst sein, falls danach
  gefragt wird.

### A2. Fehlende Literaturquelle: Cronau (2026)

- In Tabelle „Chancen" (Zeile „Erste Denkanstöße") und Tabelle „Grenzen" (Zeile „Veralteter
  Wissenstand") wird **(Cronau, 2026)** zitiert – die Quelle **fehlt komplett im
  Literaturverzeichnis**. Eintrag ergänzen.

### A3. Tabellennummerierung verrutscht (Verzeichnis vs. Fließtext)

- Das Tabellenverzeichnis führt 6 Tabellen und fasst „Chancen und Grenzen" als **eine** Tabelle 1
  zusammen. Im Dokument sind es aber **zwei** Tabellen mit eigenen Beschriftungen („Chancen von…",
  „Grenzen von…") – also real 7 Tabellen.
- Die Fließtextverweise zählen bereits mit 7 („siehe Tabelle 3" für die DSR-Tabelle in 3.4,
  „Tabelle 4 fasst…" für die Dimensionstabelle in 3.4.4), das Verzeichnis aber mit 6
  (dort ist DSR = Tabelle 2, Dimensionen = Tabelle 3).
- **Fix:** In Word alle Felder aktualisieren (Strg+A, dann F9) und danach **jeden**
  Tabellen-/Abbildungsverweis im Text gegen die Beschriftungen prüfen. Achtung: Einige
  Abbildungsbeschriftungen scheinen die Nummer **hart eingetippt** zu haben (z. B. „Abbildung 3:",
  „Abbildung 11:", „Abbildung 13:", „Abbildung 16:", „Abbildung 17:", „Abbildung 19:"), andere
  nutzen das automatische Nummernfeld – das gemischte Vorgehen ist fehleranfällig, bitte
  vereinheitlichen.

### A4. Eigenständigkeitserklärung

- „Hiermit versichern **wir**, dass **wir** die **vorliegenden Seminararbeit**…" –
  1) Wir-Form bei (vermutlich) Einzelautor → „ich",
  2) „die vorliegend**e** Seminararbeit" (Grammatik),
  3) prüfen, ob „Seminararbeit" die richtige Bezeichnung ist (es ist ein Projektbericht im
  Forschungsmodul) – ggf. offizielle HSBI-Formulierung verwenden.

---

## B – Wichtig: Sollte vor Abgabe behoben werden

### B1. Kaputte / unvollständige Sätze

| Stelle | Problem | Vorschlag |
|---|---|---|
| 3.5.3, Einleitung | „…entlang der drei zentralen Ansichten: **Der Anwendung, dem** Dashboard, dem Newsfeed und dem Radar…" – vier Elemente angekündigt als drei, „Der Anwendung" hängt in der Luft | „…entlang der drei zentralen Ansichten der Anwendung: dem Dashboard, dem Newsfeed und dem Radar…" |
| 3.5.3, Dashboard | „Einmal die Gesamtzahl der identifizierten Trends, **im dargestellten Lauf** sowie die Anzahl…" – die Zahl fehlt, Satz bricht ab | Zahl ergänzen (laut Screenshot 18) oder Einschub streichen |
| 3.5.1, letzter Absatz | „…dass die erzeugten Ergebnisse nahtlos an die … Trendradar-Logik **anlehnt** und somit **unmittelbar durch die Passgenauigkeit direkt**…" – Kongruenzfehler + doppelt gemoppelt | „…dass die erzeugten Ergebnisse nahtlos an die … Trendradar-Logik **angelehnt sind** und somit direkt in die bestehenden Foresight-Strukturen eingebunden werden können." |
| 2.4.3 | „Tabelle 1 und 2 zeigen eine komprimierte und **übersichtlichen** Darstellung" | „übersichtliche"; Nummern nach A3 prüfen |
| 2.4.3, Chancen-Tabelle | Zeile „Skalierbarkeit & Geschwindigkeit": Beschreibung endet mit „…werden automatisiert und **übertreffen**" – Satz scheint abgeschnitten | Satz vervollständigen („…übertreffen manuelle Verfahren deutlich" o. ä.) |

### B2. Rechtschreib-/Grammatikfehler (konkrete Fundliste)

| Stelle | Fehler | Korrektur |
|---|---|---|
| Tabelle Dimensionen (3.4.4) + 3.5.2 | „**Dinglichkeit**" (2×) | „Dringlichkeit" |
| Tabelle Dimensionen (3.4.4) | „Strategischer **Umfang**" (bei Handlungsstufe) | „Strategischer **Umgang**" (so steht es auch im Fließtext) |
| 3.4.4 | „**sechdimensionale** PESTEL-Analyse" | „sechsdimensionale" |
| 3.4.3 | „Bei der Speicherung **berücksichtig** es" | „berücksichtigt" |
| 3.4 (Ende) | „…wird anschließend in Abschnitt 3.6 **beschreiben**" | „beschrieben" |
| 3.6.1 | „als formative, **expertenbasierten** Bewertung" | „expertenbasierte" |
| 4.1 | „**ein** standardisierte Vergleichsmessung" | „eine standardisierte Vergleichsmessung" |
| 4.2 | „…werden … **protokoliert**" | „protokolliert" |
| 2.4.3, Grenzen-Tabelle | „Veralteter **Wissenstand**" / „festem **Wissenstand**" | „Wissensstand" (2×) |
| 3.5.2 | „Ein Matching ordnet neue Themen **bestehenden Trend** zu" | „bestehenden Trends" |
| 3.5.1 | „…ist es zuvor noch von Relevanz eine Abgrenzung durchzuführen, damit ersichtlich wird welche…" | Kommas fehlen; einfacher: „Zuvor ist jedoch eine Abgrenzung erforderlich, damit ersichtlich wird, welche Funktionen der PoC umfasst und welche Aspekte bewusst ausgeklammert wurden." |
| 3.4.4 | „Tabelle 4 fasst die einzelnen Dimensionen **nochmal** zusammen" | „noch einmal" (Stil) |
| 2.4.1 | „gewinnt … **weitreichend** an Bedeutung" | „zunehmend an Bedeutung" (Stil) |
| Tabellenüberschriften | „KI-gestützten Trendscouting **Systemen**" / „DSR **Methode**" | Durchkopplung: „Trendscouting-Systemen", „DSR-Methode" |

### B3. Zitations-/Literaturverzeichnis-Punkte

- **(Kollmann et al., 2019)** im Text (2.2.2) → Verzeichnis führt **Kollmann, T. (2019)** als
  Einzelautor → im Text „(Kollmann, 2019)".
- **(Ferras et al., 2024)** im Text (2.4.1) vs. „**Ferràs**" im Verzeichnis → Schreibweise angleichen.
- **Nicht zitierte Einträge im Literaturverzeichnis** (APA: nur Zitiertes aufnehmen):
  **Day & Schoemaker (2005)** und **Steinmüller et al. (2022)** werden im Text nirgends zitiert →
  entweder im Text verwenden oder aus dem Verzeichnis streichen.
- 2.3.2, letzter Absatz: Die Aussage, dass praxisorientierte Trendradare Dringlichkeit statt
  Unsicherheit als zweite Achse nutzen, ist mit **(Wulf et al., 2010)** belegt – Wulf et al.
  behandeln aber die Szenarioplanung/Impact-Uncertainty-Grid. Prüfen, ob die Quelle diese Aussage
  wirklich trägt (ggf. anderen Beleg wählen oder als eigene Einordnung kennzeichnen). Dieser Satz
  ist wichtig, weil er die Brücke zu deinem Radar (Impact × Dringlichkeit) schlägt.

### B4. Roter Faden: Teilziel 3 vs. Umsetzung (Unsicherheit vs. Dringlichkeit)

- Teilziel 3 (1.2) fragt nach der Quantifizierung von **Impact und Unsicherheit** und deren
  Darstellung im Trendradar. Das umgesetzte Radar nutzt aber **Impact × Dringlichkeit** (wie bei
  Schüco), die Unsicherheit läuft als separate Transparenzangabe mit.
- Du fängst das an mehreren Stellen ab (2.3.2 Ende, 3.4.4, 3.5.1) – gut. Aber im **Fazit 4.1**
  heißt es nur: „…die Quantifizierung von Impact und **Dringlichkeit** in das Trendradar
  überführt". Damit bleibt Teilziel 3 formal unbeantwortet.
- **Fix:** Im Fazit einen Satz ergänzen, dass die Unsicherheit ebenfalls quantifiziert und als
  separate Transparenzangabe ausgewiesen wird, und warum das Radar bewusst der Schüco-Logik
  (Dringlichkeit) folgt. Alternativ Teilziel 3 in 1.2 minimal umformulieren.

### B5. Kleinere Konsistenzpunkte

- **Zeitangabe vereinheitlichen:** 3.5.3 sagt „rund **1,85 Minuten**", 3.6.7 und 4.1 sagen
  „1 Minute und 51 Sekunden". Beides ist derselbe Wert (Run 7: 09:00:00 → 09:01:50, ✓ korrekt),
  aber „1,85 Minuten" liest sich sperrig → überall „1 Minute und 51 Sekunden" (oder „111 Sekunden").
- **„Schnell-Lauf" vs. „Quick":** 3.4.3 nennt den Modus „Schnell-Lauf", 3.5.3 „Quick". Einmal
  explizit verknüpfen („der Schnell-Lauf, in der Oberfläche als ‚Quick' bezeichnet").
- **Trend-Scouting vs. Trendscouting:** beide Schreibweisen kommen als eigenständiges Wort vor
  (z. B. 1.1 „KI-gestützte Trend-Scouting" vs. Kapitel 2.4 „KI-gestütztes Trendscouting").
  Eine Variante wählen (Komposita wie „Trend-Scouting-System" können bleiben).
- **1.3 (Aufbau):** „Kapitel 4 … benennt die Grenzen der Arbeit" – die Limitationen stehen aber in
  **3.6.7**, Kapitel 4 greift sie nur auf. Formulierung in 1.3 leicht anpassen.
- **3.6.1 vs. 3.6.3 vs. 3.6.7:** erst „eine … vertraute Person", dann „an fachlich eingebundene
  **Personen** übermittelt", dann „nur **eine Expertin**". Das ist erklärbar (an mehrere verschickt,
  ein Rücklauf), sollte aber in einem Halbsatz genau so gesagt werden, sonst wirkt es widersprüchlich.
- **Leere Überschrift vor dem Literaturverzeichnis:** In der Datei existiert eine leere nummerierte
  Überschrift (würde als leeres „Kapitel 5" o. ä. erscheinen) – prüfen und löschen.
- **Abkürzungsverzeichnis:** **DSR** (Design Science Research, ab 3.4 verwendet) fehlt; **BIPV**
  (Tabelle 5, Screenshots) fehlt ebenfalls. Ergänzen.
- **Beschriftungs-Interpunktion:** „Abbildung 4: … Matrix**.**" und „Abbildung 16: … (Teil 2)**.**"
  haben Schlusspunkte, andere nicht → vereinheitlichen.

---

## C – Zur Kenntnis: Was ich geprüft habe und was stimmt

### Zahlen (gegen Repo-Daten verifiziert)

| Aussage im Bericht | Befund |
|---|---|
| 280 Dokumente im dokumentierten Lauf | ✓ (Run 7 in `data/demo.sql` und `chart_data.json`) |
| Verarbeitungszeit ~1:51 Min. | ✓ (09:00:00 → 09:01:50,77 = 110,8 s) |
| Zwei Suchrunden (Deep-Research) | ✓ (`"rounds": 2` in den Run-Parametern) |
| 11 Themen/Trends | ✗ **18** Topics im Lauf; 11 = Evaluations-Teilmenge → siehe A1 |
| „Integrated Solar Solutions": Act, Technology, Megatrend, 21 Dokumente, Emergenz 0,17 | ✓ (chart_data: megatrend, act, size 21, emergence 0,174) |
| „Innovative Building Envelopes" vom System als Prepare eingeordnet (Expertin: eher Act) | ✓ (chart_data: prepare) |
| Evaluationstabelle: 10/11 Relevanz = 5 (Ausnahme Adaptive Reuse), 10/11 Nachvollziehbarkeit = 5 (Ausnahme Servitization), 5 aktiv / 6 nicht aktiv beobachtet | ✓ in sich konsistent (Tabelle ↔ Text ↔ Fazit) |
| Dashboard: „7 Trends needing action" | ✓ (7 Act-Trends in chart_data) |

### Technische Behauptungen (gegen Code verifiziert)

Bestätigt: OpenAlex/arXiv/Firecrawl-Konnektoren mit zentraler Registry und einheitlichem
Dokumentenformat; PostgreSQL + pgvector mit Kosinusmaß; BERTopic auf vorhandenen Embeddings mit
Outlier-Ausschluss; vierstufige Reifegrad-Logik; Quick-/Deep-Research-Modi mit Runden-/Dokument-
Obergrenzen; mehrstufige Deduplizierung (inkl. DOI, kanonisierte URL, Inhalts-Hash, markierte
Near-Duplicates); Heuristik- und LLM-Klassifikation mit JSON-Schema; Act/Prepare/Watch über
Schwellenwerte; deterministische 6-dimensionale PESTEL-Analyse je Portfolio-Trend
(`backend/app/pestel.py`); persistentes Trendportfolio mit Matching und Verlaufsanzeige;
Expert-Review inkl. Vorher-/Nachher-Protokollierung; Feedback-Schleife (Seeds aus Bestätigungen,
Ausschlussterme aus Ablehnungen); alle beschriebenen Frontend-Ansichten inkl. „Building Industry"
statt Economic, DE/EN und Light/Dark; RAG-Beschreibungen (im dokumentierten Lauf war
`describer=openai` aktiv ✓). Auch die „Nicht umgesetzt"-Aussagen stimmen (kein Scheduling, keine
trendspezifische PESTEL-Nachsuche mit LLM-Begründung, keine empirische Gewichtskalibrierung).

Zwei Formulierungen leicht schärfen (kein Muss):

1. **3.4.2 „Sprache und geografische Zuordnung … erkannt":** Der Code übernimmt Sprache/Land aus
   den **Quellmetadaten** (arXiv pauschal „en") statt sie selbst zu erkennen → besser „übernommen
   bzw. zugeordnet" statt „erkannt".
2. **3.4.3 Relevanz-Gate:** Im Code ist das Gate konfigurierbar und standardmäßig deaktiviert
   (Passthrough). Der Bericht sagt korrekt „wahlweise schlüsselwortbasiert oder durch ein LLM",
   beschreibt es aber als festen Prozessschritt. Ein Halbsatz „optional zuschaltbar" wäre exakter.

### Roter Faden / Gesamtbild

Struktur und Argumentation sind stimmig: Theorie (Kap. 2) wird in Kap. 3 konsequent
wiederaufgegriffen (BERTopic-Wahl mit Verweis auf 2.1.3/2.4.2, Reifegrade aus 2.2.1 im System,
PESTEL/Impact-Matrix aus 2.3 im Radar), die DSR-Zuordnung (Tabelle) verankert das Vorgehen
methodisch, und das Fazit bleibt ehrlich bei dem, was die Einzelfall-Evaluation hergibt. Die
Limitationen (3.6.7) sind vorbildlich offen. Keine inhaltlichen Widersprüche gefunden außer A1
und der Teilziel-3-Formulierung (B4).

---

## Checkliste vor Abgabe

1. [ ] A1: 11 vs. 18 Trends auflösen (3.5.3 zweimal, 3.6.3, Fazit prüfen)
2. [ ] A2: Cronau (2026) ins Literaturverzeichnis
3. [ ] A3: Felder aktualisieren (Strg+A → F9), Tabellen-/Abbildungsnummern + alle Querverweise prüfen, hart getippte Abbildungsnummern durch Felder ersetzen
4. [ ] A4: Eigenständigkeitserklärung (ich-Form, Grammatik, Bezeichnung „Seminararbeit")
5. [ ] B1: Die fünf kaputten/unvollständigen Sätze reparieren
6. [ ] B2: Tippfehlerliste abarbeiten (Dinglichkeit ×2, Umfang→Umgang, sechdimensionale, berücksichtig, beschreiben, expertenbasierten, protokoliert, Wissenstand ×2, …)
7. [ ] B3: Kollmann et al.→Kollmann, Ferras→Ferràs, Day & Schoemaker + Steinmüller streichen oder zitieren, Wulf-Beleg in 2.3.2 prüfen
8. [ ] B4: Fazit-Satz zu Teilziel 3 (Unsicherheit) ergänzen
9. [ ] B5: 1,85 Min. vereinheitlichen, Schnell-Lauf/Quick verknüpfen, Trend-Scouting-Schreibweise, 1.3-Aufbausatz, Expertin/Personen-Formulierung, leere Überschrift löschen, DSR + BIPV ins Abkürzungsverzeichnis, Beschriftungspunkte
10. [ ] Optional C: „erkannt"→„übernommen" (3.4.2), Relevanz-Gate „optional zuschaltbar" (3.4.3)
11. [ ] Nach allen Änderungen: Inhalts-, Abbildungs- und Tabellenverzeichnis final aktualisieren und PDF-Export Korrektur lesen
