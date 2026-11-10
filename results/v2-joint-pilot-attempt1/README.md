# Interrupted output serialization

All 40 traces completed. Saving aggregate metrics failed because a NumPy integer was not JSON serializable. This archive retains the original protocol, driver, log and hashes of all 40 original traces. The final pilot repeats the identical numerical controller and cases with a JSON scalar conversion fix; the validator checks that every trace hash matches this first attempt. This is an output-handling failure, not another selected controller or an additional independent cohort.

The second execution saved all metrics and checksums successfully, then hit the same NumPy conversion issue only in its console summary. Its protocol, driver and log are also retained. The final driver prints the already serialized summary file. All numerical traces are required to match the initial trace hashes.
