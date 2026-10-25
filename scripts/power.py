"""Sample-size calculator: `python -m scripts.power --rate 0.2 --effect 0.1` or `--n 46 --rate 0.2`."""
import argparse

from core.shared.power import min_detectable_effect, n_per_arm


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rate", type=float, required=True, help="baseline attack-success rate")
    ap.add_argument("--effect", type=float, help="drop to detect; prints items needed per arm")
    ap.add_argument("--n", type=int, help="independent items per arm; prints the smallest drop detectable")
    a = ap.parse_args()
    if a.effect is not None:
        print(f"{n_per_arm(a.rate, a.rate - a.effect)} independent items per arm to detect {a.rate:.2f} -> {a.rate - a.effect:.2f} (5% two-sided, 80% power)")
    if a.n is not None:
        mde = min_detectable_effect(a.n, a.rate)
        print("no drop is detectable with that few items" if mde is None else f"with {a.n} items per arm the smallest detectable drop from {a.rate:.2f} is {mde:.2f}")


if __name__ == "__main__":
    main()
