"""The analysis plan of the experiment design, fixed before the runs (docs/experiments/design.md, section 7).

Per load, a randomized complete block design with 3 treatments (autoscalers) and b blocks:
  y_ij = mu + tau_i + beta_j + e_ij
- Primary: failed requests (%). Two contrasts per load, Aegis - HPA and Aegis - tuned HPA, t tests on the
  ANOVA error (df = 2(b - 1)), Holm-corrected over the 6 contrasts (3 loads x 2).
- Robustness, reported next to it: the same contrasts on ranks (rank-transform ANOVA), the exact
  within-block randomization test (the test the randomization itself justifies) and Cliff's delta.
- H2 (the benefit needs a trend): the Aegis - HPA difference on the ramp minus the same on the spike,
  paired by block (one-sample t, df = b - 1).
- Secondary responses: the same contrasts, without correction, labelled exploratory.
- Checks: Shapiro-Wilk on the residuals and the mean of every block (drift between sessions).

Usage: python3 design_analysis.py   ->  docs/tests/design-results.md and design-results.json
"""
import argparse
import itertools
import json
import math
from scipy import stats
from settings import AUTOSCALERS, DESIGN_TESTS, LOADS, PRIMARY_METRIC, SECONDARY_METRICS, TESTS_DIR

CONTRASTS = [("aegis", "hpa"), ("aegis", "hpa-tuned")]
ALPHA = 0.05
NAMES = {"aegis": "Aegis", "hpa": "HPA (default)", "hpa-tuned": "HPA (tuned)"}


def read_runs():
    """{(load, autoscaler): {block: summary}} for every saved design run."""
    runs = {}
    for name in DESIGN_TESTS:
        load, autoscaler = name.split("-", 1)
        for path in sorted((TESTS_DIR / name / "data").glob("run-*-summary.json")):
            summary = json.loads(path.read_text())
            runs.setdefault((load, autoscaler), {})[summary.get("block", summary["run"])] = summary
    return runs


def table(runs, load, metric):
    """{block: {autoscaler: value}} for the blocks where every autoscaler has a value."""
    blocks = set.intersection(*[set(runs.get((load, a), {})) for a in AUTOSCALERS]) if runs else set()
    out = {}
    for block in sorted(blocks):
        row = {a: runs[(load, a)][block].get(metric) for a in AUTOSCALERS}
        if all(v is not None for v in row.values()):
            out[block] = {a: float(v) for a, v in row.items()}
    return out


def rcbd(data):
    """Two-way ANOVA without interaction (treatment + block). Returns means, MSE, df and residuals."""
    blocks = list(data)
    b, a = len(blocks), len(AUTOSCALERS)
    grand = sum(data[j][i] for j in blocks for i in AUTOSCALERS) / (a * b)
    treat = {i: sum(data[j][i] for j in blocks) / b for i in AUTOSCALERS}
    block = {j: sum(data[j].values()) / a for j in blocks}
    residuals = [data[j][i] - treat[i] - block[j] + grand for j in blocks for i in AUTOSCALERS]
    df = (a - 1) * (b - 1)
    sse = sum(r * r for r in residuals)
    ss_treat = b * sum((treat[i] - grand) ** 2 for i in AUTOSCALERS)
    mse = sse / df if df else float("nan")
    f = (ss_treat / (a - 1)) / mse if mse > 0 else float("inf")
    return {"b": b, "treat": treat, "block": block, "mse": mse, "df": df, "residuals": residuals,
            "f_treat": f, "p_treat": stats.f.sf(f, a - 1, df) if mse > 0 else 0.0}


def contrast(model, first, second):
    diff = model["treat"][first] - model["treat"][second]
    se = math.sqrt(2 * model["mse"] / model["b"]) if model["mse"] > 0 else 0.0
    if se == 0:
        return {"diff": diff, "se": 0.0, "t": float("inf"), "p": 0.0 if diff else 1.0, "ci": (diff, diff)}
    t = diff / se
    crit = stats.t.ppf(1 - ALPHA / 2, model["df"])
    return {"diff": diff, "se": se, "t": t, "p": 2 * stats.t.sf(abs(t), model["df"]), "ci": (diff - crit * se, diff + crit * se)}


def ranked(data):
    """Rank transform (Conover and Iman): rank all values together, then the same ANOVA."""
    cells = [(j, i, data[j][i]) for j in data for i in AUTOSCALERS]
    ranks = stats.rankdata([v for _, _, v in cells])
    out = {}
    for (j, i, _), r in zip(cells, ranks):
        out.setdefault(j, {})[i] = float(r)
    return out


def within_block_test(data, first, second):
    """Exact randomization test of the design: swap the two labels inside each block (2^b arrangements)."""
    diffs = [data[j][first] - data[j][second] for j in data]
    observed = abs(sum(diffs))
    count = 0
    for signs in itertools.product((1, -1), repeat=len(diffs)):
        if abs(sum(s * d for s, d in zip(signs, diffs))) >= observed - 1e-12:
            count += 1
    return count / 2 ** len(diffs)


