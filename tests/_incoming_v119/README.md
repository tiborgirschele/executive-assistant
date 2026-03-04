EA OS v1.19 test pack

Purpose
- Preserve all already-implemented safety and self-healing features.
- Add future-intelligence contract tests for profile, dossier, future situation,
  readiness, critical lane, and preparation planner behavior.

How to use
1. Unzip into the repository root or copy files into tests/.
2. Ensure the Python path includes the repo's `ea/` directory.
3. Run:
   pytest -q tests/test_v1_12_*.py tests/test_v1_19_*.py
4. For e2e/golden journeys, run the repo's release-smoke wrappers or adapt the
   included e2e tests to your environment.

Notes
- These are contract tests. Some will fail until v1.19 implementation lands.
- "Operational self-awareness" in this suite means confidence awareness,
  bounded recovery, and future-preparation behavior - not consciousness.
