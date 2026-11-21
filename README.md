# BeatBee

BeatBee checks an ordered list of Discogs search queries, looking first for
**Master releases**. Only when the complete Master search finds no matches does
it run a Discogs release search as an album fallback. Release results are
diagnostic links, not Master matches. A local HTML report shows the results,
problems, and clickable Discogs links.

BeatBee **does not automatically create a Discogs list**: a supported write
interface for user lists has not been confirmed. When all results are
unambiguous, you can export a list and create it manually on Discogs.

## Requirements

- Python 3.11 or newer
- An internet connection and a Discogs account
- A personal Discogs token for API searches

The program uses the Python standard library; no additional packages are
required to start it using `main.py`.

## Create a Discogs token

1. Sign in to [Discogs](https://www.discogs.com/).
2. Open the [Discogs developer settings](https://www.discogs.com/settings/developers).
3. Under **Personal Access Token** or **User Token**, select **Generate token**
   to create a personal token. The labels may change.
4. Copy the token and treat it like a password.

Source: [Discogs API Authentication](https://www.discogs.com/developers/#page:authentication).

### Put the token in JSON

Create or edit `discogsToken.json` in the project directory:

```json
{
  "discogs_token": "YOUR_TOKEN_HERE"
}
```

The value is a placeholder: replace it with your own token.
`discogsToken.json` is listed in `.gitignore`. Do not share the token or upload
the file to Git or public logs. If a token is accidentally exposed, revoke it on
Discogs and create a new one.

### Alternative: environment variable

For the current PowerShell session:

```powershell
$env:DISCOGS_TOKEN = "YOUR_TOKEN_HERE"
```

`DISCOGS_TOKEN` takes precedence over the token file. Avoid storing real tokens
in scripts or shared terminal logs.

## Input: search list

Create or edit a UTF-8 file named `discogsList.json` in the project directory:

```json
{
  "list_name": "Meine Albumliste",
  "records": [
    {"artist": "Gábor Szabó", "release_title": "Dreams", "year": "1968"},
    {"artist": "Omega", "release_title": "10000 lépés", "year": "1969"}
  ]
}
```

| Field | Meaning |
| --- | --- |
| `list_name` | Nonempty list name; Unicode and spelling are preserved. |
| `records` | Nonempty, ordered list of search objects. Each object is a separate Discogs search. |
| `artist` | Artist search term. |
| `release_title` | Album or release title search term. |
| `year` | Release year as a string or integer. |
| `q` | General search term, optionally combined with other search fields. |

`artist`, `release_title`, `year`, and `q` are examples, not required fields.
Other currently accepted parameters are `title`, `genre`, `style`, `country`,
`format`, `label`, `catno`, `barcode`, `track`, `credit`, `anv`, `submitter`,
and `contributor`. Values must be nonempty strings or integers. A search object
must not be empty.

BeatBee first searches with `type=master`; `type: "master"` is optional in the
input, and other types are rejected. For the album fallback, BeatBee sets
`type=release` itself without changing the input. BeatBee manages `page` and
`per_page`. Unknown fields and invalid JSON are rejected before the first API
request. Order and duplicate entries are preserved.

## Running BeatBee

In the project directory:

```powershell
python main.py
```

Alternatively, with an existing virtual environment:

```powershell
.venv\Scripts\python.exe main.py
```

Without arguments, the program uses `discogsList.json` and the token from
`DISCOGS_TOKEN` or `discogsToken.json`. You can specify a different input file:

```powershell
python main.py validate my-list.json
python main.py --help
```

During the search, the terminal shows a progress bar with the percentage and
number of processed entries. Failed searches also count as processed. The
program then prints the HTML report path. For `discogsList.json`, the report is
named `discogsList.summary.html` and is placed next to the input file. Open it
locally in a browser; no web server is required. A new run replaces the previous
report.

BeatBee spaces Discogs requests at least 1.25 seconds apart and takes rate-limit
headers into account. On HTTP `429`, it waits according to `Retry-After`, or
60 seconds if that header is absent, before retrying. Server-requested waits
over five minutes are reported as errors; BeatBee does not send further
requests during the cooldown. The limit applies per program run, so parallel
programs can still collectively reach the rate limit.

## Understanding the HTML report

The report contains the list name, total and status counts, and all entries in
these groups:

- **OK:** Exactly one distinct Master ID was found.
- **NOT_FOUND:** No Master ID was found. BeatBee also searches for Discogs
  releases and displays up to three links for diagnosis. This search is not
  limited to the Discogs "Album" format. Release results do not count as Master
  matches and cannot be exported.
- **MULTIPLE:** More than one distinct Master ID was found. Up to three
  deterministically sorted candidates with links are shown as suggestions only;
  BeatBee does not choose one.
- **ERROR:** A required search failed or was incomplete, for example because of
  a network problem or a search limit.

The report ends with the `OK` Masters in their original order, including artist,
album, Master ID, and Discogs link. Artist and album values are labeled when
parsed from the Discogs search title or taken from the query. Missing details
are shown as unavailable. Results are classified by the number of distinct
Master IDs, without an additional semantic check of the title or year.

For `NOT_FOUND` or `MULTIPLE`, edit the search parameters in the JSON file and
run the validation again. For `ERROR`, check the connection or token and try
again. The report also includes a machine-readable JSON summary; when every
result is `OK`, it contains the ordered manifest as well.

## Manual Discogs list and export

Only when **all** entries are `OK` can you export an ordered checklist or JSON
manifest:

```powershell
python main.py export discogsList.json --format markdown --output beatbee-list.md
python main.py export discogsList.json --format json --output beatbee-list.json
```

The Markdown checklist contains Master links; the JSON contains the list name
and Master IDs in input order. Create the list yourself on Discogs and transfer
the entries in that order. The export **is not a publication**.

`python main.py run discogsList.json` also checks the list and reaches the
publishing boundary when all results are unambiguous. Since no verified
publisher is available, `run` currently reports "Publishing unavailable" and
exits with code `4`. Optionally, `--manifest FILE.json` writes a manifest.
No non-`OK` result may be published.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Validation or manual export succeeded. |
| `1` | At least one entry is `NOT_FOUND` or `MULTIPLE`. |
| `2` | The input is invalid or cannot be read. |
| `3` | At least one search is `ERROR`, or the HTML report could not be written. |
| `4` | Publishing failed or is unavailable. |

## Project files and Git

The repository should contain `main.py`, `pyproject.toml`, `src/beatbee/`,
`tests/`, `README.md`, `SPEC.md`, `docs/`, `.gitignore`, and the project
instructions in `.github/`. The default start without arguments also requires
`discogsList.json`; alternatively, create it after cloning or specify another
input file. The file is not ignored: check its contents before committing and
pushing it.

The token file `discogsToken.json`, `.venv/`, Python caches, build files, HTML
reports `*.summary.html`, and the export files shown above remain local through
`.gitignore`. You must configure your own token after a fresh clone. Other
export filenames are not automatically ignored and should be checked before
committing.

## Tests

The tests use mocked Discogs responses and do not require a token. Run them in
the project directory using PowerShell:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -p "test_*.py"
```

## Further documentation

- [Specification](SPEC.md)
- [Search strategy](docs/SEARCH_STRATEGY.md)
- [Publishing and feasibility](docs/PUBLISHING.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Decisions](docs/DECISIONS.md)
- [Open questions](docs/OPEN_QUESTIONS.md)
- [Roadmap](docs/ROADMAP.md)
