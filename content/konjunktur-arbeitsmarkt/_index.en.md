---
title: "Business Cycle and Labor Market in Germany Based on the “Automated Business Cycle Dashboard” by Pascal Michaillat, Emmanuel Saez"
---

Real-time indicators on labor market tightness, the full-employment rate of unemployment (FERU), the Beveridge curve, and recession probability for Germany following the methodology of Pascal Michaillat and Emmanuel Saez (*Automated Business Cycle Dashboard*, [pascalmichaillat.org/dashboard](https://pascalmichaillat.org/dashboard)). Shaded in gray are German recession and slowdown phases based on the business-cycle dating of the German Council of Economic Experts and the Deutsche Bundesbank (2008/09 financial crisis, 2012/13 euro crisis, 2020 COVID-19 pandemic, and the three-year stagnation and slowdown phase from late 2022 to late 2025). Shaded in light blue are German recession phases based on negative year-on-year growth rates of real GDP.

**Table of Contents**

- [Unemployment Rate (u)](#unemployment-rate)
- [Vacancy Rate (v)](#vacancy-rate)
- [Labor Market Tightness (v / u)](#labor-market-tightness)
- [Beveridge Curve](#beveridge-curve)
- [Unemployment Rate and Full-Employment Rate (FERU u*)](#full-employment-rate)
- [Unemployment Gap (u − u*)](#unemployment-gap)
- [Recession Indicator (Michaillat Rule)](#recession-indicator)
- [Recession Probability](#recession-probability)

---

### Unemployment Rate {#unemployment-rate}

<iframe src="/konjunktur-arbeitsmarkt/u_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/u_en.png)
- **Construction:** The unemployment rate (<i>u</i>) is the number of registered unemployed divided by the civilian labor force (in %).
- **Interpretation:** It measures the share of people actively looking for work who have not yet found a job.
- **Source:** Federal Statistical Office (Federal Employment Agency data).

### Vacancy Rate {#vacancy-rate}

<iframe src="/konjunktur-arbeitsmarkt/v_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/v_en.png)
- **Construction:** The vacancy rate (<i>v</i>) is the number of job openings registered with the Federal Employment Agency divided by the civilian labor force (in %). Using the identical denominator ensures consistency between <i>u</i> and <i>v</i>.
- **Interpretation:** It measures unfilled registered job openings per civilian labor force participant.
- **Source:** Federal Statistical Office (Federal Employment Agency data).

### Labor Market Tightness {#labor-market-tightness}

<iframe src="/konjunktur-arbeitsmarkt/theta_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/theta_en.png)
- **Construction:** Labor market tightness (<i>θ</i> = <i>v</i> / <i>u</i>) is the ratio of the vacancy rate to the unemployment rate.
- **Interpretation:** It indicates the number of registered job openings per unemployed person. Values of <i>θ</i> below 1 indicate labor market slack; values above 1 indicate a tight labor market.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2024) based on data from the Federal Statistical Office (Federal Employment Agency data).

### Beveridge Curve {#beveridge-curve}

<iframe src="/konjunktur-arbeitsmarkt/bev_en.html" style="width:100%; height:465px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/bev_en.png)
- **Construction:** Scatter plot of the vacancy rate (<i>v</i>) against the unemployment rate (<i>u</i>), including the 45° ray (<i>v</i> = <i>u</i>) and hyperbolic fitted curves (<i>v</i> = <i>a</i> + <i>b</i>/<i>u</i>) with the coefficient of determination (<i>R</i>²).
- **Interpretation:** The Beveridge curve is one of the most stable relationships in macroeconomics. Over the business cycle, the economy moves along the curve: during recessions, the unemployment rate rises while the vacancy rate falls; during expansions, the unemployment rate falls while the vacancy rate rises.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2024) based on data from the Federal Statistical Office (Federal Employment Agency data).

### Unemployment Rate and Full-Employment Rate (FERU) {#full-employment-rate}

<iframe src="/konjunktur-arbeitsmarkt/feru_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/feru_en.png)
- **Construction:** The full-employment rate of unemployment (<i>u</i>*) is calculated as the geometric average of the unemployment rate and the vacancy rate: <i>u</i>* = √(<i>u</i> × <i>v</i>).
- **Interpretation:** Following Michaillat and Saez, <i>u</i>* marks the socially efficient unemployment rate that minimizes unproductive job-seeking and recruiting costs. On the Beveridge diagram, <i>u</i>* corresponds to the intersection with the 45° ray.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2024) based on data from the Federal Statistical Office (Federal Employment Agency data).

### Unemployment Gap {#unemployment-gap}

<iframe src="/konjunktur-arbeitsmarkt/gap_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/gap_en.png)
- **Construction:** The unemployment gap (<i>u</i> − <i>u</i>*) is the difference between the actual unemployment rate and the full-employment rate of unemployment (FERU) in percentage points.
- **Interpretation:** A positive value indicates labor market slack (recession or downturn); a negative value signals a tight labor market above full employment.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2024) based on data from the Federal Statistical Office (Federal Employment Agency data).

### Recession Indicator {#recession-indicator}

<iframe src="/konjunktur-arbeitsmarkt/rec_ind_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/rec_ind_en.png)
- **Construction:** Minimum of two sub-indicators: the increase in the 3-month moving average of the unemployment rate above its 12-month low (Sahm component) and the decrease in the 3-month moving average of the vacancy rate below its 12-month high (in percentage points).
- **Interpretation:** The combined indicator rises only when unemployment increases and job openings decline simultaneously. The two dashed thresholds are calibrated empirically to historical German recession phases.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2025) based on data from the Federal Statistical Office (Federal Employment Agency data).

### Recession Probability {#recession-probability}

<iframe src="/konjunktur-arbeitsmarkt/rec_prob_en.html" style="width:100%; height:455px; border:none; overflow:hidden;" scrolling="no"></iframe>

- [View full screen](/konjunktur-arbeitsmarkt/rec_prob_en.png)
- **Construction:** Recession probability translates the value of the recession indicator into a percentage between 0 % and 100 %. The lower threshold marks the range with no recession signal (0 %), and the upper threshold marks the level at which historical recessions were clearly reached (100 %).
- **Interpretation:** When the indicator is below the lower threshold, the probability is 0 %. Once it rises above the lower threshold, the probability increases proportionally up to 100 % at the upper threshold, providing an ongoing real-time assessment of recession risk in Germany.
- **Source:** Own calculation following the methodology of Michaillat and Saez (2025) based on data from the Federal Statistical Office (Federal Employment Agency data).

