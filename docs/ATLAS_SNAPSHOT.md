# Read-only Atlas snapshot

Build-time scan: Atlas canonical revision **3482**, approved filters on
Candidate_Facts (34 returned, no further page) and Project_Registry (4 returned,
no further page), both at the same revision. Export selects **5 records**:
evaluation scope, verifier scope, safety/technical skills, dissertation scope,
and the scoped neutral Atlas architecture description. This is full coverage
of those two approved scans, not of all Atlas tables or all career evidence.

| Native field | Export mapping |
|---|---|
| record_id, record_version, approval_status, table | Preserved unchanged |
| source_ref, source_version, content_hash | Preserved (version serialized as string) |
| Candidate_Facts.payload.fact_key/value | Selected fact serialized into descriptive text |
| Candidate evidence_level/independently_verified | Retained in text and metadata |
| Project approved_cv_claims | Only the three approved neutral architecture claims |
| Project contribution_summary/project_maturity | Retained, including unknown personal authorship and proposed maturity |
| source_commit_sha | Preserved for selected project |
| revision/retrieval time | Stored in envelope and every record |

No contacts, email bodies, full CVs, credentials, recipient addresses or
unrelated application history are in the export. Source references can point
to private source documents; references do not copy those documents. Approval
of a record does not establish independent engineering ownership or deployment.

The source `content_hash` identifies the original native record and must not
be relabelled as an export-byte hash. `export_text_hash` and `chunk_text_hash`
are computed separately by ingestion. Chunk IDs bind record ID/version/text.
The provenance manifest records hashes for inspected helper source snapshots.

Download the separate private snapshot into your Codespace, then run:

```bash
uv run l1-lab import-snapshot /path/to/Atlas_L1_Knowledge_Snapshot_20261113.json
uv run l1-lab demo --mode offline --snapshot private/atlas_snapshot.json --query evaluation
```

The import validates the flattened schema and selected records, then copies
the file to ignored private storage. It never writes to Atlas. ChatGPT
connector sessions/tokens are not copied to Codespaces. No documented direct
read API was established, so file-based access is the supported adapter.

To refresh, perform a new authorized approved scan at one consistent revision,
preserve the source envelope, export only relevant allowed fields, and import
the replacement. Rebuild the local index from that complete selected snapshot;
revoked/superseded records must disappear. The sample loader resolves highest
record versions before checking approval. Synthetic fixtures include revoked
and superseded cases; do not combine their invented revision with the real one.

Current snapshot approval is a build-time observation. It does not prove later
approval state or continuously synchronized knowledge. Raw traces and derived
private vectors stay in ignored .lab/ or private/ and should be shared only by
an explicit later action.
