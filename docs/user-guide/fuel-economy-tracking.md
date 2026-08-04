# Fuel Economy Tracking

MaintainIt calculates your vehicle's real-world fuel economy (MPG) from your fill-up history, and can alert you when it drops enough to suggest something might be wrong. This page explains exactly how that works, so the numbers you see are never a mystery.

## How MPG is calculated

MaintainIt only calculates a fuel economy reading between two **full** fill-ups — never from a single fill-up alone, and never from a partial one.

Here's why: fuel economy is *distance traveled* divided by *fuel actually burned* over that distance. A full tank gives you a known starting point (100% full) and a known ending point (100% full again), so the gallons you put in at the second fill-up is exactly what you burned getting there. A **partial** fill-up doesn't give you that — if you only put in 5 gallons, you don't actually know how much fuel was in the tank before you started, so there's no way to know the true amount burned.

So the app does this instead:

1. Every time you log a **full** fill-up, it looks back to your *previous* full fill-up.
2. Any **partial** fill-ups in between don't reset anything — their gallons just get added to a running total of "fuel put in since the last full tank."
3. MPG = (odometer reading now − odometer reading at that previous full fill-up) ÷ (total gallons added across every fill-up since then, including this one).

**Example:**

| Date | Odometer | Gallons | Full tank? |
|---|---|---|---|
| Jan 1 | 1,000 | 10.0 | ✅ Yes |
| Jan 8 | 1,150 | 5.0 | ⬜ No (partial) |
| Jan 15 | 1,300 | 10.0 | ✅ Yes |

MPG for the Jan 15 entry = (1,300 − 1,000) miles ÷ (10.0 + 5.0) gallons = **20 MPG**.

Notice the Jan 8 partial fill-up doesn't get an MPG of its own — it's not skipped, it's *folded into* the next full fill-up's calculation. This is the same convention used by most dedicated fuel-tracking apps, and it's the only way to get an accurate number when you don't always fill all the way up.

The very first fill-up you ever log for a vehicle won't produce an MPG reading either, since there's no earlier full fill-up to measure from yet.

## The fuel economy chart

From any vehicle's detail screen, you can view its MPG trend over time. Pick a time window (last 3 months, 6 months, 1 year, or all-time) to zoom in on recent trends or see the whole history at once. Only fill-ups that produced a real MPG reading (as described above) appear on the chart — partial fill-ups aren't separately plotted, since they don't have an MPG value of their own.

## Fuel economy drop alerts

If you'd like, MaintainIt can notify you when a new fill-up's calculated MPG drops significantly compared to your recent average — a real drop can be an early sign of something worth checking (tire pressure, an air filter, a developing mechanical issue).

You control this in **Settings**:

- **Enable/disable** the alert entirely.
- **Threshold** — how big a drop (as a percentage) should trigger a notification. A smaller threshold catches smaller changes but may notify you more often from normal variation (weather, city vs. highway driving, etc.); a larger threshold only flags more significant drops.
- **Comparison baseline** — what your new fill-up is measured against:
  - **Trailing average (last 5 fill-ups)** — reacts faster to a real, sustained change, since it isn't diluted by fill-ups from months or years ago. This is a good default for most people.
  - **All-time average** — more stable and less prone to false alarms from normal day-to-day variation, but slower to catch a real trend since one bad fill-up barely moves a long-run average.

The alert is evaluated automatically each time you log a new **full** fill-up (partial fill-ups don't produce an MPG reading, so there's nothing to evaluate). If the drop meets or exceeds your configured threshold, you'll get a notification right away.
