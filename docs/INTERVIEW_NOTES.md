# Interview notes

For each major decision: what I chose, why, the tradeoff, and what I would change at scale. Written
so a beginner can study it. Terms in *italics* are worth looking up.

## 1. A hint ladder instead of "give me a hint"
**Chose:** four fixed levels: a reflective question, a pointer to my notes (with page numbers),
where my reasoning goes wrong, then a fill-in-the-blank scaffold. **Why:** research on *retrieval
practice* says struggling a bit before getting help makes learning stick, so help should start
vague and get specific only when asked. A ladder also makes help *measurable*: "deepest level used"
is a clean number. **Tradeoff:** four levels is arbitrary, and some students need level 3 straight
away; I don't let them skip because skipping would blur the metric. **At scale:** I'd A/B test the
number and wording of levels against real learning outcomes instead of guessing.

## 2. The rubric never leaves the server
**Chose:** each question has a hidden rubric (key points) and misconceptions; student-facing
responses use their own response models, built field by field. **Why:** if a field exists on the
response model, someone will eventually return it by accident. Making it structurally impossible
(plus tests that scan the OpenAPI schema and real responses) is safer than remembering not to.
**Tradeoff:** a little duplication between database models and response models. **At scale:** I'd
add an automated contract test in CI for every new endpoint and consider a separate service for
grading so the rubric lives behind a network boundary.

## 3. A heuristic leak check on hints and feedback
**Chose:** reduce text and each rubric point to meaningful words and reject anything that repeats
most of a key point (or much of the whole rubric); regenerate once, then fall back to a generic hint.
**Why:** the model is helpful by nature and may just give the answer, or be talked into it, so I
don't trust its output. **Tradeoff:** it's a word-overlap heuristic: a good paraphrase can slip
through and a harmless hint is sometimes rejected. **At scale:** I'd add an embedding-similarity
check or a second model as a judge, and track how often hints fall back to measure model quality.

## 4. LLM-as-judge grading, with guard rails
**Chose:** a model grades each answer 0-1 against the rubric, returning strict JSON that is
validated before anything is stored. **Why:** grading free-text explanations with code isn't
practical. **Tradeoff:** it's noisy (same answer, different score), can be swayed by confident
wording or hidden instructions, and differs between model versions. I reduce this with a fixed
rubric, a 0.8 pass mark, untrusted-data framing for the answer, storing the grader model and prompt
version with each grade, and treating one score as one noisy sample. **At scale:** human-labelled
test sets to measure agreement, several graders and averaging, and calibration over time.

## 5. effective_score = rubric score x hint factor
**Chose:** the stored score is the best rubric score multiplied by 1.0 / 0.85 / 0.65 / 0.4 / 0.4
for hint levels 0-4, and 0 if the answer was revealed. **Why:** reaching 0.9 alone shows stronger
knowledge than reaching 0.9 after three hints, and the app's goal is independence. **Tradeoff:**
too harsh a penalty discourages asking for help, so level 1 costs only 15%; the exact factors are
my tuning guesses, not research-backed values. **At scale:** fit the factors from data (how well
does each help level predict later unaided success?).

## 6. Mastery as an exponential moving average
**Chose:** `new = 0.7 * old + 0.3 * latest`, with the first attempt taking its score. **Why:** one
stored number per concept, recent results matter more, an early bad score fades as you improve, and
a single noisy grade can't wreck it. **Tradeoff:** 0.7/0.3 is a tuning choice, and an EMA doesn't
model forgetting over time. **At scale:** a real memory model (spaced-repetition scheduling or
*item response theory*) that also predicts when mastery will decay.

## 7. What counts as a "gap" and as "independent"
**Chose:** gap = mastery below 0.6 after at least 2 attempts, or the same misconception on the two
most recent completed attempts. Independent = completed, hint level at most 1, not revealed.
**Why:** simple rules I can explain in one sentence, and the "same mistake twice" rule catches a
stuck belief even when the average looks fine. **Tradeoff:** hard thresholds create cliffs (0.59 vs
0.60). The rules exist in Python and in SQL, so I wrote tests that run both on the same data and
require the same answer. **At scale:** one definition in one place (for example a metrics layer)
rather than two implementations kept aligned by tests.

