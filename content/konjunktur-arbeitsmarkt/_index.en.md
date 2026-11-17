---
title: "Business Cycle and Labor Market in Germany Based on the “Automated Business Cycle Dashboard” by Pascal Michaillat, Emmanuel Saez"
---

Real-time indicators for Germany's labor market (tightness, FERU, Beveridge curve, recession probability) based on Michaillat and Saez ([pascalmichaillat.org/dashboard](https://pascalmichaillat.org)), taking into account German Council of Economic Experts and Bundesbank dating.

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
- **Construction / Interpretation:** Share of registered unemployed in the civilian labor force (in %).
- **Source:** Deutsche Bundesbank & Federal Statistical Office (Federal Employment Agency data).

### Vacancy Rate {#vacancy-rate}
<iframe src="/konjunktur-arbeitsmarkt/v_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/v_en.png)
- **Construction / Interpretation:** Registered job openings divided by the civilian labor force (in %).
- **Source:** Deutsche Bundesbank & Federal Statistical Office (Federal Employment Agency data).

### Labor Market Tightness {#labor-market-tightness}
<iframe src="/konjunktur-arbeitsmarkt/theta_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/theta_en.png)
- **Construction / Interpretation:** Ratio of vacancy rate to unemployment rate (<i>v</i> / <i>u</i>). Values < 1 indicate slack, > 1 a tight market.
- **Source:** Own calculation (Michaillat/Saez 2024 methodology) based on Bundesbank & Federal Statistical Office data.

### Beveridge Curve {#beveridge-curve}
<iframe src="/konjunktur-arbeitsmarkt/bev_en.html" style="width:100%; height:465px; border:none; overflow:hidden;" scrolling="no"></iframe>
- [View full screen](/konjunktur-arbeitsmarkt/bev_en.png)
- **Construction / Interpretation:** Scatter plot of <i>v</i> vs. <i>u</i> tracking cyclical movements (counter-cyclical shifts between expansions and recessions).
- **Source:** Own calculation (Michaillat/Saez 2024 methodology) based on Bundesbank & Federal Statistical Office data.

### Unemployment Rate and Full-Employment Rate (FERU) {#full-employment-rate}

<iframe src="/konjunktur-arbeitsmarkt/feru_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/feru_en.png)
- **Construction:** Geometric average of the unemployment rate and vacancy rate: <i>u</i>* = √(<i>u</i> × <i>v</i>).
- **Interpretation:** Following Michaillat and Saez, <i>u</i>* marks the socially efficient unemployment rate that minimizes unproductive job-seeking and recruiting costs. On the Beveridge diagram, <i>u</i>* is at the intersection with the 45° ray.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2024) based on data from Deutsche Bundesbank and the Federal Statistical Office.

### Unemployment Gap {#unemployment-gap}

<iframe src="/konjunktur-arbeitsmarkt/gap_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/gap_en.png)
- **Construction:** Difference (<i>u</i> − <i>u</i>*) between the actual unemployment rate and the full-employment rate (FERU) in percentage points.
- **Interpretation:** A positive gap marks an inefficiently slack labor market (recession or downturn); a negative gap marks a tight labor market above full employment.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2024) based on data from Deutsche Bundesbank and the Federal Statistical Office.

### Recession Indicator {#recession-indicator}

<iframe src="/konjunktur-arbeitsmarkt/rec_ind_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/rec_ind_en.png)
- **Construction:** Minimum of two indicators: the increase in the 3-month average of the unemployment rate above its 12-month low (Sahm component) and the decrease in the 3-month average of the vacancy rate below its 12-month high (in percentage points).
- **Interpretation:** The combined indicator rises only when unemployment increases and vacancies decline simultaneously. The two dashed thresholds are calibrated empirically to historical German recession phases.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2025) based on data from Deutsche Bundesbank and the Federal Statistical Office.

### Recession Probability {#recession-probability}

<iframe src="/konjunktur-arbeitsmarkt/rec_prob_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/rec_prob_en.png)
- **Construction:** Translates the recession indicator into a percentage scale from 0 % to 100 %, measuring how far the indicator has moved between the lower threshold (no recession signal) and the upper threshold (clear recession signal).
- **Interpretation:** Below the lower threshold, the probability is 0 %. Once the indicator crosses the lower threshold, the probability rises proportionally up to 100 % at the upper threshold, providing an ongoing real-time assessment of recession risk in Germany.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2025) based on data from Deutsche Bundesbank and the Federal Statistical Office.

