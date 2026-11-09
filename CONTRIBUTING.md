# Contributing

Start with README.md and docs/MODEL.md. Keep plant truth inaccessible to controllers
except through documented measurement channels. Explain units, time conventions,
assumptions and failure behavior alongside new code.

For numerical changes, provide a hand calculation, invariant or convergence check
that can fail independently of the implementation. Run `python -m unittest discover
-s tests -v`. For viewer changes, run `node tests/web_contract.cjs`; browser testing
is a separate check and this mock-DOM contract test does not replace it.

Changes to the model, faults or policies require re-running the affected benchmark,
figures and replay export. Preserve all paired seeds and failed runs. Do not tune
on the same outputs later described as an independent evaluation. Describe changes
to the protocol and retain a machine-readable environment record.

Do not upload patient information, credentials, proprietary device algorithms,
medical-device control interfaces or third-party figures. New clinical claims
need primary evidence and a clear distinction between model output and observation.

Open an issue with the command, software versions, seed, expected behavior and
actual behavior for a reproducibility problem. Include a minimal synthetic case.