## 8. Bronze / silver / gold, in plain SQL
**Chose:** the app writes raw tables and an append-only event log (bronze); one SQL file makes a
clean row-per-attempt table with shared definitions (silver); small tables shaped for each chart
(gold). **Why:** every number has one definition, and a wrong chart is debugged by checking gold
against silver against bronze. **Tradeoff:** plain SQL files and a short Python runner are easy to
read but have no scheduling, dependency tracking, lineage or alerting. **At scale:** dbt (or
similar) for dependencies and tests, an orchestrator, and a separate analytics warehouse so queries
don't compete with the app.

## 9. Full refresh instead of incremental
**Chose:** every pipeline run drops and rebuilds silver and gold in one transaction. **Why:** it is
simple and obviously correct, and takes milliseconds at demo size. **Tradeoff:** cost grows with
total history, and a rebuild briefly holds locks. **At scale:** incremental models that only
process new or changed attempts, partitioned by day, with a periodic full rebuild as a safety net.

## 10. TEXT + CHECK instead of Postgres enums
**Chose:** status-like columns are `TEXT` with a named `CHECK (... IN (...))` constraint, and
numeric ranges use `BETWEEN`. **Why:** the database rejects bad values even if my code has a bug,
and changing the allowed list is a simple constraint swap, while changing an `ENUM` type is awkward
in migrations. **Tradeoff:** slightly more storage and no type-level documentation. **At scale:**
the same; the constraints are cheap, and I'd keep them.

## 11. An append-only events table with no foreign keys
**Chose:** `events_raw` records what happened (question served, hint requested, answer graded, ...)
with ids stored as plain numbers, not foreign keys. **Why:** an event log is history, so deleting a
document shouldn't erase it or be blocked by it, and writing events must never fail because of a
constraint. **Tradeoff:** dangling ids are possible, so the pipeline joins defensively. **At
scale:** stream events through a queue to a warehouse and validate them against a schema.

## 12. A fake LLM mode
**Chose:** one client interface with a deterministic offline implementation (the default) and a
real Anthropic implementation. **Why:** tests run offline, free and identically every time; the
demo works without a key; tests can feed in malformed output to prove error handling; and I can
simulate a *compromised* model to test the leak check. **Tradeoff:** the fake can drift from real
model behavior, so passing tests don't prove the real model behaves; the UI shows a banner while
in demo mode so nobody mistakes placeholders for real output. **At scale:** a small suite that runs
against the real API on a schedule, recording and replaying responses.

## 13. Grounding questions in the student's own chunks
**Chose:** documents are split into chunks (with page numbers); concepts and questions are
generated only from those chunks, and every concept stores which chunks it came from. **Why:**
limiting the model to the notes reduces made-up content, and the chunk ids let hints say "see page
3 of your notes". **Tradeoff:** a concept that spans many chunks can lose context; scanned PDFs
aren't supported (no OCR). **At scale:** embeddings for retrieval across many documents and OCR for
scans.

## 14. One demo user and no authentication
**Chose:** every request acts as user id 1, shown as "You". **Why:** this is a learning project
under a deadline; authentication is its own project and would have crowded out the core ideas.
**Tradeoff:** the app is not safe to expose to the internet, and per-user ownership checks exist
but are only exercised for one user. **At scale:** real login (OAuth or session cookies), per-user
authorization on every query, rate limiting, and an audit log.

## 15. Frontend data fetching with TanStack Query
**Chose:** server data (documents, mastery, analytics) is fetched and cached by TanStack Query,
and each dashboard section sits inside an error boundary with a retry. **Why:** it handles
loading, error, caching and refetching so components stay small, and one broken chart doesn't blank
the page. **Tradeoff:** one more concept to learn, and cache keys must be managed carefully.
**At scale:** generated API types from the OpenAPI schema so the frontend and backend can't drift.
