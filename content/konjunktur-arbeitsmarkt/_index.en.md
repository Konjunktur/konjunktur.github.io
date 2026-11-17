---
title: "Business Cycle and Labor Market in Germany Based on the “Automated Business Cycle Dashboard” by Pascal Michaillat, Emmanuel Saez"
---

Real-time indicators of labor market tightness, full-employment rate (FERU), Beveridge curve, and recession probability for Germany based on the methodology of Pascal Michaillat and Emmanuel Saez (*Automated Business Cycle Dashboard*, [pascalmichaillat.org/dashboard](https://pascalmichaillat.org)). Shaded areas indicate German recession and downturn phases.

**Table of Contents**

- [Unemployment Rate (u)](#unemployment-rate)
- [Vacancy Rate (v)](#vacancy-rate)
- [Labor Market Tightness (v / u)](#labor-market-tightness)
- [Beveridge Curve](#beveridge-curve)
- [Unemployment Rate and Full-Employment Rate (FERU u*)](#full-employment-rate)
- [Unemployment Gap (u − u*)](#unemployment-gap)
- [Recession Indicator (Michez Rule)](#recession-indicator)
- [Recession Probability](#recession-probability)

---

### Unemployment Rate {#unemployment-rate}
<iframe src="/konjunktur-arbeitsmarkt/u_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/u_en.png)
- **Construction & Interpretation:** Share of registered unemployed in the civilian labor force.
- **Source:** Deutsche Bundesbank and Federal Statistical Office.

### Vacancy Rate {#vacancy-rate}
<iframe src="/konjunktur-arbeitsmarkt/v_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/v_en.png)
- **Construction & Interpretation:** Share of registered job openings in the civilian labor force.
- **Source:** Deutsche Bundesbank and Federal Statistical Office.

### Labor Market Tightness {#labor-market-tightness}
<iframe src="/konjunktur-arbeitsmarkt/theta_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/theta_en.png)
- **Construction & Interpretation:** Ratio of vacancy rate to unemployment rate (<i>v</i> / <i>u</i>). Values below 1 indicate slack; above 1 indicate tightness.
- **Source:** Michaillat and Saez (2024) methodology based on Bundesbank/Destatis data.

### Beveridge Curve {#beveridge-curve}

<iframe src="/konjunktur-arbeitsmarkt/bev_en.html" style="width:100%; height:465px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/bev_en.png)
- **Construction:** Scatter plot of the vacancy rate (<i>v</i>) against the unemployment rate (<i>u</i>) including the 45° ray (<i>v</i> = <i>u</i>) and hyperbolic trend curves (<i>v</i> = <i>a</i> + <i>b</i>/<i>u</i>) with coefficient of determination (<i>R</i>²).
- **Interpretation:** The Beveridge curve is one of the most robust relationships in macroeconomics. Over the business cycle, the economy moves along the curve. In recessions the unemployment rate increases while the vacancy rate decreases; in expansions the unemployment rate decreases while the vacancy rate increases.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2024) based on data from Deutsche Bundesbank and the Federal Statistical Office.

### Unemployment Rate and Full-Employment Rate (FERU) {#full-employment-rate}
<iframe src="/konjunktur-arbeitsmarkt/feru_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/feru_en.png)
- **Construction & Interpretation:** Socially efficient unemployment rate calculated as <i>u</i>* = √(<i>u</i> × <i>v</i>).
- **Source:** Michaillat and Saez (2024) methodology based on Bundesbank/Destatis data.

### Unemployment Gap {#unemployment-gap}
<iframe src="/konjunktur-arbeitsmarkt/gap_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/gap_en.png)
- **Construction & Interpretation:** Difference between actual unemployment and FERU (<i>u</i> − <i>u</i>*).
- **Source:** Michaillat and Saez (2024) methodology based on Bundesbank/Destatis data.

### Recession Indicator {#recession-indicator}
<iframe src="/konjunktur-arbeitsmarkt/rec_ind_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/rec_ind_en.png)
- **Construction & Interpretation:** Combined index measuring simultaneous increases in unemployment and drops in vacancies.
- **Source:** Michaillat and Saez (2025) methodology based on Bundesbank/Destatis data.

### Recession Probability {#recession-probability}

<iframe src="/konjunktur-arbeitsmarkt/rec_prob_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/rec_prob_en.png)
- **Construction:** The recession probability translates the recession indicator into a percentage scale from 0 % to 100 %, measuring how far the indicator has moved between the lower threshold (no recession signal) and the upper threshold (clear recession signal).
- **Interpretation:** Below the lower threshold, the probability is 0 %. Once the indicator crosses the lower threshold, the probability rises proportionally up to 100 % at the upper threshold, providing an ongoing real-time assessment of recession risk in Germany.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2025) based on data from Deutsche Bundesbank and the Federal Statistical Office.
