"""Fidetype open benchmark v0.1 (milestone M5).

Score neural text entry from NeuralTextStream outputs, with fixed splits,
honest metrics and required controls. The package ships **no data and no
weights**: every dataset is download-only (see :mod:`.registry`).

- :mod:`.registry`: datasets (source, licence, version, checksum,
  download steps) and tracks (split, normaliser, CI unit, user model).
- :mod:`.splits`: the committed split files (ids, clusters, text hashes).
- :mod:`.prepare`: rebuild the local truth from your downloaded data.
- :mod:`.submission`: the submission format (NTS files + manifest).
- :mod:`.scoring`: CER / WER, eWPM vs the no-BCI reference, wrong-commit
  (marginal) and error among commits, commit rate, controls, cluster
  bootstrap CIs, guarantee reporting.
- :mod:`.harness`: one call / one command to score a folder.
- :mod:`.leaderboard`: the static leaderboard page.

Command line: ``python -m fidetype.benchmark --help``. Docs:
``benchmark/README.md`` and ``wiki/concepts/open-benchmark.md``.
"""

from fidetype.benchmark.registry import BENCHMARK_VERSION, DATASETS, TRACKS, Dataset, Track, UserModel, get_track

__all__ = ["BENCHMARK_VERSION", "DATASETS", "TRACKS", "Dataset", "Track", "UserModel", "get_track"]
