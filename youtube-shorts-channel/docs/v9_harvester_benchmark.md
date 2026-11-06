# Studio v9 Harvester Benchmark (M2 acceptance)

- **v8 shipped**: v8 `discover_footage_first_by_purpose` (verbose planner queries; note its Internet Archive
  query was silently broken — unescaped `*/by/*` — and is counted here AFTER the v9 escape fix, i.e. generous to v8).
- **v8 sources / v9 sources**: same v9 compact queries, restricted to NASA+Commons+IA vs all enabled v9 sources.

| Topic | v8 shipped usable (action) | v8 sources usable (action) | v9 sources usable (action) | v9 low-res leads | v9 non-camera visuals | v9 / v8 shipped |
|---|---:|---:|---:|---:|---:|---:|
| hydrothermal vent black smoker | 0 (0) | 16 (11) | 16 (11) | 7 | 4 | infx |
| aurora borealis solar wind | 0 (0) | 15 (1) | 24 (1) | 0 | 6 | infx |
| Apollo Saturn V rocket launch | 0 (0) | 25 (6) | 30 (6) | 0 | 3 | infx |

Per-source stats (v9):

```json
{
 "hydrothermal vent black smoker": {
  "nasa_images": {
   "returned": 1,
   "kept": 1,
   "rejected_license": 0
  },
  "wikimedia": {
   "returned": 10,
   "kept": 9,
   "rejected_license": 0
  },
  "internet_archive": {
   "returned": 7,
   "kept": 6,
   "rejected_license": 0
  },
  "nasa_svs": {
   "returned": 4,
   "kept": 4,
   "rejected_license": 0
  },
  "esa_webb": {
   "returned": 0,
   "kept": 0,
   "rejected_license": 0
  },
  "esa_hubble": {
   "returned": 0,
   "kept": 0,
   "rejected_license": 0
  },
  "noaa_onestop": {
   "returned": 11,
   "kept": 7,
   "rejected_license": 0
  }
 },
 "aurora borealis solar wind": {
  "nasa_images": {
   "returned": 4,
   "kept": 4,
   "rejected_license": 0
  },
  "wikimedia": {
   "returned": 9,
   "kept": 9,
   "rejected_license": 0
  },
  "internet_archive": {
   "returned": 2,
   "kept": 2,
   "rejected_license": 0
  },
  "nasa_svs": {
   "returned": 12,
   "kept": 10,
   "rejected_license": 0
  },
  "esa_webb": {
   "returned": 2,
   "kept": 2,
   "rejected_license": 0
  },
  "esa_hubble": {
   "returned": 3,
   "kept": 3,
   "rejected_license": 0
  },
  "noaa_onestop": {
   "returned": 0,
   "kept": 0,
   "rejected_license": 0
  }
 },
 "Apollo Saturn V rocket launch": {
  "nasa_images": {
   "returned": 16,
   "kept": 13,
   "rejected_license": 0
  },
  "wikimedia": {
   "returned": 10,
   "kept": 9,
   "rejected_license": 0
  },
  "internet_archive": {
   "returned": 3,
   "kept": 3,
   "rejected_license": 0
  },
  "nasa_svs": {
   "returned": 12,
   "kept": 8,
   "rejected_license": 0
  },
  "esa_webb": {
   "returned": 0,
   "kept": 0,
   "rejected_license": 0
  },
  "esa_hubble": {
   "returned": 0,
   "kept": 0,
   "rejected_license": 0
  },
  "noaa_onestop": {
   "returned": 0,
   "kept": 0,
   "rejected_license": 0
  }
 }
}
```

## Reading the numbers (honest summary)

- v8 as shipped returned **0 usable candidates** on all three topics: its long planner queries
  ("… aerial documentary footage") match nothing in archive search engines, and its Internet Archive
  query errored silently (unescaped `*/by/*`).
- Most of the v9 gain comes from **compact archive queries + the Internet Archive fix** (column "v8 sources").
- The **new sources** add on top of that with identical queries: +60% (aurora: NASA SVS, ESA/Webb/Hubble),
  +20% (Apollo: NASA SVS), +0 HD for hydrothermal vents (NOAA OneStop only exposes 640x360 leads; HD
  needs the NCEI order basket).
- "Usable" here uses the metadata class hint; `download-footage` re-classifies from pixels and can only
  downgrade (e.g. SVS/ESA items are animations or pans over stills, never counted as camera footage).
