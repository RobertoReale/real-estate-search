# Roadmap

What is known and not done. Every entry here was found by a review that had the evidence in
front of it and decided, deliberately, not to act — so each one carries the evidence and the
reason, not just the intention. An item with neither is a wish, and belongs in an issue
rather than in this file.

Two rules keep it honest:

- **A row states its blocker as plainly as its ambition.** A roadmap that lists only what
  would be nice is a wish list; the value is in what has to be solved first.
- **A row is removed when it is done or when it is withdrawn**, and a withdrawn row says
  why. Nothing accumulates here silently.

---

## Found by the backend review, not done

The review is [`audit.md`](audit.md) §2–§3 (correctness), §6 (security) and §7
(efficiency). It ran at the end of phase H — after the scan was rewritten and before the
interface was built on it — under a standing rule that it was a review and not a rewrite:
anything that would change behaviour a test asserts stops and becomes a row here.

### Idealista's own delay floor is overwritten by the scanner

`IdealistaScraper.__init__` raises whatever delay it is given to at least 8 seconds, with a
comment saying why ("DataDome is sensitive to request frequency"), and the availability
check applies the same idea properly — `max(request_delay_seconds, MIN_PROBE_DELAY[portal])`
in `services/availability_check.py`. The scan does not: `scanner._fetch_search` assigns
`scraper.delay_seconds = request_delay_seconds` *after* construction, so the floor is
silently discarded and Idealista is paged at the global 6-second default. `scanner`'s own
docstring for `_fetch_searches` states the floor as a fact, which makes this a place where
the code says one thing and does another.

**Why it was not fixed in the review.** Applying the floor changes what
`test_the_two_portals_are_read_at_once_and_neither_is_asked_faster` measures: Idealista
would then pace at 8 s against Immobiliare's test delay, the concurrency assertion
(`whole < serial * 0.75`) no longer holds arithmetically, and the suite grows by roughly
half a minute of real sleeping. That is a behaviour change with a test in front of it, which
is exactly the line the review was told not to cross.

**What doing it looks like.** A `min_delay_seconds` class attribute (0 on `BaseScraper`,
8 on `IdealistaScraper`), applied where the scanner sets the delay, plus a decision about
whether a configured `0` means "no pacing at all" — the offline sandbox relies on it, and
the availability check today does not honour it. The concurrency test then needs its two
delays chosen per host rather than globally.

### A scraped URL's scheme is checked where it is exported, and nowhere else

The HTML dossier now refuses to link anything that is not `http(s)` (`exporter._safe_url`,
`audit.md` §6.1). Two other consumers of the same field were deliberately left alone:

- **ingestion** — `scrapers/immobiliare.py` and `idealista.py` store whatever the portal's
  `href` or `seo.url` field held. Filtering there would protect every consumer at once, but
  the URL is also the identity two sightings of an ad are matched on (`listing_key`,
  `merge_scrapes`, `_already_seen`), so dropping or blanking one is a change to
  deduplication, not to rendering.
- **the frontend**, which renders the same value as a link. It is being replaced wholesale
  by phases B–E, so it is F.7's to read, not the backend review's.

### `_mark_vanished_properties` walks every active property in Python

`services/scanner.py` loads every `active`/`filtered` property and compares `last_seen_at`
row by row, where a single `UPDATE … WHERE last_seen_at < ?` would do it. It is a candidate
and not a change, because §7's rule applies: it runs **once per clean full scan**, not per
request, and no measurement shows it costs anything at the sizes this app holds. It is
recorded so that whoever does measure it at 100 000 properties finds it already named.
