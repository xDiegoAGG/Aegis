import json
from charts import deficit_seconds, plot_evidence, plot_summary, read_timeline
from compare import complete
from report import load_test
from settings import TESTS_DIR

# Evidence figures of the gradual ramp: test 1 (Aegis) and test 3 (HPA only) with the same load.
AEGIS_TEST = "test1-linear-ramp"
HPA_TEST = "test3-hpa-baseline"


# The median run of a test by failed requests (the representative one), plus every run.
def runs_of(name):
    folder = TESTS_DIR / name
    summaries, runs = load_test(folder)
    if not summaries:
        return None, []
    order = sorted(range(len(summaries)), key=lambda i: summaries[i]["failed_percent"])
    index = order[(len(order) - 1) // 2]
    summary = complete(summaries[index], runs[index])
    timeline = read_timeline(folder, summary["run"])
    summary["deficit_s"] = deficit_seconds(runs[index], summary, timeline)
    return (summary, runs[index], timeline), summaries


def main():
    aegis, aegis_all = runs_of(AEGIS_TEST)
    hpa, hpa_all = runs_of(HPA_TEST)
    if aegis is None or hpa is None:
        print("evidence: test 1 and test 3 are both needed")
        return
    repeats = list(aegis_all)
    extra = TESTS_DIR / AEGIS_TEST / "data" / "repeat-runs-summary.json"
    if len(aegis_all) == 1 and extra.exists():
        repeats += json.loads(extra.read_text())
    for lang, suffix in (("en", ".png"), ("es", ".es.png")):
        plot_evidence(TESTS_DIR / ("evidence" + suffix), aegis, hpa, lang)
        plot_summary(TESTS_DIR / ("summary" + suffix), aegis[0], hpa[0], repeats, hpa_all, lang)
    print("evidence: Aegis", aegis[0]["deficit_s"], "s above capacity, HPA", hpa[0]["deficit_s"], "s")


if __name__ == "__main__":
    main()
