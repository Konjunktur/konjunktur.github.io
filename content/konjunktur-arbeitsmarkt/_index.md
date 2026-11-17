---
title: "Konjunktur und Arbeitsmarkt in Deutschland nach dem „Automated Business Cycle Dashboard“ von Pascal Michaillat, Emmanuel Saez"
---

Echtzeit-Indikatoren zur Arbeitsmarktanspannung, Vollbeschäftigungsquote (FERU), Beveridge-Kurve und Rezessionswahrscheinlichkeit für Deutschland nach der Methodik von Pascal Michaillat und Emmanuel Saez (*Automated Business Cycle Dashboard*, [pascalmichaillat.org/dashboard](https://pascalmichaillat.org)). Grau hinterlegt sind deutsche Rezessions- und Schwächephasen in Anlehnung an die Konjunkturdatierung von Sachverständigenrat und Bundesbank (Finanzkrise 2008/09, Eurokrise 2012/13, Corona-Pandemie 2020 sowie die dreijährige Stagnations- und Schwächephase von Ende 2022 bis Ende 2025).

**Inhaltsverzeichnis**

- [Arbeitslosenquote (u)](#arbeitslosenquote)
- [Vakanzrate (v)](#vakanzrate)
- [Arbeitsmarktanspannung (v / u)](#arbeitsmarktanspannung)
- [Beveridge-Kurve](#beveridge-kurve)
- [Arbeitslosenquote und Vollbeschäftigungsquote (FERU u*)](#vollbeschaeftigungsquote)
- [Arbeitslosigkeitslücke (u − u*)](#arbeitslosigkeitsluecke)
- [Rezessionsindikator (Michez-Regel)](#rezessionsindikator)
- [Rezessionswahrscheinlichkeit](#rezessionswahrscheinlichkeit)

---

### Arbeitslosenquote {#arbeitslosenquote}

<iframe src="/konjunktur-arbeitsmarkt/u.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/u.png)
- **Konstruktion:** Die Arbeitslosenquote (<i>u</i>) ist die Zahl der registrierten Arbeitslosen geteilt durch alle zivilen Erwerbspersonen (in %).
- **Interpretation:** Sie misst den Anteil der Personen, die eine Beschäftigung suchen, aber noch keine Stelle gefunden haben.
- **Quelle:** Deutsche Bundesbank und Statistisches Bundesamt (Daten der Bundesagentur für Arbeit).

### Vakanzrate {#vakanzrate}

<iframe src="/konjunktur-arbeitsmarkt/v.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/v.png)
- **Konstruktion:** Die Vakanzrate (<i>v</i>) ist die Zahl der bei der Bundesagentur für Arbeit gemeldeten Arbeitsstellen geteilt durch alle zivilen Erwerbspersonen (in %). Durch den identischen Nenner sind <i>u</i> und <i>v</i> konsistent zueinander.
- **Interpretation:** Sie misst die unbesetzten, gemeldeten Stellen je ziviler Erwerbsperson.
- **Quelle:** Deutsche Bundesbank und Statistisches Bundesamt (Daten der Bundesagentur für Arbeit).

### Arbeitsmarktanspannung {#arbeitsmarktanspannung}

<iframe src="/konjunktur-arbeitsmarkt/theta.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/theta.png)
- **Konstruktion:** Die Arbeitsmarktanspannung (<i>θ</i> = <i>v</i> / <i>u</i>) ist das Verhältnis der Vakanzrate zur Arbeitslosenquote.
- **Interpretation:** Sie gibt die Zahl der gemeldeten offenen Stellen je Arbeitslosen an. Liegt <i>θ</i> unter 1, herrscht Unterauslastung am Arbeitsmarkt; über 1 liegt eine Anspannung vor.
- **Quelle:** Eigene Berechnung nach der Methodik von Michaillat und Saez (2024) auf Basis von Daten der Deutschen Bundesbank und des Statistischen Bundesamts.

### Beveridge-Kurve {#beveridge-kurve}

<iframe src="/konjunktur-arbeitsmarkt/bev.html" style="width:100%; height:465px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/bev.png)
- **Konstruktion:** Streudiagramm der Vakanzrate (<i>v</i>) gegen die Arbeitslosenquote (<i>u</i>) inklusive der 45°-Linie (<i>v</i> = <i>u</i>) sowie hyperbolischer Anpassungskurven (<i>v</i> = <i>a</i> + <i>b</i>/<i>u</i>) mit Bestimmtheitsmaß (<i>R</i>²).
- **Interpretation:** Im Konjunkturzyklus bewegt sich die Wirtschaft entlang der Beveridge-Kurve. In Rezessionen steigt die Arbeitslosenquote und die Vakanzrate sinkt (Bewegung nach unten rechts); im Aufschwung verläuft die Bewegung nach oben links. Verschiebungen der Kurve nach außen zeigen strukturelle Friktionen an.
- **Quelle:** Eigene Berechnung nach der Methodik von Michaillat und Saez (2024) auf Basis von Daten der Deutschen Bundesbank und des Statistischen Bundesamts.

### Arbeitslosenquote und Vollbeschäftigungsquote (FERU) {#vollbeschaeftigungsquote}

<iframe src="/konjunktur-arbeitsmarkt/feru.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/feru.png)
- **Konstruktion:** Die Vollbeschäftigungsquote (<i>u</i>*) berechnet sich als geometrisches Mittel aus Arbeitslosenquote und Vakanzrate: <i>u</i>* = √(<i>u</i> × <i>v</i>).
- **Interpretation:** Nach Michaillat und Saez markiert <i>u</i>* die sozial effiziente Arbeitslosenquote, bei der unproduktive Such- und Rekrutierungskosten minimiert werden. Auf der Beveridge-Kurve entspricht <i>u</i>* dem Schnittpunkt mit der 45°-Linie.
- **Quelle:** Eigene Berechnung nach der Methodik von Michaillat und Saez (2024) auf Basis von Daten der Deutschen Bundesbank und des Statistischen Bundesamts.

### Arbeitslosigkeitslücke {#arbeitslosigkeitsluecke}

<iframe src="/konjunktur-arbeitsmarkt/gap.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/gap.png)
- **Konstruktion:** Die Arbeitslosigkeitslücke (<i>u</i> − <i>u</i>*) ist die Differenz zwischen der tatsächlichen Arbeitslosenquote und der Vollbeschäftigungsquote (FERU) in Prozentpunkten.
- **Interpretation:** Ein positiver Wert zeigt Unterauslastung (Rezessions- oder Schwächephase) an; ein negativer Wert signalisiert einen angespannten Arbeitsmarkt über Vollbeschäftigung.
- **Quelle:** Eigene Berechnung nach der Methodik von Michaillat und Saez (2024) auf Basis von Daten der Deutschen Bundesbank und des Statistischen Bundesamts.

### Rezessionsindikator {#rezessionsindikator}

<iframe src="/konjunktur-arbeitsmarkt/rec_ind.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/rec_ind.png)
- **Konstruktion:** Minimum zweier Teilindikatoren: dem Anstieg des 3-Monats-Durchschnitts der Arbeitslosenquote über sein 12-Monats-Tief (Sahm-Komponente) und dem Rückgang des 3-Monats-Durchschnitts der Vakanzrate unter sein 12-Monats-Hoch (in Prozentpunkten).
- **Interpretation:** Der kombinierte Indikator schlägt nur dann an, wenn gleichzeitig die Arbeitslosigkeit steigt und die offenen Stellen sinken. Die beiden gestrichelten Schwellenwerte sind empirisch an den historischen deutschen Rezessionsphasen kalibriert.
- **Quelle:** Eigene Berechnung nach der Methodik von Michaillat und Saez (2025) auf Basis von Daten der Deutschen Bundesbank und des Statistischen Bundesamts.

### Rezessionswahrscheinlichkeit {#rezessionswahrscheinlichkeit}

<iframe src="/konjunktur-arbeitsmarkt/rec_prob.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/rec_prob.png)
- **Konstruktion:** Normierter Anteil der Spanne zwischen unterer und oberer Rezessionsschwelle, den der Rezessionsindikator aktuell erreicht hat (in %).
- **Interpretation:** Liegt der Indikator unter der unteren Schwelle, beträgt die Wahrscheinlichkeit 0 %. Zwischen unterer und oberer Schwelle steigt sie linear bis 100 % an und dient als Echtzeit-Frühindikator (Nowcast) für Rezessionsrisiken in Deutschland.
- **Quelle:** Eigene Berechnung nach der Methodik von Michaillat und Saez (2025) auf Basis von Daten der Deutschen Bundesbank und des Statistischen Bundesamts.
