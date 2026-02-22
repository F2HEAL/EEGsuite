# 🧠 Academic EEG Research Pipeline --- Copilot Instructions

## 🎯 Research Objective

Perform, process, and analyze EEG measurements in the study of
Parkinson's Disease.

This repository must remain:

-   Reproducible
-   Deterministic
-   Peer-review ready
-   Computationally rigorous
-   Cross-platform compatible

These constraints override convenience.

------------------------------------------------------------------------

# 🚨 GLOBAL ENFORCEMENT RULES (ALWAYS APPLY)

## 0️⃣ Style Guide

-   Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) as strictly as possible.
-   Adhere to naming conventions (snake_case for functions/variables, PascalCase for classes).
-   Limit line lengths to 80 characters where possible.

## 1️⃣ Determinism

ALWAYS define at top of file:

``` python
RANDOM_SEED: int = 42
```

-   ALWAYS set seed explicitly when randomness is used.
-   NEVER rely on implicit randomness.
-   Outputs must be reproducible across runs.

------------------------------------------------------------------------

## 2️⃣ Path Handling

-   NEVER hardcode file paths as strings.
-   ALWAYS use pathlib.Path.
-   All paths must be OS-independent.

### ✅ Correct

``` python
from pathlib import Path

data_path: Path = Path("data") / "raw" / "subject_01.csv"
```

### ❌ Incorrect

``` python
data_path = "data/raw/subject_01.csv"
```

------------------------------------------------------------------------

## 3️⃣ Logging (No print)

-   NEVER use `print()` for general status or debugging.
-   ALWAYS use Python `logging` module for event tracking.
-   **EXCEPTION**: When implementing progress bars for long-running operations, `print()` statements (or `tqdm`) may be used to provide real-time terminal feedback.
-   Configure logging at module level.

### Example

``` python
import logging

logger = logging.getLogger(__name__)
logger.info("Processing subject %s", subject_id)
```

------------------------------------------------------------------------

## 4️⃣ No Magic Numbers

-   NEVER embed unexplained numeric literals.
-   ALL constants must be defined at top of file.

### Example

``` python
ALPHA_BAND: tuple[float, float] = (8.0, 12.0)
FILTER_ORDER: int = 4
```

------------------------------------------------------------------------

## 5️⃣ Type Safety

-   ALL functions must use full type hints.
-   ALL return types must be declared.
-   Use explicit types (avoid implicit Any).

------------------------------------------------------------------------

## 6️⃣ Documentation Standard

-   ALWAYS use Google-style docstrings.
-   Document:
    -   Purpose
    -   Args
    -   Returns
    -   Raises (if applicable)

### Required Template

``` python
def example_function(
    signal: np.ndarray,
    sampling_rate: float,
) -> float:
    """
    Short description of what the function does.

    Args:
        signal: Description of signal.
        sampling_rate: Sampling frequency in Hz.

    Returns:
        Description of returned value.
    """
```

------------------------------------------------------------------------

# 🧱 Architectural Principles

-   Prefer small, pure functions.
-   One responsibility per function.
-   Avoid long procedural scripts.
-   Avoid hidden state.
-   Avoid global mutable variables.
-   Explicit \> implicit.

------------------------------------------------------------------------

# 📊 Scientific Integrity Rules

When implementing:

-   Signal processing
-   Filtering
-   FFT / spectral methods
-   Statistics
-   Machine learning
-   Feature extraction

You MUST:

1.  Briefly describe the mathematical method in the docstring.
2.  Ensure deterministic behavior.
3.  Avoid silent numerical instability.
4.  Suggest a minimal unit test.
5.  Validate input shapes explicitly.
6.  Raise clear errors instead of failing silently.

------------------------------------------------------------------------

# 🧪 Mandatory Unit Test Suggestion

After any non-trivial mathematical function, append:

"Suggested unit test:"

Provide a minimal deterministic example using synthetic data.

Example:

``` python
# Suggested unit test:
# Use a pure 10 Hz sine wave sampled at 1000 Hz.
# Alpha bandpower should be significantly higher than beta bandpower.
```

------------------------------------------------------------------------

# 📁 Environment & Dependency Discipline

-   Assume dependencies are locked in requirements.txt.
-   Do NOT introduce new libraries unless necessary.
-   If introducing one, justify why.

------------------------------------------------------------------------

# 🧠 EEG-Specific Expectations

-   Always specify sampling_rate explicitly.
-   Never assume channel ordering.
-   Avoid implicit re-referencing.
-   Clearly define filter bands.
-   Avoid data leakage in ML pipelines.
-   Separate preprocessing from modeling.

------------------------------------------------------------------------

# 🧩 Verification Checklist (Self-Check Before Output)

Before generating code, verify:

-   [ ] RANDOM_SEED defined
-   [ ] No print()
-   [ ] Uses logging
-   [ ] Uses pathlib for paths
-   [ ] No magic numbers
-   [ ] Full type hints
-   [ ] Google-style docstrings
-   [ ] Deterministic logic
-   [ ] Modular design
-   [ ] Unit test suggested (if mathematical)

If any box is unchecked → revise output.

------------------------------------------------------------------------

# 🏛 Academic Standard Reminder

Code in this repository should be:

-   Suitable for publication
-   Clear to peer reviewers
-   Reproducible by external labs
-   Transparent in assumptions
-   Explicit in methodology

Clarity and rigor are more important than brevity.
