from services.history import History
from services.timeutil import iso


def test_iso():
    assert iso(None) is None
    assert iso(0) == "1970-01-01T00:00:00Z"


def test_old_points_fall_out_of_the_window():
    h = History(window_s=10)
    for t in range(0, 30, 2):
        h.add("cpu", t, t=t)
    assert [p[0] for p in h.series("cpu")] == [18, 20, 22, 24, 26, 28]


def test_none_values_are_skipped_and_unknown_series_is_empty():
    h = History(window_s=10)
    h.add("temp", None, t=1)
    assert h.series("temp") == [] and h.series("nope") == []


def test_series_is_downsampled_by_bucket_mean():
    h = History(window_s=1000)
    for t in range(100):
        h.add("cpu", t, t=t)
    points = h.series("cpu", max_points=10)
    assert len(points) == 10
    assert points[0] == [9, 4.5]     # last timestamp of bucket, mean of 0..9
    assert points[-1] == [99, 94.5]
