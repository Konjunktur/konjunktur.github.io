---
title: "Konjunktur und Arbeitsmarkt in Deutschland nach dem „Automated Business Cycle Dashboard“ von Pascal Michaillat, Emmanuel Saez"
---

Echtzeit-Indikatoren zur Arbeitsmarktanspannung, Vollbeschäftigungs-Arbeitslosenquote (FERU), Beveridge-Kurve und Rezessionswahrscheinlichkeit für Deutschland nach der Methodik von Pascal Michaillat und Emmanuel Saez (*Automated Business Cycle Dashboard*, [pascalmichaillat.org/dashboard](https://pascalmichaillat.org/dashboard/)). Grau hinterlegt sind deutsche Rezessions- und Schwächephasen.

<iframe src="/konjunktur-arbeitsmarkt/u.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/u.png)
- **Konstruktion:** Die Arbeitslosenquote ($u$) ist die Zahl der registrierten Arbeitslosen geteilt durch alle zivilen Erwerbspersonen (in %).
- **Interpretation:** Sie misst den Anteil der Personen, die eine Beschäftigung suchen, aber noch keine Stelle gefunden haben.
- **Quelle:** Deutsche Bundesbank und Statistisches Bundesamt (Daten der Bundesagentur für Arbeit).

<iframe src="/konjunktur-arbeitsmarkt/v.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/v.png)
- **Konstruktion:** Die Vakanzrate ($v$) ist die Zahl der bei der Bundesagentur für Arbeit gemeldeten Arbeitsstellen geteilt durch alle zivilen Erwerbspersonen (in %). Durch den identischen Nenner sind $u$ und $v$ konsistent zueinander.
- **Interpretation:** Sie misst die unbesetzten, gemeldeten Stellen je ziviler Erwerbsperson.
- **Quelle:** Deutsche Bundesbank und Statistisches Bundesamt (Daten der Bundesagentur für Arbeit).

<iframe src="/konjunktur-arbeitsmarkt/theta.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/theta.png)
- **Konstruktion:** Die Arbeitsmarktanspannung ($\theta = v / u$) ist das Verhältnis der Vakanzrate zur Arbeitslosenquote.
- **Interpretation:** Sie gibt die Zahl der gemeldeten offenen Stellen je Arbeitslosen an. Liegt $\theta$ unter 1, herrscht Unterauslastung am Arbeitsmarkt; über 1 liegt eine Anspannung vor. (Hinweis: Da in Deutschland nur gemeldete Stellen erfasst werden, liegt das Niveau strukturell niedriger als in den USA.)
- **Quelle:** Eigene Berechnung nach Michaillat und Saez (2024).

<iframe src="/konjunktur-arbeitsmarkt/bev.html" style="width:100%; height:465px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/bev.png)
- **Konstruktion:** Streudiagramm der Vakanzrate ($v$) gegen die Arbeitslosenquote ($u$) inklusive der 45°-Linie ($v = u$) sowie hyperbolischer Anpassungskurven ($v = a + b/u$) mit Bestimmtheitsmaß ($R^2$).
- **Interpretation:** Im Konjunkturzyklus bewegt sich die Wirtschaft entlang der Beveridge-Kurve. In Rezessionen steigt die Arbeitslosenquote und die Vakanzrate sinkt (Bewegung nach unten rechts); im Aufschwung verläuft die Bewegung nach oben links. Verschiebungen der Kurve nach außen zeigen strukturelle Friktionen an.
- **Quelle:** Eigene Berechnung nach Michaillat und Saez (2024).

<iframe src="/konjunktur-arbeitsmarkt/feru.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/feru.png)
- **Konstruktion:** Die Vollbeschäftigungs-Arbeitslosenquote ($u^\ast$) berechnet sich als geometrisches Mittel aus Arbeitslosenquote und Vakanzrate: $u^\ast = \sqrt{u \times v}$.
- **Interpretation:** Nach Michaillat und Saez markiert $u^\ast$ die sozial effiziente Arbeitslosenquote, bei der unproduktive Such- und Rekrutierungskosten minimiert werden. Auf der Beveridge-Kurve entspricht $u^\ast$ dem Schnittpunkt mit der 45°-Linie.
- **Quelle:** Eigene Berechnung nach Michaillat und Saez (2024).

<iframe src="/konjunktur-arbeitsmarkt/gap.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/gap.png)
- **Konstruktion:** Die Arbeitslosigkeitslücke ($u - u^\ast$) ist die Differenz zwischen der tatsächlichen Arbeitslosenquote und der FERU in Prozentpunkten.
- **Interpretation:** Ein positiver Wert zeigt Unterauslastung (Rezessions- oder Schwächephase) an; ein negativer Wert signalisiert einen angespannten Arbeitsmarkt über Vollbeschäftigung.
- **Quelle:** Eigene Berechnung nach Michaillat und Saez (2024).

<iframe src="/konjunktur-arbeitsmarkt/rec_ind.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/rec_ind.png)
- **Konstruktion:** Minimum zweier Teilindikatoren: dem Anstieg des 3-Monats-Durchschnitts der Arbeitslosenquote über sein 12-Monats-Tief (Sahm-Komponente) und dem Rückgang des 3-Monats-Durchschnitts der Vakanzrate unter sein 12-Monats-Hoch (in Prozentpunkten).
- **Interpretation:** Der kombinierte Indikator schlägt nur dann an, wenn gleichzeitig die Arbeitslosigkeit steigt und die offenen Stellen sinken. Die beiden gestrichelten Schwellenwerte sind empirisch an den historischen deutschen Rezessionsphasen kalibriert.
- **Quelle:** Eigene Berechnung nach Michaillat und Saez (2025).

<iframe src="/konjunktur-arbeitsmarkt/rec_prob.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [In Vollbild anzeigen](/konjunktur-arbeitsmarkt/rec_prob.png)
- **Konstruktion:** Normierter Anteil der Spanne zwischen unterer und oberer Rezessionsschwelle, den der Rezessionsindikator aktuell erreicht hat (in %).
- **Interpretation:** Liegt der Indikator unter der unteren Schwelle, beträgt die Wahrscheinlichkeit 0 %. Zwischen unterer und oberer Schwelle steigt sie linear bis 100 % an und dient als Echtzeit-Frühindikator (Nowcast) für Rezessionsrisiken in Deutschland.
- **Quelle:** Eigene Berechnung nach Michaillat und Saez (2025).
