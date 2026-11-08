"""fidetype: a trust layer for neural text entry.

The package reads decoder output in one standard format, the
NeuralTextStream. It then calibrates the output, abstains when unsure,
offers n-best choices and guards against hallucination.
"""

__version__ = "0.0.1"