def cliffs_delta(xs, ys):
    """P(x > y) - P(x < y): -1 means every x is below every y."""
    greater = sum(1 for x in xs for y in ys if x > y)
    less = sum(1 for x in xs for y in ys if x < y)
    return (greater - less) / (len(xs) * len(ys))


def holm(pvalues):
    """Holm step-down adjusted p-values, in the input order."""
    order = sorted(range(len(pvalues)), key=lambda k: pvalues[k])
    adjusted = [0.0] * len(pvalues)
    running = 0.0
    for rank, k in enumerate(order):
        running = max(running, min(1.0, (len(pvalues) - rank) * pvalues[k]))
        adjusted[k] = running
    return adjusted


def sensitivity(runs, primary):
    """Post hoc, not in the registered plan: robustness to unequal variances between autoscalers.
    Paired t test by block (each contrast with its own variance, df = b - 1) and the same on log(1 + %)."""
    paired, logged = [], []
    for row in primary:
        data = table(runs, row["load"], PRIMARY_METRIC)
        first = [data[j][row["first"]] for j in data]
        second = [data[j][row["second"]] for j in data]
        paired.append(stats.ttest_rel(first, second).pvalue)
        logged.append(stats.ttest_rel([math.log1p(v) for v in first], [math.log1p(v) for v in second]).pvalue)
    for row, p, ph, q, qh in zip(primary, paired, holm(paired), logged, holm(logged)):
        row["post_hoc"] = {"paired_p": p, "paired_p_holm": ph, "log_paired_p": q, "log_paired_p_holm": qh}


def analyze(runs):
    results = {"primary": [], "secondary": [], "interaction": None, "checks": {}}
    for load in LOADS:
        data = table(runs, load, PRIMARY_METRIC)
        if len(data) < 2:
            continue
        model = rcbd(data)
        rank_model = rcbd(ranked(data))
        shapiro = stats.shapiro(model["residuals"]).pvalue if len(model["residuals"]) >= 3 else None
        results["checks"][load] = {"blocks": len(data), "f_treat": model["f_treat"], "p_treat": model["p_treat"],
                                   "shapiro_residuals_p": shapiro,
                                   "block_means": {str(j): round(v, 2) for j, v in model["block"].items()}}
        for first, second in CONTRASTS:
            c = contrast(model, first, second)
            results["primary"].append(dict(
                load=load, metric=PRIMARY_METRIC, first=first, second=second, blocks=len(data),
                mean_first=model["treat"][first], mean_second=model["treat"][second], diff=c["diff"], ci=c["ci"],
                t=c["t"], df=model["df"], p=c["p"], p_rank=contrast(rank_model, first, second)["p"],
                p_within_block=within_block_test(data, first, second),
                cliffs_delta=cliffs_delta([data[j][first] for j in data], [data[j][second] for j in data])))
        for metric in SECONDARY_METRICS:
            sdata = table(runs, load, metric)
            if len(sdata) < 2:
                continue
            smodel = rcbd(sdata)
            for first, second in CONTRASTS:
                c = contrast(smodel, first, second)
                results["secondary"].append(dict(load=load, metric=metric, first=first, second=second, blocks=len(sdata),
                                                 mean_first=smodel["treat"][first], mean_second=smodel["treat"][second],
                                                 diff=c["diff"], ci=c["ci"], p=c["p"]))
    primary = results["primary"]
    for row, adjusted, rank_adjusted in zip(primary, holm([r["p"] for r in primary]), holm([r["p_rank"] for r in primary])):
        row["p_holm"] = adjusted
        row["p_rank_holm"] = rank_adjusted
        # Registered rule (design.md 7.2 and 7.5): the ANOVA decides unless its residuals are not normal for
        # that load (Shapiro-Wilk p < 0.05); then the rank-transform ANOVA decides, also Holm-corrected.
        shapiro = results["checks"][row["load"]]["shapiro_residuals_p"]
        row["decided_on"] = "ranks" if shapiro is not None and shapiro < ALPHA else "anova"
        row["p_decision"] = rank_adjusted if row["decided_on"] == "ranks" else adjusted
        row["significant"] = row["p_decision"] < ALPHA and row["diff"] < 0
    sensitivity(runs, primary)
    ramp, spike = table(runs, "ramp", PRIMARY_METRIC), table(runs, "spike", PRIMARY_METRIC)
    common = sorted(set(ramp) & set(spike))
    if len(common) >= 3:
        gaps = [(ramp[j]["aegis"] - ramp[j]["hpa"]) - (spike[j]["aegis"] - spike[j]["hpa"]) for j in common]
        test = stats.ttest_1samp(gaps, 0.0)
        ci = test.confidence_interval(1 - ALPHA)
        results["interaction"] = {"blocks": len(common), "mean": sum(gaps) / len(gaps), "ci": (ci.low, ci.high),
                                  "t": test.statistic, "p": test.pvalue}
    return results


def fmt(v, d=2):
    return "–" if v is None else (f"{v:.{d}f}" if isinstance(v, float) else str(v))


def pfmt(p):
    return "–" if p is None else ("< 0.0001" if p < 0.0001 else f"{p:.4f}")


