# Data in and out

How entry lists, times and results get in and out as CSV, and how a whole event moves between servers as a bundle. Until the organiser console exists (Phase 4), use the **Data in/out** page on each event in the Django admin, the staff API (`/api/v1/staff/…`, see [`protocol/openapi.json`](../protocol/openapi.json)), or the management commands.

| What | Who (staff API) | Admin | API |
|---|---|---|---|
| Import entries | organiser | Event → Data in/out | `POST /staff/events/{id}/entries/import` |
| Download entries | organiser | Event → Data in/out | `GET /staff/events/{id}/entries.csv` |
| Import times | organiser | Event → Data in/out | `POST /staff/events/{id}/times/import` |
| Download results | volunteer | Event → Data in/out | `GET /staff/events/{id}/results.csv` |
| Download bundle | organiser | Event → Data in/out | `GET /staff/events/{id}/bundle` |
| Import bundle | owner | Events → Import bundle | `POST /staff/organisations/{slug}/events/import` |

Entry lists and bundles contain runners' personal details, which is why volunteers can't download them.

## Reading CSV files

Files from spreadsheets are accepted as they come:

- UTF-8 (with or without Excel's byte-order mark), falling back to Windows-1252
- Comma, semicolon or tab separators
- Header names in any case and spacing: `First name`, `FirstName` and `first_name` all mean the same column
- Blank rows are skipped. Columns the import doesn't use are listed back to you, so a typo in a header doesn't go unnoticed

Imports check the whole file first. **If any row has a problem, nothing is saved**, and every problem is reported with its line number (the header is line 1). A dry run checks a file without saving anything.

Exported cells that start with `=`, `+`, `-` or `@` get a `'` in front, so spreadsheet apps don't run them as formulas. Imports remove it again, so an exported file imports back unchanged.

## Entries

Rows are matched to existing entries **by bib**. Importing the same file twice changes nothing, and importing a corrected file updates people in place. Entries that aren't in the file are left alone.

| Column | Also accepted | Notes |
|---|---|---|
| `bib` | `BibNumber`, `race_number`, `number` | Required. Letters, digits and hyphens |
| `given_name` | `Firstname`, `forename` | Required, unless there's a `name` column |
| `family_name` | `Lastname`, `surname` | |
| `name` | `full_name` | Used when there are no separate name columns |
| `gender` | `sex` | `male`/`m`, `female`/`f`/`w`, `non_binary`/`nb`/`x`, blank for undisclosed. The legacy `other` becomes non-binary |
| `date_of_birth` | `dob` | `2001-04-30` or `30/04/2001` (day first) |
| `age` | | Age on race day, if there's no date of birth |
| `club` | `ClubName` | |
| `email` | | Only used to send results |
| `hide_name` | `anonymous` | `yes`/`no`. Shows the runner as "Anonymous" in results |
| `race` | | Race name. Optional when the event has one race, or when you pick a race for the whole file |
| `wave` | | Wave name. Needed for races with several waves |

Legacy columns `TeamName`, `AgeCategory` and `OldCategory` are accepted and ignored. Categories are worked out from the race's category scheme, not typed in. `status` is in exports for reference but isn't imported: statuses change through the review tools, so they're in the audit log.

**Downloads:** the native layout has the columns above plus `status`. `legacy=true` gives the old system's participant layout (`BibNumber,Firstname,Lastname,Gender,ClubName,TeamName,AgeCategory,Age`), with `AgeCategory` filled in from the category scheme.

## Times

Each row becomes a **manual read** at one timing point, with an audit-log entry saying which file it came from (plus any reason you give). The timing point defaults to the race's finish line. Results are rebuilt straight away. Rows whose read already exists (same timing point, bib and time) are skipped, so importing a file again is safe.

A file has a bib column and **exactly one** time column:

| Column | Also accepted | Meaning |
|---|---|---|
| `at` | `datetime` | ISO 8601 date and time: `2026-06-14T10:25:36.5`. Without an offset it's in the event's timezone |
| `clock` | `time`, `time_of_day` | Time of day (`10:25:36.5`) on the event's first day, in the event's timezone |
| `unix` | `timestamp`, `Result` | Seconds since 1970. The legacy bib detector's `BibNumber,Result,TrackerID,filename` files work as they are; rows with bib `-1` (unreadable) are skipped |
| `elapsed` | `total_time`, `gun_time` | Time since the runner's wave started (`25:36` or `0:25:36.97`). The legacy `race_number,total_time` files work as they are. The wave must have started |

## Results

Results come from the stored results, so they're always the same as what the system shows. Names follow each runner's "hide my name" choice, because results files get published. Times are truncated, never rounded up: `0:25:36.97` shows as `0:25:36`. Add `decimals=1` (up to 3) for fractions of a second.

The native layout is `race, position, bib, name, gender, category, gender_position, category_position, club, status, gun_time, net_time`, then one column per intermediate split. Finishers come first in position order, then everyone else. `legacy=true` gives the old system's `race_number,total_time` (finishers only, `HH:MM:SS`).

## Event bundles

A bundle is one event and everything in it, as a zip ([ADR 0002](decisions/0002-event-mode-and-accounts.md)). It moves an event between servers: cloud to venue laptop and back once event mode exists, or between two self-hosted installs today.

```
manifest.json                   format, schema version, the event, sha256 + size of every file
data/events.categoryscheme.jsonl
data/events.categoryrule.jsonl
data/events.event.jsonl
data/events.timingpoint.jsonl
data/events.race.jsonl
data/events.wave.jsonl
data/events.split.jsonl
data/events.entry.jsonl
data/timing.device.jsonl
data/timing.heartbeat.jsonl
data/timing.read.jsonl
data/timing.observation.jsonl
data/timing.adjustment.jsonl
media/crops/<event id>/<observation id>.jpg
```

Each data file has one row per line (`{"model", "pk", "fields"}`, like Django's serialiser), sorted by id. Times keep their microseconds, and rows keep their ids and `created_at`, so a bundle round-trips exactly.

**Importing** makes the event on this server match the bundle exactly:

- A new event is created in the organisation you import into. If the event is already here, you have to choose **replace**. Anything added here since the bundle was made is then lost. This is deliberate: during event mode only one copy of an event can be changed at a time.
- Importing the same bundle twice changes nothing.
- Category schemes belong to the organisation, so an import never changes one that's already here. New ones are added; if the name is taken, the bundle's one gets the event's name as a suffix.
- If the event's slug is taken by another event, pick a different one.

**What doesn't travel:**

- Pairing codes and device tokens. Phones pair again.
- Staff accounts. The audit log keeps who did what by email; the link to the account is kept only if that account exists on this server too.
- Stored results. They're rebuilt from the reads on import.

**Checks on import.** A bundle is checked before anything is saved:

- The manifest's format and schema version.
- Every file's checksum and size.
- No files other than the ones listed.
- Every row is the model its file says.
- Every field value is valid.
- Every link points to a row inside the bundle.
- No row's id belongs to another event here.

So a bundle can only ever write to its own event. A bundle made by a newer server (higher schema version) is refused with a message to update.

**Bundles hold runners' personal details** (names, dates of birth, emails). Treat them like a database backup.

### Commands

```bash
uv run python manage.py export_event exeter-harriers/riverside-10k -o riverside.bundle.zip
uv run python manage.py import_event riverside.bundle.zip exeter-harriers --replace
```

`import_event` also takes `--slug` to rename the event on the way in.
