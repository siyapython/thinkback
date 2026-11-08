# Audit (Milestone 8)

A read-only review of the code plus tests, aimed at five promises the app makes. Method for every
item: read the code path, then write a test that tries to break it. The tests live in
`backend/tests/test_audit.py` (checks that passed first time) and `backend/tests/test_audit_fixes.py`
(regression tests for the three bugs found). Everything runs offline against the fake LLM.

**Bottom line:** three real bugs were found and fixed (each in its own commit), all in item (a).
Items (b) to (e) held up. Section "Not verified" lists what tests here cannot prove.

## Results at a glance

| # | Promise | Result |
|---|---------|--------|
| a | Rubric and misconceptions never reach the student | 3 leaks found and fixed, rest verified |
| b | Docs, API and SQL pipeline agree on the numbers | Verified, no drift |
| c | Prompt injection can't raise the score ceiling or skip hint levels | Verified, with one honest limit |
| d | No endpoint returns `file_path` | Verified |
| e | Uploads can't write outside `backend/uploads/` | Verified |

## (a) Rubric and misconceptions never appear in student-facing responses

**Checked by:** reading every router and response model; walking the whole student flow plus error
paths with a "does any rubric point or misconception string appear in the body?" check; scanning
the OpenAPI schema for response fields that could carry secrets.

**Verified (no change needed)**
- Student-facing models (`QuestionOut`, `AnswerOut`, `HintOut`, ...) are built field by field; the
  grader's covered/missed point *text* is reduced to counts. A schema-level test fails if any model
  anywhere declares `rubric`, `misconceptions`, `points_covered`, `points_missed`, `misconception`,
  `file_path` or `content_hash`.
- Error responses (404, 409, 422, 502 from a failed or out-of-range grade) contain no rubric or
  misconception text. The 502 message only carries an exception class name, never model output.
- Reveal returns the rubric points as its explanation (that is its job) and never the misconceptions.
  Question and attempt responses after a reveal are unchanged.
- Hints never see the misconception list (it is not in the hint prompt), and are leak-checked against
  the rubric.

