# Cost of downtime and degraded service: evidence for a general economic model for Aegis

Research date: 2026-11-05. Scope: a general value model, value = avoided degraded/failed minutes (or failed requests) x cost per degraded minute, that works for any organization: SaaS, internal services, public sector, banks, and others, not only sellers.

Reliability legend used below:
- **[V]**: vendor-sponsored, where the publisher sells observability, incident or IT products and benefits from a high number.
- **[SR]**: self-reported estimates from respondents, not measured losses.
- **[OLD]**: figure from before 2022.
- **[2ary]**: verified only through secondary sources.

---

## 1. What do the major surveys report as the cost of downtime per hour or minute?

### Takeaway
Every major 2023–2026 survey puts the cost of a serious outage for mid-size and large organizations in the range of **$100k to $2M per hour**, roughly **$1.7k to $33k per minute**. All of them are self-reported, and most are vendor-sponsored, so they should be shown as **ranges and shares of respondents**, never as one "true" cost. The Gartner figure of $5,600/min is from 2014, rests on an undocumented method, and should not be used as a headline number.

### Cited Findings

**ITIC 2024 Hourly Cost of Downtime Survey** (independent analyst firm, but its reports are often redistributed by vendors) [SR]
- Over 90% of mid-size and large enterprises say one hour of downtime costs more than **$300,000**. The headline wording says "90% of firms", so the page is ambiguous about whether the base is all firms or only mid-size and large ones. — [ITIC 2024 Part 1](https://itic-corp.com/?p=3152)
- **41%** of enterprises put hourly downtime at **$1 million to over $5 million**. — [ITIC 2024 Part 1](https://itic-corp.com/?p=3152)
- Sample: "over 1,000 firms worldwide". Independent web survey run from **November 2023 to mid-March 2024**. — [ITIC 2024 Part 1](https://itic-corp.com/?p=3152)
- The figures **exclude** litigation and civil or criminal penalties, so they are conservative on the legal side. — [ITIC 2024 Part 1](https://itic-corp.com/?p=3152)
- Earlier ITIC editions, reported in secondary sources, say 97% of large enterprises (more than 1,000 employees) put an hour above **$100,000**. I did not check this against an ITIC primary page. [2ary] — [ManageEngine summary](https://www.manageengine.com/network-monitoring/tech-topics/how-much-an-hour-of-downtime-cost.html); Part 2 PDF: [ITIC 2024 Part 2 (mirror)](https://calyptix.com/wp-content/uploads/ITIC-2024-Hourly-Cost-of-Downtime-Survey-Results-Part-2.pdf)

**Splunk + Oxford Economics, "The Hidden Costs of Downtime" (June 11, 2024)** [V][SR]
- Unplanned downtime costs Global 2000 companies about **$400B per year**, which is **9% of profits**. — [Cisco/Splunk press release](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html); [Oxford Economics blog](https://oxfordeconomics.com/?p=69595)
- Average cost per company per year by region: US **$256M**, Europe **$198M**, APAC **$187M**. Coverage commonly rounds this to about $200M per company. — [Cisco/Splunk press release](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html)
- Sample: **2,000 executives** from Forbes' 2023 Global 2000 list, covering technology, finance (CFOs) and marketing (CMOs) roles, **53 countries** and **10 industries**. Oxford Economics ran the survey in collaboration with Splunk. — [Cisco/Splunk press release](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html)
- **Its definition of downtime explicitly includes degradation**: "any service degradation (such as latency) or unavailability of critical business systems". This matters directly for Aegis. — [Cisco/Splunk press release](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html)
- Root causes: **56%** of downtime incidents come from security incidents and **44%** from application or infrastructure issues. Human error is the top cause in both groups. — same source
- Full report (gated): [Splunk PDF](https://www.splunk.com/en_us/pdfs/gated/ebooks/the-hidden-costs-of-downtime.pdf)

**New Relic 2025 Observability Forecast (released September 17, 2025)** [V][SR]
- Median cost of a **high-business-impact outage**: **$2M per hour**, about **$33,333 per minute**. Organizations with full-stack observability report **$1M per hour**. — [New Relic press release](https://newrelic.com/press-release/20250917)
- Annual median cost of high-impact outages: **$76M per year**. — [New Relic press release](https://newrelic.com/press-release/20250917)
- Sample: **1,700** IT and engineering practitioners and leaders (65% practitioners, 24% managers, 11% executives) in **23 countries** and **11 industries**. Fieldwork in April–May 2025 by Enterprise Technology Research (ETR), in partnership with New Relic. — [New Relic press release](https://newrelic.com/press-release/20250917); [Full report PDF](https://newrelic.com/sites/default/files/2025-09/new-relic-2025-observability-forecast-report.pdf)
- Respondents say engineers spend **33%** of their time firefighting disruptions. **40%** of teams without full-stack observability have high-impact outages at least weekly, against 23% of teams with it. — [New Relic press release](https://newrelic.com/press-release/20250917)
- Sector cut: in retail and eCommerce, the median hourly cost of a critical outage is about **$1M**. — [Business Wire, Nov 2025 retail report](https://www.businesswire.com/news/home/20251104312088/en/New-Relic-Report-Reveals-Retailers-are-Turning-to-Observability-Amidst-AI-Adoption) [2ary; seen only in the search snippet]

**Uptime Institute Annual Outage Analysis** (independent data-center research body. Its survey asks about the respondent's *most recent* significant outage) [SR]
- 2024 report (2023 survey): **54%** said their most recent significant, serious or severe outage cost **more than $100k**, and **16%** said **more than $1M**. — [Uptime Institute AOA 2024](https://intelligence.uptimeinstitute.com/resource/annual-outage-analysis-2024)
- 2025 report (2024 survey): about **54%** above $100k and **20%** above $1M. [2ary] — [Data Center Knowledge](https://www.datacenterknowledge.com/outages/data-center-outages-decline-for-fourth-straight-year-but-issues-persist)
- 2026 report (2025 survey, released May 13, 2026): **57%** above $100k and **20%** above $1M, the second year in a row at one in five. [2ary: I could not load the primary press release] — [Business Wire release (title)](https://www.businesswire.com/news/home/20260513289344/en/Uptime-Announces-Annual-Outage-Analysis-Report-2026); [MSP Channel](https://www.msp-channel.com/news/72355/uptime-publishes-annual-outage-analysis-report-2026)
- Earlier trend: the 2022 analysis said downtime costs and consequences were worsening. [OLD] — [Business Wire 2022](https://www.businesswire.com/news/home/20220608005265/en/Uptime-Institutes-2022-Outage-Analysis-Finds-Downtime-Costs-and-Consequences-Worsening-as-Industry-Efforts-to-Curb-Outage-Frequency-Fall-Short)

**PagerDuty survey (June 27, 2024)** [V][SR]
- Estimated downtime cost: **$4,537 per minute**. With an average incident lasting **175 minutes**, that is about **$794,000 per incident**. With about 25 high-priority incidents a year, the total is just under **$20M per organization per year**. — [PagerDuty newsroom](https://pagerduty.com/newsroom/study-cost-of-incidents); [PagerDuty investor release](https://investor.pagerduty.com/news/news-details/2024/PagerDuty-Survey-Reveals-Customer-Facing-Incidents-Increased-by-43-During-the-Past-Year-Each-Incident-Costs-Nearly-800000/default.aspx)
- Sample: **500 IT leaders** at companies with more than 1,000 employees in the US, UK and Australia. Censuswide ran it online from May 31 to June 6, 2024. — same sources
- **59%** reported more customer-impacting incidents, an average increase of **43%** in 12 months. Organizations with mostly manual response steps reported **$30.4M** a year in outage costs, against **$16.8M** for fully automated ones. — same sources

**Gartner, $5,600 per minute (2014)** [OLD][2ary]
- Origin: a Gartner blog post by Andrew Lerner, "The Cost of Downtime", July 16, 2014 ([blogs.gartner.com URL](https://blogs.gartner.com/andrew-lerner/2014/07/16/the-cost-of-downtime/)). It is behind a Cloudflare challenge and I could not retrieve it. It is cited by [Atlassian](https://www.atlassian.com/incident-management/kpis/cost-of-downtime) and [CDW/Axiom](https://webobjects2.cdw.com/is/content/CDW/cdw/on-domain-cdw/brands/axiom/axiom-card-2.pdf).
- Atlassian stresses that Gartner itself called it "just an average" that varies with company size and industry. — [Atlassian](https://www.atlassian.com/incident-management/kpis/cost-of-downtime)
- Atlassian also cites a **2016 Ponemon** figure of about **$9,000 per minute**, and **$137–$427 per minute for small businesses**. [OLD][2ary] — [Atlassian](https://www.atlassian.com/incident-management/kpis/cost-of-downtime)
- Secondary sources disagree on its scope ("IT downtime" vs "network downtime"). One source (CDW/Axiom) misquotes it as a "$5,600 to $5M per minute" range. — [CDW/Axiom card](https://webobjects2.cdw.com/is/content/CDW/cdw/on-domain-cdw/brands/axiom/axiom-card-2.pdf)

### Inferences
- The surveys measure different things, so they cannot be averaged:
  - New Relic gives a median per hour for *high-impact* outages.
  - PagerDuty gives a per-minute figure for *customer-facing incidents*.
  - ITIC gives the distribution of firms' self-estimated hourly cost.
  - Uptime gives the cost of the *most recent significant outage* as a whole event, not per hour.
  - Splunk gives an annual total for Global 2000 firms.
  The honest summary for a slide is: "for large organizations a serious incident minute costs on the order of $5k–$33k; for SMBs, hundreds of dollars."
- The Gartner $5,600 per minute ($336k per hour) happens to sit near the ITIC $300k per hour threshold. That is why it survives, but it is 12 years old and its method is undocumented. Mention it only as "the classic, outdated reference".
- Three of the five sources (Splunk, New Relic, PagerDuty) sell the cure, so there is a systematic risk of upward bias. ITIC and Uptime are not product vendors but are still self-reported.

### Gaps
- I could not read the Gartner 2014 post directly (bot block), so its methodology is unverified. My unconfirmed recollection is that it was a back-of-envelope figure "based on industry surveys", not a study with a reported sample.
- I could not read the primary Uptime 2026 release or report. The 57%/20% figures come from secondary coverage.
- I found no ITIC breakdown by industry (finance, health, government) in accessible text. It is probably in the exhibit images or Part 2.
- New Relic's 2023 and 2024 editions were not checked, so I have no trend line for the median hourly cost.

---

## 2. What makes up the cost, and in what proportions?

### Takeaway
Only Splunk/Oxford Economics gives a dollar breakdown by component, and it shows that **lost revenue is only part of the cost**. For a Global 2000 firm, direct costs include about $49M lost revenue, $22M regulatory fines, $16M SLA penalties and $19M ransomware per year. On top of that come hidden costs: stock price drops of up to 9%, delayed innovation, lower developer productivity, and customer lifetime value. This is the evidence that answers the professor: cost exists even where nothing is sold.

### Cited Findings
- **Splunk/Oxford Economics 2024**, average per Global 2000 company per year [V][SR] — [Cisco/Splunk press release](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html)
  - Lost revenue: **$49M** per year, about 75 days to recover.
  - Regulatory fines: **$22M** per year, the second-largest cost.
  - Missed SLA penalties: **$16M**, the third-largest.
  - Ransomware and extortion payouts: **$19M**.
  - Europe only: **$12M** overtime wages and **$9M** to recover from backups.
  - Hidden costs:
    - Stock price drop of **up to 9%** after one incident, about 79 days to recover.
    - **74%** of tech executives saw delayed time-to-market and **64%** saw stagnant developer productivity.
    - **40%** of CMOs say downtime hurts customer lifetime value and **40%** say it damages partner relationships.
    - **41%** say customers are often or always the first to detect downtime.
  - "Resilience leaders" (the top 10%) lose **$17M** less revenue and pay **$10M** less in fines.
- Engineering and recovery cost: engineers spend **33%** of their time firefighting disruptions (New Relic 2025 [V]). — [New Relic press release](https://newrelic.com/press-release/20250917)
- Response process cost: manual response is associated with **$30.4M** a year against **$16.8M** for automated response (PagerDuty 2024 [V]). — [PagerDuty newsroom](https://pagerduty.com/newsroom/study-cost-of-incidents)
- ITIC hourly figures exclude litigation and civil or criminal penalties. — [ITIC 2024](https://itic-corp.com/?p=3152)
- Uptime counts "direct and indirect losses" in its cost bands. [2ary] — [MSP Channel / Uptime 2026](https://www.msp-channel.com/news/72355/uptime-publishes-annual-outage-analysis-report-2026)

### Inferences
- From the Splunk dollar items alone, **lost revenue (~$49M) is less than half** of the itemized direct costs (49 + 22 + 16 + 19 ≈ $106M before overtime, recovery and hidden costs). Total per firm is about $200M, so revenue is roughly **25%** of the whole. This is my arithmetic, not a figure published by Splunk. Fines, SLA penalties, labor and reputation make up the rest, and none of these require the organization to "sell" anything.
- For non-sellers, the relevant components map as follows:

  | Organization | Main cost components |
  |---|---|
  | Internal service | Employee productivity lost (blocked users × loaded hourly cost) plus engineering recovery time |
  | SaaS | SLA credits, churn or lower customer lifetime value, and support load |
  | Bank | Regulatory fines and penalties, transaction failures, reputation |
  | Public sector | Citizen time lost, extra channel cost (call center or in-person fallback), statutory obligations |

### Gaps
- I found no source with **percentage shares** of each component that hold across industries. The Splunk breakdown is the only itemized one, and it covers only Global 2000 firms.
- I found no reliable public-sector-specific cost-of-downtime survey in this search.

---

## 3. How do cloud providers price unavailability in SLA credits?

### Takeaway
The three hyperscalers use almost the same step function: **10% credit** for missing the target (99.99% or 99.9%) but staying at or above 99%, **25–30%** between 95% and 99%, and **100%** below 95%. Credits are the customer's **sole remedy** and are capped at the monthly bill. This shows the contract price of unavailability is a fraction of the service fee, far below the customer's real loss.

### Cited Findings
- **AWS EC2 (updated May 25, 2022)**:
  - Region-level SLA (2+ Availability Zones): below **99.99%** but at least 99.0% → **10%**; below 99.0% but at least 95.0% → **30%**; below 95.0% → **100%**.
  - Instance-level SLA: below **99.5%** but at least 99.0% → 10%; 99.0% to 95.0% → 30%; below 95% → 100%.
  - "Unavailable" means **no external connectivity**.
  - Service credits are the "sole and exclusive remedy".
  — [AWS Compute SLA](https://aws.amazon.com/compute/sla/)
- **Google Compute Engine** (retrieved 2026-11-05):
  - Service level objectives: Instances in Multiple Zones **≥99.99%** (Premium Tier), load balancing ≥99.99%, single instance ≥99.9% (memory-optimized ≥99.95%).
  - Credits for multi-zone: 99.00% to below 99.99% → **10%**; 95.00% to below 99.00% → **25%**; below 95.00% → **100%**.
  - Credits for single instance: 95% to below 99.9% → 10%; 90% to below 95% → 25%; below 90% → 100%.
  - Downtime periods shorter than one minute do not count.
  - The SLA is the "sole and exclusive remedy".
  — [Google Compute Engine SLA](https://cloud.google.com/compute/sla)
- **Microsoft Azure**: the official SLA is now a downloadable document, "Service Level Agreement for Microsoft Online Services", with the latest edition dated **November 1, 2026**. I could not extract the VM table. — [Microsoft SLA portal](https://www.microsoft.com/licensing/docs/view/Service-Level-Agreements-SLA-for-Online-Services)

### Inferences
- The SLA credit is a **lower bound** and a contractual proxy. A 10% fee credit for falling from 99.99% to 99% (about 7 hours down in a month) says nothing about the customer's loss, which the surveys put at $100k+ per hour. That gap is exactly why customers invest in their own resilience, and Aegis is part of that.
- For a **SaaS provider using Aegis**, its *own* SLA credits to customers are a direct, contract-backed cost component it can compute exactly: credit % × monthly recurring revenue (MRR) of affected customers.
- All three SLAs define unavailability as total loss of connectivity (or, for Google, loss of connectivity or failed health checks). **Degradation that is slow but up does not trigger credits.** This is an important caveat when Aegis's benefit is fewer degraded minutes rather than fewer down minutes.

### Gaps
- I did not verify the Azure VM thresholds and credits from the primary source in this session. My unverified recollection is: 99.99% for 2+ Availability Zones, with credits of 10%, 25% and 100% at the same 99%/95% cut-points. Check this in the Nov 2026 SLA document before using it.

---

## 4. Does partial degradation cost less or more than a full outage?

### Takeaway
There is **no rigorous study that directly compares the cost of a degraded minute with a down minute**. The evidence shows degradation is **costly and counted**: Splunk's definition of downtime includes latency, and Akamai/SOASTA measured conversion loss from a 100 ms delay. The defensible modelling choice is a **severity weight w in [0, 1]** applied to degraded minutes, where w = 1 for full outage and each organization calibrates w for itself.

### Cited Findings
- Splunk/Oxford Economics explicitly defines downtime as "any service degradation (such as latency) or unavailability of critical business systems". Its $400B therefore already mixes degraded and down time. — [Cisco/Splunk press release](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html)
- Uptime Institute's cost bands apply to "significant, serious or severe" outages on its severity scale. Lower categories (minor, degraded) are not costed in the headline figures. — [Uptime AOA 2024](https://intelligence.uptimeinstitute.com/resource/annual-outage-analysis-2024)
- Akamai/SOASTA spring 2017 State of Online Retail Performance, based on about **10 billion** visits to top retailers in one month [OLD][V, observational]:
  - A **100 ms** delay in load time is associated with up to **7%** lower conversion (desktop −2.4%, mobile −7.1%, tablet −3.8%).
  - A **2 s** delay is associated with a **103%** increase in bounce rate.
  - **53%** of mobile visitors leave a page that takes more than 3 s to load.
  — [Akamai press release](https://www.akamai.com/fr/newsroom/press-release/akamai-releases-spring-2017-state-of-online-retail-performance-report); [Retail TouchPoints](https://www.retailtouchpoints.com/topics/digital-commerce/milliseconds-matter-a-0-1-second-delay-can-hurt-conversions-7)
- **41%** of tech executives say customers are often or always the first to detect downtime (Splunk 2024). New Relic says 41% of leaders learn of interruptions through inefficient means such as customer complaints. Degradation that is detected late lasts longer. — [Splunk press release](https://newsroom.cisco.com/c/r/newsroom/en/us/a/y2024/m06/conf24-splunk-report-shows-downtime-costs-global-2000-companies-400b-annually.html); [New Relic press release](https://newrelic.com/press-release/20250917)
- Google SRE practice frames reliability through a request-based SLI: the share of good requests over total requests, with an **error budget = 1 − SLO**. A failed or too-slow request consumes budget whether or not the service is "down". The book also argues that 100% is the wrong target, because the cost of extra nines has to be weighed against user benefit. — [Google SRE Book, "Embracing Risk"](https://sre.google/sre-book/embracing-risk/); [Google SRE Book, "Service Level Objectives"](https://sre.google/sre-book/service-level-objectives/)

### Inferences
- Measuring Aegis's benefit in **failed requests** fits the SRE "bad events / total events" accounting. A failed request during a spike is equivalent to a user-visible failure, so it maps to a down-minute cost through **failed requests ÷ requests per minute = equivalent full-outage minutes**. This conversion avoids having to argue about how severe "degraded" is.
- Degradation can cost *more* per incident than an outage, because it often goes undetected longer and does not trigger SLA credits or failover. Per minute, it costs less because some users still succeed. I found no study that quantifies this, so present it as a hypothesis.

### Gaps
- I found no peer-reviewed or survey source with a degraded-to-down cost ratio.
- Latency-to-conversion evidence is retail-specific and from 2017. I found no equivalent for internal tools or the public sector.

---

## 5. Which figures are robust enough for a slide, and how should a general model be framed?

### Takeaway
Use a **plug-in model** in which each organization supplies its own cost per minute, built from components. Show survey figures only as **reference ranges** with their caveats. The most defensible slide numbers are:
- ITIC 2024: more than 90% of mid-size and large firms are above $300k per hour.
- Uptime 2026: 57% of significant outages cost more than $100k, and 20% more than $1M.
- New Relic 2025: median $2M per hour for high-impact outages, labeled as vendor-sponsored.
- Splunk 2024: 9% of profits, with lost revenue only a minority of the cost.

### Cited Findings
- Reference ranges for the slide:

  | Source | Figure | Base |
  |---|---|---|
  | [ITIC 2024](https://itic-corp.com/?p=3152) | >$300k per hour for >90% of firms; $1M–$5M+ for 41% | >1,000 firms |
  | [Uptime 2026](https://www.msp-channel.com/news/72355/uptime-publishes-annual-outage-analysis-report-2026) | 57% of outages >$100k; 20% >$1M | most recent significant outage |
  | [PagerDuty 2024](https://pagerduty.com/newsroom/study-cost-of-incidents) | $4,537 per minute | 500 IT leaders, firms >1,000 employees |
  | [New Relic 2025](https://newrelic.com/press-release/20250917) | $33,333 per minute median | 1,700 respondents, high-impact outages |
  | [Atlassian citing Ponemon 2016](https://www.atlassian.com/incident-management/kpis/cost-of-downtime) | $137–$427 per minute for SMBs | [OLD] |

- Contractual floor: hyperscaler SLAs pay 10%/25–30%/100% of the monthly fee. — [AWS](https://aws.amazon.com/compute/sla/), [Google Cloud](https://cloud.google.com/compute/sla)

### Inferences (proposed general model, my synthesis)

**Value per period**

    V = Σ_incidents [ (ΔM_down × C_min) + (ΔM_degraded × w × C_min) ]

or, in request terms:

    V = ΔFailedRequests / RPM_avg × C_min   (+ degraded part)

- ΔM_down and ΔM_degraded are the down and degraded minutes avoided, measured in Aegis's experiments, for example the reduction against both HPAs.
- w is the severity weight: the share of users or requests affected, or the SLO-violation fraction (default 0.3–0.5 if unknown, plus a sensitivity analysis).
- RPM_avg is the average number of requests per minute.

**Cost per minute, built bottom-up from components the organization knows**

    C_min = R_min × d + U × h × p + S + E + F + K

| Term | Meaning | Applies to |
|---|---|---|
| R_min × d | revenue per minute × share of it that is lost and not deferred | sellers only. Zero for internal or public services |
| U × h × p | users blocked × loaded cost per user-minute × productivity loss % | internal services, public sector (citizens' time) |
| S | SLA credits or penalties per minute = credit % × affected MRR ÷ minutes in the month | SaaS |
| E | engineering and incident response per minute = responders × loaded rate | everyone |
| F | expected regulatory fines and penalties per minute | banks, health, public sector |
| K | churn and reputation = P(churn) × customer lifetime value × affected customers | SaaS, banks, consumer services |

**Calibration by organization type**

| Organization type | Main terms |
|---|---|
| SaaS | S + K + E |
| Internal platform | U × h × p + E |
| Bank | F + K + transaction revenue |
| Public sector | citizens' time × value of time + fallback channel cost + E |
| E-commerce | R × d dominates (this is the current Aegis business case, now one special case) |

**Presentation tips**
- Cross-check each organization's own C_min against the survey ranges above.
- Present results as a **break-even**: "Aegis pays off if your cost per degraded minute exceeds $X". This avoids asserting a single industry number.
- Label survey figures as self-reported and, where relevant, vendor-sponsored.
- Do not use Gartner's $5,600 per minute as evidence, only as history.

### Gaps
- I found no authoritative per-industry table (finance vs health vs government) from 2022–2026 in accessible primary sources. ITIC may have one in its exhibits.
- I found no published source that validates the default severity weight w. It is a modelling assumption and must be flagged as such.
