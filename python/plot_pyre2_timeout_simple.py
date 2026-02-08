import matplotlib.pyplot as plt

RAW_DATA = """
None, 0.00013256072998046875
None, 3.0994415283203125e-06
None, 1.430511474609375e-06
None, 1.1920928955078125e-06
None, 1.1920928955078125e-06
None, 1.6689300537109375e-06
None, 3.0994415283203125e-06
None, 5.245208740234375e-06
None, 8.344650268554688e-06
None, 1.5974044799804688e-05
None, 3.0517578125e-05
None, 6.127357482910156e-05
None, 0.00012230873107910156
None, 0.00024199485778808594
None, 0.0004878044128417969
None, 0.0010447502136230469
None, 0.0024900436401367188
None, 0.004483938217163086
None, 0.007972478866577148
None, 0.016557931900024414
None, 0.03325486183166504
None, 0.06627798080444336
None, 0.13461518287658691
None, 0.2704160213470459
None, 0.5469763278961182
None, 1.0881619453430176
None, 2.2021138668060303
None, 4.475754499435425
None, 9.167499303817749
None, 18.406904697418213
None, 36.722875118255615
""".strip()


def parse_timings(raw_data: str) -> list[float]:
    timings = []
    for line in raw_data.splitlines():
        _, timing_str = line.split(",", maxsplit=1)
        timings.append(float(timing_str.strip()))
    return timings


def main() -> None:
    timings = parse_timings(RAW_DATA)
    x_values = list(range(len(timings)))

    plt.figure(figsize=(10, 5))
    plt.plot(x_values, timings, marker="o", linewidth=1.5, markersize=4)
    plt.xlabel("Sample index")
    plt.ylabel("Time (seconds)")
    plt.title("run_pyre2_timeout_simple.py timings")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
