import numpy as np


def cliffs_delta(x, y):
  """Compute Cliff's Delta effect size."""
  x = np.array(x)
  y = np.array(y)

  n_x = len(x)
  n_y = len(y)

  greater = sum((xi > yj) for xi in x for yj in y)
  less = sum((xi < yj) for xi in x for yj in y)

  return (greater - less) / (n_x * n_y)

def interpret_cliffs_delta(d):
  d = abs(d)
  if d < 0.147:
    return "negligible"
  elif d < 0.33:
    return "small"
  elif d < 0.474:
    return "medium"
  else:
    return "large"


def format_p(p):
  if p < 0.001:
    return "< 0.001"
  else:
    return f"{p:.3f}"