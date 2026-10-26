# ipfs_back 2.3.1

A Python agent and Kubo in one container: files from `Upload/` are pinned to
the public IPFS network and synchronized to `Synced_dir/` on nodes.

## Features

- Starts Kubo with `IPFS_PATH=/data/ipfs`.
- Watches `Upload/` for new files.
- Pins CIDs and stores file paths, CIDs, and addition dates in `data/ipfs.sqlite3`.
- Downloads peer files into `Synced_dir/`.

## SQLite storage

On first startup, existing `data/file_cid_mapping.json` and
`data/deleted_files.json` are imported into SQLite in a single transaction.
Both mapping formats are supported: CID strings and `{cid, date_added}` objects.
Deleted entries can be path strings or objects containing `path`, `cid`, and
`deleted_at`.

The original JSON files remain on disk but are no longer read or updated after
migration. If JSON input is invalid, startup stops: correct the file and retry.
Deleted paths are also stored in SQLite. Database access uses Python's standard
`sqlite3` module and requires no additional dependency.

To move the data, stop the agent and copy `data/ipfs.sqlite3` together with
`ipfs.sqlite3-wal` and `ipfs.sqlite3-shm` if those files are present.

## uv environment

Project settings and dependencies are defined in `pyproject.toml`; exact versions
are recorded in `uv.lock`. Install the environment and run the agent from the
project root:

```bash
uv sync --locked
uv run --locked src/ipfs_test_node_public.py
```

Python 3.12 or later and the Kubo CLI are required.
Docker uses a separate `DOCKER/V2/requirements.txt`; keep it in sync with
`pyproject.toml` when changing dependencies.

## Tests

Run from the project root:

```bash
uv run --locked python -m unittest discover -s tests -v
```

Tests use temporary SQLite databases and directories. Kubo calls are mocked,
so no running IPFS daemon or network access is required. Working data is unchanged.

## Run with Podman or Docker

Build from `DOCKER/V2`. Before building, copy all `src/*.py` files, including
`storage.py`, into `DOCKER/V2`.

```bash
cd DOCKER/V2
mkdir -p Upload Synced_dir data ipfs-repo
podman compose -f docker-compose.yml up -d --build
podman logs -f ipfs-back
```