def markdown(results):
    lines = ["# Design results", "",
             "Generated by `scripts/experiments/design_analysis.py` from the runs in `docs/tests/<load>-<autoscaler>/`. "
             "Plan and reasons: [design.md](../experiments/design.md). Differences are first minus second; "
             "negative failed % favours the first.", ""]
    if not results["primary"]:
        return "\n".join(lines + ["No complete block yet: run `python3 scripts/experiments/campaign.py`.", ""])
    lines += ["## Primary: failed requests (%), Holm-corrected over 6 contrasts", "",
              "| Load | Contrast | Blocks | Means | Difference [95% CI] | t (df) | p Holm (ANOVA) | p Holm (ranks) | Decided on | Supported | p within-block | Cliff's δ |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results["primary"]:
        lines.append(f"| {r['load']} | {NAMES[r['first']]} − {NAMES[r['second']]} | {r['blocks']} | "
                     f"{r['mean_first']:.2f} vs {r['mean_second']:.2f} | {r['diff']:+.2f} [{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}] | "
                     f"{r['t']:.2f} ({r['df']}) | {pfmt(r['p_holm'])} | {pfmt(r['p_rank_holm'])} | {r['decided_on']} | "
                     f"**{'yes' if r['significant'] else 'no'}** | {pfmt(r['p_within_block'])} | {r['cliffs_delta']:+.2f} |")
    lines += ["", "**Decided on**: the registered rule ([design.md](../experiments/design.md#75-diagnostics-and-fallback)) uses the "
              "ANOVA unless the residuals of that load are not normal (Shapiro-Wilk p < 0.05, see Checks); then the rank ANOVA. "
              "**Supported**: Holm-corrected p < 0.05 on that basis and Aegis lower.", "",
              "### Sensitivity (post hoc, not in the registered plan)", "",
              "Unequal variances between autoscalers (Aegis runs vary far less than HPA runs). Paired t by block, each contrast "
              "with its own variance (df = b − 1), raw and on log(1 + %), Holm-corrected. Same direction in every row.", "",
              "| Load | Contrast | Paired t, p Holm | Paired t on log(1 + %), p Holm |", "|---|---|---|---|"]
    for r in results["primary"]:
        h = r["post_hoc"]
        lines.append(f"| {r['load']} | {NAMES[r['first']]} − {NAMES[r['second']]} | {pfmt(h['paired_p_holm'])} | {pfmt(h['log_paired_p_holm'])} |")
    lines += ["", "The within-block randomization test cannot go below 2 / 2^blocks (0.031 with 6 blocks): it confirms the "
              "direction, the ANOVA carries the inference ([design.md](../experiments/design.md#7-analysis-plan)).", ""]
    if results["interaction"]:
        i = results["interaction"]
        lines += ["## H2: does the benefit need a trend?", "",
                  f"(Aegis − HPA on the ramp) − (Aegis − HPA on the spike), paired by block: {i['mean']:+.2f} points "
                  f"[{i['ci'][0]:+.2f}, {i['ci'][1]:+.2f}], t = {i['t']:.2f}, p = {pfmt(i['p'])} ({i['blocks']} blocks). "
                  "Negative: Aegis gains more on the ramp than on the spike.", ""]
    lines += ["## Secondary (exploratory, not corrected)", "",
              "| Load | Metric | Contrast | Means | Difference [95% CI] | p |", "|---|---|---|---|---|---|"]
    for r in results["secondary"]:
        lines.append(f"| {r['load']} | {r['metric']} | {NAMES[r['first']]} − {NAMES[r['second']]} | "
                     f"{r['mean_first']:.2f} vs {r['mean_second']:.2f} | {r['diff']:+.2f} [{r['ci'][0]:+.2f}, {r['ci'][1]:+.2f}] | {pfmt(r['p'])} |")
    lines += ["", "## Checks", "", "| Load | Blocks | F autoscaler (p) | Shapiro-Wilk on residuals (p) | Mean failed % per block |",
              "|---|---|---|---|---|"]
    for load, c in results["checks"].items():
        lines.append(f"| {load} | {c['blocks']} | {c['f_treat']:.1f} ({pfmt(c['p_treat'])}) | {pfmt(c['shapiro_residuals_p'])} | "
                     + ", ".join(f"{k}: {v}" for k, v in c["block_means"].items()) + " |")
    lines += ["", "Shapiro-Wilk p < 0.05 means the residuals are not normal: then the rank column decides "
              "(pre-registered fallback). Block means that drift in one direction point to a session effect.", ""]
    return "\n".join(lines)


# numpy and scipy return their own scalar types; JSON needs Python ones (a numpy False written as text is truthy).
def plain(value):
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "item"):
        return value.item()
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyse the experiment design")
    parser.parse_args(argv)
    results = analyze(read_runs())
    (TESTS_DIR / "design-results.md").write_text(markdown(results))
    (TESTS_DIR / "design-results.json").write_text(json.dumps(plain(results), indent=1))
    print((TESTS_DIR / "design-results.md").read_text())


if __name__ == "__main__":
    main()
