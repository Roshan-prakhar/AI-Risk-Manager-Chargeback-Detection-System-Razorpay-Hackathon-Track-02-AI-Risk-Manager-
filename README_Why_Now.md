# AI Risk Manager — Chargeback Detection System

## Why Now?

Indian banking is seeing fraud losses climb faster than at any point in recent memory, while
the underlying pattern of fraud itself is shifting from many small incidents to fewer,
far costlier ones. This project targets that shift directly.

### Fraud losses are rising sharply across Indian BFSI

According to a BioCatch survey covering 1,440 fraud, AML, and risk leaders across 25
countries, 84% of Indian banking leaders reported rising fraud losses this past year, up
from 70% in the 2025 survey and just 57% the year before that, compared with a 76% global
average [1]. Indian respondents were also the most concerned globally about the pace of
fraud; the survey report states that a large majority "recognize AI agents as the
industry's greatest exploitable vulnerability" looking ahead [1]. 90% of Indian
institutions said fraud attempts increased over the past year, well above the 81% global
average, and 66% pointed to scams through instant payment platforms like UPI as the
primary driver [1].

### The pattern is shifting: fewer incidents, dramatically higher value

This is the core trend behind this project. RBI data on public and private sector banks
shows fraud *case counts* falling every year for three consecutive years, while the *value*
lost in those same years has risen sharply, the opposite direction [2]:

| Bank Category | Year | Fraud Cases | Fraud Value |
|---|---|---|---|
| Public Sector Banks | FY24 | 7,446 | ₹8,092 crore |
| Public Sector Banks | FY25 | 6,916 | ₹23,617 crore |
| Public Sector Banks | FY26 | 5,418 | ₹35,709 crore |
| Private Sector Banks | FY24 | 23,965 | ₹2,667 crore |
| Private Sector Banks | FY25 | 14,024 | ₹8,927 crore |
| Private Sector Banks | FY26 | 3,956 | ₹11,399 crore |

Across the full banking and financial institution sector, total reported fraud fell from
23,722 cases to 10,114 cases year over year, while the value involved rose from ₹32,803
crore to ₹48,021 crore [2]. Every single row in this table tells the same story: **cases
down, value up, without exception.** Attackers are executing fewer, larger, more targeted
incidents rather than many small ones, exactly the pattern a static, volume-tuned rule
engine is worst equipped to catch.

### The same shift is visible in chargebacks specifically, not just lending fraud

The RBI data above is lending-side fraud; the chargeback trend shows an equivalent shift
in payments. Chargeback rates climbed steadily through 2025, reaching 0.26% of transactions
in the third quarter, roughly a 53% increase from the first quarter of the year, with retail
e-commerce chargebacks alone growing 233% in that same window, the sharpest rise of any
merchant category [3]. Separately, industry-wide benchmark data puts the average chargeback
rate at 0.26% of transactions as of Q3 2025, up 24% year over year from 0.21% [4].

### Why this matters beyond the raw numbers

Card networks penalize merchants directly once chargeback ratios cross a threshold, Visa's
threshold is dropping to 1.5% in April 2026, and Mastercard's Excessive Chargeback Program
fines merchants that cross 100 monthly disputes or a 1.5% ratio [4]. For an aggregator
processing payments across many merchants, this compounds: rising chargeback rates aren't
just a per-merchant loss, they're a direct exposure to network-level penalties.

**In short:** fraud losses are rising, the pattern producing those losses is shifting toward
fewer and larger incidents, and that same shift shows up in chargebacks specifically, not
just adjacent fraud categories. A detection system tuned for the old pattern (many small,
similar transactions) will systematically miss the new one. That gap is what this project
is built to close.

---

## Sources

[1] BioCatch 2026 fraud survey findings, as reported via Economic Times/ANI wire coverage,
"84% of Indian banking leaders report rising fraud losses, AI-driven threats emerge as
major concern," June 2026.

[2] Reserve Bank of India, Report on Trend and Progress of Banking in India, FY24-FY26
fraud data, as reported via Economic Times BFSI, "Fraud value surges 4x to Rs 48,021
crore: Banks, NBFCs face rising digital lending risks," May 2026.

[3] Sift Q4 2025 Digital Trust Index, as reported by Chain Store Age, "Why chargeback
rates are soaring."

[4] Sift Q3 2025 chargeback benchmark data, as reported by Chargeback.io, "Average
Chargeback Rate: Benchmarks and Network Thresholds."

*Note: quotations above are kept short and attributed per source; full figures and context
are available at the original articles.*
