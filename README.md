# ccf-srs — CCF Self-Report Server (Reference Implementation)

*One provider's way of speaking the framework. Not the framework.*

## Thirty seconds to runtime

1. Serve your `report.json` with this server:
   `python3 ccrfc-self-report-server.py --report report.json --port 8000`
2. Your report appears at `/.well-known/ccrfc-report` and in the `/handshake` declaration. Both doors, byte-identical.
3. Done. Forget it until your handling changes.

Implements the [Cognitive Commons Framework](https://github.com/JohnHenryUS/ccf) — read the RFCs there. This repo is code only: the server, a sample report, and the test driver.

## Files

- `ccrfc-self-report-server.py` — stdlib-only, no dependencies. Both doors, 304-on-match, 404 clean, refuses to start on checksum mismatch.
- `report.json` — canonical sample report. Copy it, fill your values, recompute the checksum.
- `test_srs.py` — live test driver. 10 cases: 200, ETag, 304, both 404s, first-contact, match-304, mismatch-refetch, refusal-to-start. Re-run against your own implementation before claiming conformance.

## Verification

Live-tested Oct 18: 10/10 passing against the sample report. See the framework's PROVIDER_README for the full record.

Read it, steal from it, replace it.

**License:** MIT. See LICENSE.