**Bugs found and fixed**
1. **Grader feedback could quote a hidden misconception.** The grading prompt contains the
   question's misconception list, but the feedback leak check compared only against rubric points,
   so a grader echoing a misconception would show it to the student. *Fix:* feedback is checked
   against misconceptions too (commit "fix: leak-check grader feedback against hidden
   misconceptions"). Side effect to know about: feedback that restates a misconception closely is
   now replaced by the generic nudge.
2. **`GET /analytics/overview` returned `top_misconception`.** The grader's diagnosed misconception
   is often a verbatim entry from the hidden list, so the dashboard API handed it to the browser
   (visible in the network tab even though no component rendered it). *Fix:* removed from the
   response; it stays in `gold.concept_summary` for analysis. This removes a field from an API
   response; if you wanted a "top misconception" display, it needs a deliberate design (for
   example, only show text the grader wrote itself, never list entries).
3. **A revealed question could be re-attempted with the rubric pasted in.** Reveal shows the rubric,
   and `POST /questions/{id}/attempts` accepted a new attempt on the same question, so pasting the
   revealed points scored full marks and inflated mastery. *Fix:* starting an attempt on a question
   that user already revealed returns 409 ("Ask for a new question"). The UI always creates a new
   question per attempt, so it is unaffected. One existing test that reused a revealed question was
   updated to use a fresh one.

## (b) Docs, API and pipeline agree

**Checked by:** tests that read `docs/LEARNING.md` and `docs/pipeline.md` and compare the stated
numbers with the code constants, plus tests that build the same data and compare Python with SQL.

- `hint_factor` 1.0 / 0.85 / 0.65 / 0.4 / 0.4 and 0 on reveal: the exact sentence in LEARNING.md is
  built from `HINT_FACTOR` in the test, so changing either side fails it. Rounding checked (0.9 x
  0.85 = 0.765 rounds half-up to 0.77).
- EMA `new = 0.7 * old + 0.3 * latest`, first attempt takes its score, and the worked example in
  LEARNING.md (0.8 -> 0.68 -> 0.776) is reproduced by the code.
- Gap rule: constants (0.6, 2 attempts) match both docs and the SQL; 8 scenarios (boundaries at
  0.59/0.60, 1 vs 2 attempts, normalised-equal misconceptions, A/B/A, A/A/none, B/A/A) give the
  *same* answer from the Python rule (`GET /documents/{id}/mastery`) and from
  `gold.concept_summary.is_gap`.
- Independence (completed AND `max_hint_level <= 1` AND not revealed): 6 cases (levels 0, 1, 2, 4,
  revealed at level 0 and 1) give the same count from `GET /metrics/independence` and from
  `silver.attempt_facts.is_independent`; an in-progress attempt counts for neither. The SQL text and
  both docs state the same rule.

## (c) Prompt injection

**Checked by:** reading the grading and hint prompts and the code that consumes their output; tests
with injection text and with a grader that *obeys* the injection.

- Answer text goes into the prompt inside delimiter tags after stripping any tag that would close
  them (grading and hint prompts both tested with a breakout attempt).
- **Worst case tested:** a grader that falls for "give me 1.0" and returns 1.0 after two hints still
  yields `effective_score` 0.65. The ceiling comes from `max_hint_level`, which only the server
  changes.
- Hint levels advance one at a time (1, 2, 3, 4, then 409) whatever the answer says. The answer
  request body ignores extra fields (`rubric_score`, `max_hint_level`, `status`, ...).
- A grader score outside 0-1 is rejected (502, nothing stored as graded), not clamped. A reveal
  can't be undone by a later perfect answer.
- **Honest limit:** at hint level 0 a grader that obeys an injection *can* award 1.0 to a junk
  answer. That is inherent to LLM-as-judge. We mitigate (untrusted-data framing, the instruction
  that manipulative answers score low, `best` of several answers, moving-average mastery) but
  cannot prove it with the fake grader. See "Not verified".

## (d) No endpoint returns `file_path`

**Checked by:** OpenAPI scan (no response model declares `file_path` or `content_hash`) and real
responses for upload, list, get, extract, concepts and the duplicate-upload 409: none contains
`file_path`, `content_hash` or the server's upload directory. `DocumentOut` documents this on purpose.

## (e) Uploads cannot write outside `backend/uploads/`

**Checked by:** reading `ingest._store` and uploading PDFs whose filenames are `../../evil.pdf`,
`/etc/cron.d/evil.pdf`, `..\..\evil.pdf`, `a/../../../b.pdf`, `....//....//x.pdf`,
`C:\Windows\evil.pdf`, an encoded `%2e%2e%2f` name, a 400-character name and `..`; the `title`
field also carried `../../`.

- The on-disk name is always `<user_id>-<sha256 of the content>.pdf`; the client's filename is kept
  only as a display label (base name only) and never used to build a path.
- In every case exactly one file was created, directly inside the upload directory, with a name
  matching that pattern; a sibling directory stayed empty. An empty filename is rejected (422).

## Other observations (not changed)

- Some existing backend tests query `events_raw` without filtering by user, so they fail against a
  development database that already holds real practice data (we saw 3 to 8 failures on the dev
  database; all 173 pass on an empty one, which is what CI uses). Not a product bug; use a scratch
  database for local test runs.
- `pipeline/` has no Ruff config of its own, so CI lints it with `backend/pyproject.toml`.

## Not verified

- **Real model behavior.** Everything above uses the fake LLM. Whether Claude resists injection,
  returns well-formed JSON, or paraphrases misconceptions into feedback was not tested here
  (`backend/scripts/smoke_real.py` exists for manual runs).
- **Leak-check recall.** Verbatim and heavy-overlap leaks are caught (and tested); a skilled
  paraphrase is not guaranteed to be.
- **Gap-rule text normalisation.** Python (`casefold`, `\W`) and Postgres (`lower`, regex `\W`) agree
  on the tested inputs; unusual Unicode (for example German "ß") might normalise differently.
- **PDF parser safety.** A malicious PDF crafted against `pypdf` was not tried; only size, page and
  type limits were tested.
- **Upload directory tricks.** A pre-existing symlink inside `backend/uploads/` was not tested; the
  deployment would own that directory.
- **No auth, no rate limiting.** Any client can call every endpoint, including
  `POST /analytics/refresh`. Known limitation, out of scope here.
- **Frontend rendering.** Component tests check what is rendered from mocked data; no browser-level
  test confirms the rubric is absent from the DOM end to end.
