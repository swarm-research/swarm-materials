#!/usr/bin/env python3
"""Read-only, deterministic audit parser for MASO swarm filesystem snapshots.

The parser never writes into an input snapshot.  It separates three classes of
execution evidence:

1. planned_only: static launcher defaults or command text;
2. log_footprint: a log/session/spawn record exists;
3. success_evidence: at least one logged HTTP 200 API request exists.

None of these, including success_evidence, proves that an agent completed its
intended task.  In particular, a command that names 900 agents is never counted
as 900 running or successful agents.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import csv
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import re
import shlex
import signal
import stat
import sys
import tarfile
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator, Sequence, Union


SCHEMA_VERSION = "swarm-snapshot-audit/v1.1"
TOOL_VERSION = "1.1.0"
AGENT_RE = re.compile(r"(?i)\bagent[-_ ]?(\d{1,6})\b")
BRACKET_AGENT_RE = re.compile(r"\[(agent[-_ ]?\d{1,6})\]", re.I)
ERROR_RE = re.compile(r"(?i)\b(error|exception|traceback|fatal|failed|failure)\b")
RATE_LIMIT_RE = re.compile(r"(?i)(?:\b429\b|rate[ -]?limit(?:ed|ing)?)")
HTTP_REQUEST_RE = re.compile(r'(?i)\bHTTP Request:\s*([A-Z]+)\s+.*?"HTTP/[^"\s]+\s+(\d{3})\b')
TOOL_RE = re.compile(r"(?i)\btool:([A-Za-z0-9_.-]+)")
INITIAL_RESPONSE_RE = re.compile(r"(?i)\bInitial response:\s*(.*)$")
TURN_RESPONSE_RE = re.compile(r"(?i)\bTurn\s+(\d+)\s*:\s*(.*)$")
START_RE = re.compile(r"(?i)\bStarting with provider(?:=|\s+)([^\s,]+)")
FINISHED_RE = re.compile(r"(?i)\bFinished after\s+(\d+)\s+turns?\b")
FAILURE_PREFIX_RE = re.compile(
    r"(?i)(api\s+(?:call\s+)?fail|max(?:imum)?\s+retr|rate[ -]?limit|"
    r"max\s+tool\s+rounds\s+reached|exception|traceback|fatal|\berror\b|unable to|timed?\s*out)"
)
SECRET_RES = [
    re.compile(r"(?i)(api[_-]?key|token|authorization|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"https://[^\s]+/hook/[A-Za-z0-9_-]+", re.I),
]
SOURCE_SUFFIXES = {".py", ".sh", ".bash"}
TEXT_SUFFIXES = {".log", ".out", ".txt", ".sh", ".bash", ".py"}
FILE_READ_TIMEOUT_SECONDS = 30.0
HASH_WORKERS = 8


@dataclass(frozen=True)
class Snapshot:
    host: str
    root: Path
    swarm: Path | None
    swarmctl: Path | None
    swarmctl_archive: Path | None

    def plane_roots(self) -> list[tuple[str, Path]]:
        result: list[tuple[str, Path]] = []
        if self.swarm is not None and self.swarm.exists():
            result.append(("swarm", self.swarm))
        if self.swarmctl is not None and self.swarmctl.exists():
            result.append(("swarmctl", self.swarmctl))
        return result


@dataclass(frozen=True)
class TarMemberRef:
    """A read-only reference to a regular member of a local tar archive."""

    tar_path: Path
    member_name: str


DataRef = Union[Path, TarMemberRef]


def utc_iso_from_ns(ns: int) -> str:
    return dt.datetime.fromtimestamp(ns / 1_000_000_000, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def generated_at() -> str:
    source_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_epoch:
        return dt.datetime.fromtimestamp(int(source_epoch), tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")
    return dt.datetime.now(tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@contextlib.contextmanager
def file_read_deadline(path: Path) -> Iterator[None]:
    """Prevent an offline/cloud-stub regular file from hanging the audit."""
    seconds = FILE_READ_TIMEOUT_SECONDS
    if (
        seconds <= 0
        or not hasattr(signal, "SIGALRM")
        or threading.current_thread() is not threading.main_thread()
    ):
        yield
        return

    def on_alarm(_signum: int, _frame: Any) -> None:
        raise TimeoutError(f"file read exceeded {seconds:g}s: {path}")

    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, on_alarm)
    old_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old_handler)
        if old_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, old_timer[0], old_timer[1])


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with file_read_deadline(path):
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
    return digest.hexdigest()


def sha256_stream(handle: Any, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = handle.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


@contextlib.contextmanager
def open_text_ref(ref: DataRef) -> Iterator[io.TextIOBase]:
    """Open a local file or tar member as text without extraction."""
    if isinstance(ref, Path):
        with ref.open("r", encoding="utf-8", errors="replace") as handle:
            yield handle
        return
    with tarfile.open(ref.tar_path, mode="r:*") as archive:
        try:
            member = archive.getmember(ref.member_name)
        except KeyError as exc:
            raise OSError(f"tar member disappeared: {ref.member_name}") from exc
        raw = archive.extractfile(member)
        if raw is None:
            raise OSError(f"tar member is not readable as a regular file: {ref.member_name}")
        with raw:
            with io.TextIOWrapper(raw, encoding="utf-8", errors="replace") as handle:
                yield handle


def read_text_ref(ref: DataRef) -> str:
    with open_text_ref(ref) as handle:
        return handle.read()


def normalize_agent(value: Any) -> tuple[str, int] | tuple[None, None]:
    if value is None:
        return None, None
    match = AGENT_RE.search(str(value))
    if not match:
        return None, None
    number = int(match.group(1))
    return f"agent-{number}", number


def redact(text: str, limit: int = 240) -> str:
    cleaned = text.replace("\x00", "�").strip()
    for pattern in SECRET_RES:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned[:limit]


def sanitize_host(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    if not cleaned:
        raise ValueError("host label is empty after sanitization")
    return cleaned


def path_is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def looks_like_workspace(path: Path) -> bool:
    signals = ("commons", "agents", "vitals", "board", "devbox_runner.py", "swarm_sessions.json")
    return path.is_dir() and any((path / name).exists() for name in signals)


def snapshot_from_root(host: str, root: Path) -> Snapshot:
    root = root.expanduser().resolve()
    # Claude's serial pull keeps the incoming workspace tar in the machine
    # directory while extraction is in progress.  Refuse the whole machine in
    # that state: even already-visible extracted files may still be changing.
    in_progress_markers = sorted(
        path.name
        for path in root.iterdir()
        if path.is_file()
        and (
            path.name in {"swarm.tgz", "swarm.tar.gz", "swarm.tar"}
            or path.suffix.lower() in {".partial", ".part", ".tmp"}
        )
    ) if root.is_dir() else []
    if in_progress_markers:
        raise ValueError(
            f"snapshot appears in progress; refusing to read {root}: "
            f"markers={in_progress_markers}"
        )
    safe_host = sanitize_host(host)
    companion_candidates = [
        root / "swarmctl.tgz",
        root / "swarmctl.tar.gz",
        root.parent / f"{safe_host}_ctl.tgz",
        root.parent / f"{safe_host}_ctl.tar.gz",
    ]
    companion = next((path.resolve() for path in companion_candidates if path.is_file()), None)
    if (root / "swarm").is_dir() or (root / "swarmctl").is_dir():
        return Snapshot(
            host=safe_host,
            root=root,
            swarm=(root / "swarm") if (root / "swarm").is_dir() else None,
            swarmctl=(root / "swarmctl") if (root / "swarmctl").is_dir() else None,
            swarmctl_archive=companion,
        )
    if looks_like_workspace(root):
        return Snapshot(host=safe_host, root=root, swarm=root, swarmctl=None, swarmctl_archive=companion)
    raise ValueError(f"not a recognized snapshot root: {root}")


def discover_inputs(input_roots: Sequence[str], workspace_specs: Sequence[str]) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    for spec in workspace_specs:
        if "=" not in spec:
            raise ValueError(f"--workspace must be HOST=PATH, got: {spec!r}")
        host, raw_path = spec.split("=", 1)
        snapshots.append(snapshot_from_root(host, Path(raw_path)))

    for raw in input_roots:
        root = Path(raw).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"input directory does not exist: {root}")
        if (root / "swarm").is_dir() or (root / "swarmctl").is_dir() or looks_like_workspace(root):
            snapshots.append(snapshot_from_root(root.name, root))
            continue
        children = [
            child
            for child in sorted(root.iterdir(), key=lambda p: p.name)
            if child.is_dir()
            and not child.name.startswith(".")
            and ((child / "swarm").is_dir() or (child / "swarmctl").is_dir())
        ]
        if not children:
            raise ValueError(f"no workspace-id/{{swarm,swarmctl}} children found under: {root}")
        snapshots.extend(snapshot_from_root(child.name, child) for child in children)

    if not snapshots:
        raise ValueError("provide at least one --input or --workspace")

    by_host: dict[str, Snapshot] = {}
    for snap in snapshots:
        if snap.host in by_host and by_host[snap.host].root != snap.root:
            raise ValueError(f"duplicate host label {snap.host!r} for different roots")
        by_host[snap.host] = snap
    return [by_host[key] for key in sorted(by_host)]


def walk_entries(root: Path, error_rows: list[dict[str, Any]], host: str, plane: str) -> Iterator[Path]:
    def onerror(exc: OSError) -> None:
        error_rows.append(
            {
                "source_host": host,
                "source_path": str(getattr(exc, "filename", root)),
                "line": "",
                "category": "walk_error",
                "detail": redact(str(exc)),
            }
        )

    for current, dirs, files in os.walk(root, topdown=True, onerror=onerror, followlinks=False):
        dirs.sort()
        files.sort()
        current_path = Path(current)
        for filename in files:
            yield current_path / filename


def safe_tar_member_relative(name: str) -> str | None:
    """Return a normalized control-plane relative name without traversal."""
    normalized = name.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts:
        return None
    parts = [part for part in pure.parts if part not in {"", "."}]
    if "swarmctl" in parts:
        parts = parts[parts.index("swarmctl") + 1 :]
    if not parts:
        return None
    return PurePosixPath(*parts).as_posix()


def add_control_tar_manifest(
    snapshot: Snapshot,
    rows: list[dict[str, Any]],
    lookup: dict[tuple[str, str], DataRef],
    error_rows: list[dict[str, Any]],
) -> None:
    archive_path = snapshot.swarmctl_archive
    if archive_path is None:
        return
    before = archive_path.stat()
    container_rel = f"__archives__/{archive_path.name}"
    rows.append(
        {
            "source_host": snapshot.host,
            "plane": "archive_container",
            "path": container_rel,
            "kind": "regular",
            "size_bytes": before.st_size,
            "mtime_ns": before.st_mtime_ns,
            "mtime_utc": utc_iso_from_ns(before.st_mtime_ns),
            "sha256": sha256_file(archive_path),
            "hash_status": "ok",
            "symlink_target": "",
            "container_path": str(archive_path),
            "member_name": "",
        }
    )
    lookup[(snapshot.host, container_rel)] = archive_path
    seen_paths: set[str] = set()
    try:
        # Iteration plus extraction hashes every regular member and forces gzip
        # CRC/end-of-stream validation. Nothing is extracted to disk.
        with tarfile.open(archive_path, mode="r:*") as archive:
            for member_index, member in enumerate(archive):
                rel = safe_tar_member_relative(member.name)
                if rel is None:
                    if member.isfile() or member.issym() or member.islnk():
                        error_rows.append(
                            {
                                "source_host": snapshot.host,
                                "source_path": container_rel,
                                "line": member_index,
                                "category": "tar_member_unsafe_or_empty_path",
                                "detail": redact(member.name),
                            }
                        )
                    continue
                output_path = f"swarmctl/{rel}"
                if output_path in seen_paths:
                    error_rows.append(
                        {
                            "source_host": snapshot.host,
                            "source_path": output_path,
                            "line": member_index,
                            "category": "tar_member_duplicate_path",
                            "detail": "later duplicate retained in manifest but first lookup reference is used",
                        }
                    )
                seen_paths.add(output_path)
                mtime_ns = int(member.mtime * 1_000_000_000)
                if member.isfile():
                    raw = archive.extractfile(member)
                    if raw is None:
                        raise tarfile.ReadError(f"cannot read regular member {member.name}")
                    with raw:
                        digest = sha256_stream(raw)
                    kind = "tar_regular"
                    target = ""
                    lookup.setdefault((snapshot.host, output_path), TarMemberRef(archive_path, member.name))
                elif member.issym() or member.islnk():
                    kind = "tar_symlink" if member.issym() else "tar_hardlink"
                    target = member.linkname
                    digest = sha256_bytes((kind.upper() + "\0" + target).encode("utf-8", errors="surrogateescape"))
                else:
                    continue
                rows.append(
                    {
                        "source_host": snapshot.host,
                        "plane": "swarmctl",
                        "path": output_path,
                        "kind": kind,
                        "size_bytes": member.size,
                        "mtime_ns": mtime_ns,
                        "mtime_utc": utc_iso_from_ns(mtime_ns),
                        "sha256": digest,
                        "hash_status": "ok",
                        "symlink_target": target,
                        "container_path": str(archive_path),
                        "member_name": member.name,
                    }
                )
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ValueError(f"control archive is incomplete or unreadable; refusing snapshot {snapshot.host}: {exc}") from exc
    after = archive_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError(
            f"control archive changed while being read; refusing snapshot {snapshot.host}: {archive_path}"
        )


def build_manifest(snapshots: Sequence[Snapshot], error_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[tuple[str, str], DataRef]]:
    rows: list[dict[str, Any]] = []
    absolute_lookup: dict[tuple[str, str], DataRef] = {}
    hash_tasks: list[tuple[dict[str, Any], Path]] = []
    for snap in snapshots:
        for plane, plane_root in snap.plane_roots():
            for path in walk_entries(plane_root, error_rows, snap.host, plane):
                rel = Path(plane) / path.relative_to(plane_root)
                rel_posix = rel.as_posix()
                try:
                    info = path.lstat()
                    kind = "regular"
                    target = ""
                    if stat.S_ISLNK(info.st_mode):
                        kind = "symlink"
                        target = os.readlink(path)
                        digest = sha256_bytes(("SYMLINK\0" + target).encode("utf-8", errors="surrogateescape"))
                        hash_status = "ok"
                    elif stat.S_ISREG(info.st_mode):
                        digest = ""
                        hash_status = "pending"
                    else:
                        kind = "special"
                        digest = ""
                        hash_status = "not_applicable"
                    row = {
                        "source_host": snap.host,
                        "plane": plane,
                        "path": rel_posix,
                        "kind": kind,
                        "size_bytes": info.st_size,
                        "mtime_ns": info.st_mtime_ns,
                        "mtime_utc": utc_iso_from_ns(info.st_mtime_ns),
                        "sha256": digest,
                        "hash_status": hash_status,
                        "symlink_target": target,
                        "container_path": "",
                        "member_name": "",
                    }
                    rows.append(row)
                    absolute_lookup[(snap.host, rel_posix)] = path
                    if hash_status == "pending":
                        hash_tasks.append((row, path))
                except (OSError, ValueError) as exc:
                    error_rows.append(
                        {
                            "source_host": snap.host,
                            "source_path": rel_posix,
                            "line": "",
                            "category": "manifest_error",
                            "detail": redact(str(exc)),
                        }
                    )
        add_control_tar_manifest(snap, rows, absolute_lookup, error_rows)

    def hash_one(item: tuple[dict[str, Any], Path]) -> tuple[dict[str, Any], Path, str, str | None]:
        row, path = item
        try:
            digest = sha256_file(path)
            after = path.lstat()
            if (after.st_size, after.st_mtime_ns) != (row["size_bytes"], row["mtime_ns"]):
                return row, path, "", "file changed while being hashed"
            return row, path, digest, None
        except OSError as exc:
            return row, path, "", str(exc)

    # Local hashing is parallel because the snapshots contain thousands of
    # small files and filesystem-open latency dominates. This does not affect
    # the Merlin/SSH serial-access rule: all inputs here are already-local and
    # read-only. Results are sorted deterministically afterwards.
    if HASH_WORKERS == 1:
        hash_results = map(hash_one, hash_tasks)
        executor_context = contextlib.nullcontext()
    else:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=HASH_WORKERS)
        executor_context = executor
        hash_results = executor.map(hash_one, hash_tasks)
    with executor_context:
        for row, path, digest, error in hash_results:
            if error is None:
                row["sha256"] = digest
                row["hash_status"] = "ok"
            else:
                row["hash_status"] = "error"
                absolute_lookup.pop((row["source_host"], row["path"]), None)
                error_rows.append(
                    {
                        "source_host": row["source_host"],
                        "source_path": row["path"],
                        "line": "",
                        "category": "manifest_hash_error",
                        "detail": redact(error),
                    }
                )
    for snap in snapshots:
        late_markers = sorted(
            path.name
            for path in snap.root.iterdir()
            if path.is_file()
            and (
                path.name in {"swarm.tgz", "swarm.tar.gz", "swarm.tar"}
                or path.suffix.lower() in {".partial", ".part", ".tmp"}
            )
        )
        if late_markers:
            raise ValueError(
                f"snapshot became active during manifesting; refusing {snap.root}: markers={late_markers}"
            )
    rows.sort(key=lambda r: (r["source_host"], r["path"]))
    return rows, absolute_lookup


def classify_component(basename: str) -> str | None:
    lower = basename.lower()
    suffix = Path(lower).suffix
    if suffix not in SOURCE_SUFFIXES:
        return None
    if "runner" in lower:
        return "runner"
    if "launch" in lower:
        return "launcher"
    if "reaper" in lower:
        return "reaper"
    return None


def is_regular_content(row: dict[str, Any]) -> bool:
    return row.get("kind") in {"regular", "tar_regular"} and row.get("hash_status", "ok") == "ok"


def is_deployed_source_candidate(row: dict[str, Any]) -> bool:
    """Exclude agent-authored lookalikes from deployed-control source hashes."""
    pure = PurePosixPath(row["path"])
    basename = pure.name.lower()
    if row.get("plane") == "swarmctl":
        return classify_component(basename) is not None
    # In the data plane, only top-level deployed programs count. Files under
    # commons/ or agents/ can deliberately contain runner/reaper lookalikes.
    if row.get("plane") != "swarm" or len(pure.parts) != 2:
        return False
    return bool(
        basename == "devbox_runner.py"
        or basename.startswith("devbox_launch")
        or basename in {"devbox_reaper.py", "swarm_reaper.py"}
    )


def source_hash_rows(manifest: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in manifest:
        if not is_regular_content(row) or not is_deployed_source_candidate(row):
            continue
        component = classify_component(PurePosixPath(row["path"]).name)
        if component:
            rows.append(
                {
                    "source_host": row["source_host"],
                    "component": component,
                    "basename": PurePosixPath(row["path"]).name,
                    "path": row["path"],
                    "sha256": row["sha256"],
                    "size_bytes": row["size_bytes"],
                    "mtime_utc": row["mtime_utc"],
                }
            )
    return sorted(rows, key=lambda r: (r["source_host"], r["component"], r["path"]))


def ast_argparse_defaults(text: str) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        options = [arg.value for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
        if not options:
            continue
        default_value: Any = None
        required = False
        for keyword in node.keywords:
            if keyword.arg == "default" and isinstance(keyword.value, ast.Constant):
                default_value = keyword.value.value
            elif keyword.arg == "required" and isinstance(keyword.value, ast.Constant):
                required = bool(keyword.value.value)
        for option in options:
            if option.startswith("--"):
                defaults[option] = default_value
                if required:
                    defaults[f"{option}__required"] = True
    return defaults


def flag_value(tokens: Sequence[str], flag: str) -> int | None:
    try:
        index = tokens.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(tokens):
        return None
    try:
        return int(tokens[index + 1])
    except ValueError:
        return None


def command_plan_from_line(line: str) -> dict[str, int] | None:
    if "launch" not in line.lower() or ".py" not in line.lower():
        return None
    try:
        tokens = shlex.split(line, comments=False, posix=True)
    except ValueError:
        tokens = line.strip().split()
    values: dict[str, int] = {}
    for flag, key in (
        ("--start", "start"),
        ("--end", "end"),
        ("--batch-index", "batch_index"),
        ("--batch-count", "batch_count"),
        ("--max-concurrent", "max_concurrent"),
    ):
        value = flag_value(tokens, flag)
        if value is not None:
            values[key] = value
    return values if values else None


def assigned_agent_numbers(start: int, end: int, batch_index: int, batch_count: int) -> list[int]:
    if end < start or batch_count <= 0 or not 0 <= batch_index < batch_count:
        return []
    return [number for offset, number in enumerate(range(start, end)) if offset % batch_count == batch_index]


def scan_plan_observations(
    source_rows: Sequence[dict[str, Any]],
    manifest: Sequence[dict[str, Any]],
    lookup: dict[tuple[str, str], DataRef],
    error_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, set[int]], dict[str, Counter[int]]]:
    observations: list[dict[str, Any]] = []
    planned_agents: dict[str, set[int]] = defaultdict(set)
    spawned_agents: dict[str, Counter[int]] = defaultdict(Counter)
    defaults_by_host: dict[str, dict[str, Any]] = defaultdict(dict)

    for row in source_rows:
        if row["component"] != "launcher":
            continue
        path = lookup.get((row["source_host"], row["path"]))
        if path is None:
            continue
        try:
            text = read_text_ref(path)
            defaults = ast_argparse_defaults(text)
        except (OSError, SyntaxError) as exc:
            error_rows.append(
                {
                    "source_host": row["source_host"],
                    "source_path": row["path"],
                    "line": "",
                    "category": "launcher_ast_error",
                    "detail": redact(str(exc)),
                }
            )
            continue
        defaults_by_host[row["source_host"]].update(defaults)
        start = defaults.get("--start")
        end = defaults.get("--end")
        count = end - start if isinstance(start, int) and isinstance(end, int) and end >= start else ""
        observations.append(
            {
                "source_host": row["source_host"],
                "source_path": row["path"],
                "line": "",
                "observation_type": "static_source_defaults",
                "proof_level": "planned_only",
                "start": start if start is not None else "",
                "end_exclusive": end if end is not None else "",
                "batch_index": defaults.get("--batch-index") if defaults.get("--batch-index") is not None else "",
                "batch_count": defaults.get("--batch-count") if defaults.get("--batch-count") is not None else "",
                "max_concurrent": defaults.get("--max-concurrent") if defaults.get("--max-concurrent") is not None else "",
                "declared_or_derived_count": count,
                "agent_number": "",
                "detail": "Static source defaults are a plan, not execution evidence.",
            }
        )

    scan_candidates: list[dict[str, Any]] = []
    for row in manifest:
        if not is_regular_content(row) or PurePosixPath(row["path"]).suffix.lower() not in TEXT_SUFFIXES:
            continue
        lower = row["path"].lower()
        if row["plane"] == "swarmctl" or "launch" in lower or "/vitals/" in f"/{lower}":
            scan_candidates.append(row)

    spawn_pattern_1 = re.compile(r"\[\d+/\d+\]\s+(agent[-_ ]?\d{1,6})\s+PID=", re.I)
    spawn_pattern_2 = re.compile(r"\bLaunched\s+(agent[-_ ]?\d{1,6})\b", re.I)
    aggregate_pattern = re.compile(r"(?i)\b(?:All\s+)?(\d+)\s+agents?\s+launched\b")
    seen_command_hashes: set[tuple[str, str]] = set()
    for row in scan_candidates:
        path = lookup.get((row["source_host"], row["path"]))
        if path is None:
            continue
        try:
            with open_text_ref(path) as handle:
                for line_number, line in enumerate(handle, 1):
                    plan = command_plan_from_line(line)
                    if plan:
                        merged = {
                            "start": defaults_by_host[row["source_host"]].get("--start"),
                            "end": defaults_by_host[row["source_host"]].get("--end"),
                            "batch_index": defaults_by_host[row["source_host"]].get("--batch-index"),
                            "batch_count": defaults_by_host[row["source_host"]].get("--batch-count"),
                            "max_concurrent": defaults_by_host[row["source_host"]].get("--max-concurrent"),
                        }
                        merged.update(plan)
                        fingerprint = sha256_bytes(canonical_json(merged).encode())
                        dedup_key = (row["source_host"], fingerprint)
                        if dedup_key not in seen_command_hashes:
                            seen_command_hashes.add(dedup_key)
                            start = merged.get("start")
                            end = merged.get("end")
                            batch_index = merged.get("batch_index")
                            batch_count = merged.get("batch_count")
                            assigned: list[int] = []
                            if all(isinstance(x, int) for x in (start, end, batch_index, batch_count)):
                                assigned = assigned_agent_numbers(start, end, batch_index, batch_count)
                                planned_agents[row["source_host"]].update(assigned)
                            observations.append(
                                {
                                    "source_host": row["source_host"],
                                    "source_path": row["path"],
                                    "line": line_number,
                                    "observation_type": "command_text",
                                    "proof_level": "planned_only",
                                    "start": start if start is not None else "",
                                    "end_exclusive": end if end is not None else "",
                                    "batch_index": batch_index if batch_index is not None else "",
                                    "batch_count": batch_count if batch_count is not None else "",
                                    "max_concurrent": merged.get("max_concurrent") if merged.get("max_concurrent") is not None else "",
                                    "declared_or_derived_count": len(assigned) if assigned else "",
                                    "agent_number": "",
                                    "detail": "Command text is a plan/request; it does not prove launch, run, or success.",
                                }
                            )
                    spawn_match = spawn_pattern_1.search(line) or spawn_pattern_2.search(line)
                    if spawn_match:
                        _, number = normalize_agent(spawn_match.group(1))
                        if number is not None:
                            spawned_agents[row["source_host"]][number] += 1
                            observations.append(
                                {
                                    "source_host": row["source_host"],
                                    "source_path": row["path"],
                                    "line": line_number,
                                    "observation_type": "launcher_spawn_line",
                                    "proof_level": "process_spawn_footprint",
                                    "start": "",
                                    "end_exclusive": "",
                                    "batch_index": "",
                                    "batch_count": "",
                                    "max_concurrent": "",
                                    "declared_or_derived_count": 1,
                                    "agent_number": number,
                                    "detail": "Launcher-reported process spawn; not model-response or completion evidence.",
                                }
                            )
                    aggregate = aggregate_pattern.search(line)
                    if aggregate:
                        observations.append(
                            {
                                "source_host": row["source_host"],
                                "source_path": row["path"],
                                "line": line_number,
                                "observation_type": "aggregate_launcher_claim",
                                "proof_level": "process_spawn_claim_only",
                                "start": "",
                                "end_exclusive": "",
                                "batch_index": "",
                                "batch_count": "",
                                "max_concurrent": "",
                                "declared_or_derived_count": int(aggregate.group(1)),
                                "agent_number": "",
                                "detail": "Aggregate launcher text; not independently verified agent execution.",
                            }
                        )
        except OSError as exc:
            error_rows.append(
                {
                    "source_host": row["source_host"],
                    "source_path": row["path"],
                    "line": "",
                    "category": "plan_scan_error",
                    "detail": redact(str(exc)),
                }
            )
    observations.sort(key=lambda r: (r["source_host"], r["source_path"], str(r["line"]), r["observation_type"]))
    return observations, planned_agents, spawned_agents


def is_agent_log(row: dict[str, Any]) -> bool:
    if not is_regular_content(row):
        return False
    pure = PurePosixPath(row["path"])
    if pure.suffix.lower() not in {".log", ".out", ".txt"}:
        return False
    if not AGENT_RE.search(pure.name):
        return False
    parts = {part.lower() for part in pure.parts}
    return bool(parts.intersection({"vitals", "logs", "log"}))


def scan_agent_logs(
    manifest: Sequence[dict[str, Any]],
    lookup: dict[tuple[str, str], DataRef],
    error_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for manifest_row in manifest:
        if not is_agent_log(manifest_row):
            continue
        path = lookup.get((manifest_row["source_host"], manifest_row["path"]))
        if path is None:
            continue
        filename_id, filename_number = normalize_agent(PurePosixPath(manifest_row["path"]).name)
        identity_counts: Counter[int] = Counter()
        line_count = 0
        nonempty_count = 0
        error_count = 0
        rate_limit_count = 0
        api_http_request_count = 0
        api_http_200_count = 0
        api_http_statuses: Counter[str] = Counter()
        tool_count = 0
        tool_names: Counter[str] = Counter()
        response_prefix_count = 0
        response_prefix_success_count = 0
        response_prefix_failure_count = 0
        start_count = 0
        finished_count = 0
        max_finished_turn = None
        providers: Counter[str] = Counter()
        response_examples: list[dict[str, Any]] = []
        error_line_numbers: list[int] = []
        rate_limit_line_numbers: list[int] = []
        try:
            with open_text_ref(path) as handle:
                for line_number, line in enumerate(handle, 1):
                    line_count += 1
                    stripped = line.rstrip("\r\n")
                    if stripped.strip():
                        nonempty_count += 1
                    for raw_identity in BRACKET_AGENT_RE.findall(line):
                        _, number = normalize_agent(raw_identity)
                        if number is not None:
                            identity_counts[number] += 1
                    if ERROR_RE.search(line):
                        error_count += 1
                        if len(error_line_numbers) < 20:
                            error_line_numbers.append(line_number)
                    if RATE_LIMIT_RE.search(line):
                        rate_limit_count += 1
                        if len(rate_limit_line_numbers) < 20:
                            rate_limit_line_numbers.append(line_number)
                    http_match = HTTP_REQUEST_RE.search(line)
                    if http_match:
                        api_http_request_count += 1
                        status = http_match.group(2)
                        api_http_statuses[status] += 1
                        if status == "200":
                            api_http_200_count += 1
                    for tool_name in TOOL_RE.findall(line):
                        tool_count += 1
                        tool_names[tool_name] += 1
                    start_match = START_RE.search(line)
                    if start_match:
                        start_count += 1
                        providers[start_match.group(1)] += 1
                    finished_match = FINISHED_RE.search(line)
                    if finished_match:
                        finished_count += 1
                        turn = int(finished_match.group(1))
                        max_finished_turn = turn if max_finished_turn is None else max(max_finished_turn, turn)
                    response_match = INITIAL_RESPONSE_RE.search(line)
                    response_kind = "initial"
                    response_turn: int | None = None
                    if response_match is None:
                        turn_match = TURN_RESPONSE_RE.search(line)
                        if turn_match:
                            response_match = turn_match
                            response_kind = "turn"
                            response_turn = int(turn_match.group(1))
                    if response_match is not None:
                        visible = response_match.group(response_match.lastindex or 1)
                        # Empty prefixes and the runner's local fallback are not
                        # model-success evidence.  The v1 parser incorrectly
                        # treated `(max tool rounds reached)` as a successful
                        # model response, inflating the activity layer from 97
                        # HTTP-success identities to 123 runner-loop identities.
                        is_failure = not visible.strip() or bool(FAILURE_PREFIX_RE.search(visible))
                        response_prefix_count += 1
                        if is_failure:
                            response_prefix_failure_count += 1
                        else:
                            response_prefix_success_count += 1
                        if len(response_examples) < 12:
                            response_examples.append(
                                {
                                    "line": line_number,
                                    "kind": response_kind,
                                    "turn": response_turn,
                                    "classified_failure": is_failure,
                                    "prefix": redact(visible),
                                    "prefix_sha256": sha256_bytes(visible.encode("utf-8", errors="replace")),
                                }
                            )
        except OSError as exc:
            error_rows.append(
                {
                    "source_host": manifest_row["source_host"],
                    "source_path": manifest_row["path"],
                    "line": "",
                    "category": "agent_log_read_error",
                    "detail": redact(str(exc)),
                }
            )
            continue

        primary_number = filename_number
        identity_source = "filename" if filename_number is not None else ""
        if primary_number is None and identity_counts:
            primary_number = identity_counts.most_common(1)[0][0]
            identity_source = "log_bracket_majority"
        mentioned_numbers = sorted(identity_counts)
        identity_conflict = bool(primary_number is not None and any(n != primary_number for n in mentioned_numbers))
        # A logged HTTP 200 is the strictest provider-success signal preserved
        # by these runner logs.  Response text can be a local runner fallback,
        # and tool events are downstream of a successful response but are not
        # guaranteed for every valid model call (agent-067 is the observed null).
        success_evidence = api_http_200_count > 0
        rows.append(
            {
                "source_host": manifest_row["source_host"],
                "path": manifest_row["path"],
                "size_bytes": manifest_row["size_bytes"],
                "sha256": manifest_row["sha256"],
                "agent_id": f"agent-{primary_number}" if primary_number is not None else filename_id or "",
                "agent_number": primary_number if primary_number is not None else "",
                "identity_source": identity_source,
                "identity_mentions_json": canonical_json({f"agent-{n}": identity_counts[n] for n in mentioned_numbers}),
                "identity_conflict": identity_conflict,
                "line_count": line_count,
                "nonempty_line_count": nonempty_count,
                "start_marker_count": start_count,
                "providers_json": canonical_json(dict(sorted(providers.items()))),
                "error_line_count": error_count,
                "error_line_numbers_json": canonical_json(error_line_numbers),
                "rate_limit_429_line_count": rate_limit_count,
                "rate_limit_line_numbers_json": canonical_json(rate_limit_line_numbers),
                "api_http_request_line_count": api_http_request_count,
                "api_http_200_request_line_count": api_http_200_count,
                "api_http_status_counts_json": canonical_json(dict(sorted(api_http_statuses.items()))),
                "api_http_200_interpretation": (
                    "Count of logged HTTP 200 API requests; not model turns, responses, tokens, or task completions."
                ),
                "tool_event_count": tool_count,
                "tool_names_json": canonical_json(dict(sorted(tool_names.items()))),
                "response_prefix_count": response_prefix_count,
                "response_prefix_success_count": response_prefix_success_count,
                "response_prefix_failure_count": response_prefix_failure_count,
                "response_prefix_examples_json": canonical_json(response_examples),
                "finished_marker_count": finished_count,
                "max_finished_turn": max_finished_turn if max_finished_turn is not None else "",
                "success_evidence": success_evidence,
                "success_evidence_basis": "logged_http_200_api_request" if success_evidence else "",
            }
        )
    return sorted(rows, key=lambda r: (r["source_host"], str(r["agent_number"]), r["path"]))


def value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def iter_session_files(manifest: Sequence[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for row in manifest:
        if is_regular_content(row) and PurePosixPath(row["path"]).name.lower() == "devbox_sessions.json":
            yield row


def parse_sessions(
    manifest: Sequence[dict[str, Any]],
    lookup: dict[tuple[str, str], DataRef],
    error_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Counter[int]]]:
    records_out: list[dict[str, Any]] = []
    schemas: list[dict[str, Any]] = []
    agents: dict[str, Counter[int]] = defaultdict(Counter)
    common_fields = {"id", "agent_id", "provider", "model", "pid", "started_at", "start", "launched_at", "host", "session_id"}
    for file_row in iter_session_files(manifest):
        path = lookup.get((file_row["source_host"], file_row["path"]))
        if path is None:
            continue
        try:
            value = json.loads(read_text_ref(path))
            if isinstance(value, list):
                records = value
                top_type = "list"
            elif isinstance(value, dict):
                if isinstance(value.get("sessions"), list):
                    records = value["sessions"]
                    top_type = "dict.sessions"
                else:
                    records = [value]
                    top_type = "dict.single"
            else:
                raise ValueError(f"expected list/dict, found {type(value).__name__}")
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            error_rows.append(
                {
                    "source_host": file_row["source_host"],
                    "source_path": file_row["path"],
                    "line": "",
                    "category": "devbox_sessions_parse_error",
                    "detail": redact(str(exc)),
                }
            )
            schemas.append(
                {
                    "source_host": file_row["source_host"],
                    "path": file_row["path"],
                    "parse_status": "error",
                    "top_level_type": "",
                    "record_count": "",
                    "dict_record_count": "",
                    "non_dict_record_count": "",
                    "key_presence_json": "{}",
                    "key_types_json": "{}",
                    "schema_variants_json": "{}",
                }
            )
            continue

        key_presence: Counter[str] = Counter()
        key_types: dict[str, Counter[str]] = defaultdict(Counter)
        schema_variants: Counter[str] = Counter()
        dict_count = 0
        non_dict_count = 0
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                non_dict_count += 1
                error_rows.append(
                    {
                        "source_host": file_row["source_host"],
                        "source_path": file_row["path"],
                        "line": index,
                        "category": "devbox_sessions_non_dict_record",
                        "detail": f"record type={type(record).__name__}",
                    }
                )
                continue
            dict_count += 1
            keys = sorted(str(key) for key in record)
            schema_variants[",".join(keys)] += 1
            for key, item in record.items():
                key_presence[str(key)] += 1
                key_types[str(key)][value_type(item)] += 1
            raw_id = record.get("id", record.get("agent_id"))
            agent_id, agent_number = normalize_agent(raw_id)
            if agent_number is not None:
                agents[file_row["source_host"]][agent_number] += 1
            canonical_record = canonical_json(record)
            extra = {str(k): v for k, v in record.items() if str(k) not in common_fields}
            records_out.append(
                {
                    "source_host": file_row["source_host"],
                    "source_path": file_row["path"],
                    "record_index": index,
                    "agent_id": agent_id or "",
                    "agent_number": agent_number if agent_number is not None else "",
                    "raw_id": str(raw_id) if raw_id is not None else "",
                    "provider": record.get("provider", ""),
                    "model": record.get("model", ""),
                    "pid": record.get("pid", ""),
                    "started_at": record.get("started_at", record.get("start", record.get("launched_at", ""))),
                    "host_field": record.get("host", ""),
                    "session_id": record.get("session_id", ""),
                    "record_keys_json": canonical_json(keys),
                    "extra_json": canonical_json(extra),
                    "canonical_record_sha256": sha256_bytes(canonical_record.encode("utf-8")),
                }
            )
        schemas.append(
            {
                "source_host": file_row["source_host"],
                "path": file_row["path"],
                "parse_status": "ok",
                "top_level_type": top_type,
                "record_count": len(records),
                "dict_record_count": dict_count,
                "non_dict_record_count": non_dict_count,
                "key_presence_json": canonical_json(dict(sorted(key_presence.items()))),
                "key_types_json": canonical_json({key: dict(sorted(counts.items())) for key, counts in sorted(key_types.items())}),
                "schema_variants_json": canonical_json(dict(sorted(schema_variants.items()))),
            }
        )
    records_out.sort(key=lambda r: (r["source_host"], r["source_path"], r["record_index"]))
    schemas.sort(key=lambda r: (r["source_host"], r["path"]))
    return records_out, schemas, agents


def baseline_commons_root(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser().resolve()
    candidates = [path / "commons", path / "swarm" / "commons"]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    if path.name == "commons" and path.is_dir():
        return path
    raise ValueError(f"baseline has no commons directory: {path}")


def hash_baseline_commons(root: Path | None, error_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if root is None:
        return {}
    rows: dict[str, dict[str, Any]] = {}
    tasks: list[tuple[str, Path, int]] = []
    for path in walk_entries(root, error_rows, "__baseline__", "commons"):
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode):
                continue
            rel = path.relative_to(root).as_posix()
            tasks.append((rel, path, info.st_size))
        except OSError as exc:
            error_rows.append(
                {
                    "source_host": "__baseline__",
                    "source_path": str(path),
                    "line": "",
                    "category": "baseline_manifest_error",
                    "detail": redact(str(exc)),
                }
            )

    def hash_one(item: tuple[str, Path, int]) -> tuple[str, str, int, str | None]:
        rel, path, size = item
        try:
            return rel, sha256_file(path), size, None
        except OSError as exc:
            return rel, "", size, str(exc)

    if HASH_WORKERS == 1:
        hash_results = map(hash_one, tasks)
        executor_context = contextlib.nullcontext()
    else:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=HASH_WORKERS)
        executor_context = executor
        hash_results = executor.map(hash_one, tasks)
    with executor_context:
        for rel, digest, size, error in hash_results:
            if error is None:
                rows[rel] = {"sha256": digest, "size_bytes": size}
            else:
                error_rows.append(
                    {
                        "source_host": "__baseline__",
                        "source_path": rel,
                        "line": "",
                        "category": "baseline_hash_error",
                        "detail": redact(error),
                    }
                )
    return rows


def commons_rows(
    snapshots: Sequence[Snapshot],
    manifest: Sequence[dict[str, Any]],
    baseline: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    host_names = [snapshot.host for snapshot in snapshots]
    entries: list[dict[str, Any]] = []
    by_path: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prefix = PurePosixPath("swarm/commons")
    for row in manifest:
        pure = PurePosixPath(row["path"])
        try:
            rel = pure.relative_to(prefix).as_posix()
        except ValueError:
            continue
        if not is_regular_content(row):
            continue
        item = {
            "source_host": row["source_host"],
            "artifact_path": rel,
            "sha256": row["sha256"],
            "hash_status": row.get("hash_status", ""),
            "size_bytes": row["size_bytes"],
            "mtime_utc": row["mtime_utc"],
        }
        entries.append(item)
        by_path[rel].append(item)

    summaries: list[dict[str, Any]] = []
    summary_lookup: dict[str, dict[str, Any]] = {}
    all_paths = sorted(set(by_path) | set(baseline))
    for rel in all_paths:
        present = by_path.get(rel, [])
        hashes: dict[str, list[str]] = defaultdict(list)
        for item in present:
            hashes[item["sha256"]].append(item["source_host"])
        variants = {digest: sorted(hosts) for digest, hosts in sorted(hashes.items())}
        present_hosts = sorted({item["source_host"] for item in present})
        missing_hosts = sorted(set(host_names) - set(present_hosts))
        baseline_item = baseline.get(rel)
        if not present:
            cross_status = "baseline_only_missing_all_hosts"
        elif len(hashes) > 1:
            cross_status = "conflict_across_hosts"
        elif missing_hosts:
            cross_status = "same_across_present_hosts_missing_others"
        else:
            cross_status = "same_across_all_hosts"
        if baseline_item is None:
            baseline_status = "new_vs_baseline" if present else "not_applicable"
        else:
            matching = sum(1 for item in present if item["sha256"] == baseline_item["sha256"])
            differing = len(present) - matching
            if not present:
                baseline_status = "baseline_only_missing_all_hosts"
            elif matching and differing:
                baseline_status = "mixed_same_and_conflict_vs_baseline"
            elif differing:
                baseline_status = "conflict_vs_baseline"
            else:
                baseline_status = "same_as_baseline"
        summary = {
            "artifact_path": rel,
            "present_host_count": len(present_hosts),
            "total_host_count": len(host_names),
            "present_hosts_json": canonical_json(present_hosts),
            "missing_hosts_json": canonical_json(missing_hosts),
            "variant_count": len(hashes),
            "hash_to_hosts_json": canonical_json(variants),
            "cross_host_status": cross_status,
            "baseline_present": baseline_item is not None,
            "baseline_sha256": baseline_item["sha256"] if baseline_item else "",
            "baseline_size_bytes": baseline_item["size_bytes"] if baseline_item else "",
            "baseline_status": baseline_status,
        }
        summaries.append(summary)
        summary_lookup[rel] = summary

    enriched: list[dict[str, Any]] = []
    for item in entries:
        summary = summary_lookup[item["artifact_path"]]
        baseline_item = baseline.get(item["artifact_path"])
        if baseline_item is None:
            host_baseline_status = "new_vs_baseline" if baseline else "baseline_not_supplied"
        elif baseline_item["sha256"] == item["sha256"]:
            host_baseline_status = "same_as_baseline"
        else:
            host_baseline_status = "conflict_vs_baseline"
        enriched.append(
            {
                **item,
                "cross_host_status": summary["cross_host_status"],
                "variant_count": summary["variant_count"],
                "host_baseline_status": host_baseline_status,
                "baseline_sha256": baseline_item["sha256"] if baseline_item else "",
            }
        )
    enriched.sort(key=lambda r: (r["artifact_path"], r["source_host"]))
    return enriched, summaries


def iter_jsonl(
    path: DataRef,
    host: str,
    source_path: str,
    category: str,
    error_rows: list[dict[str, Any]],
) -> Iterator[tuple[int, dict[str, Any]]]:
    try:
        with open_text_ref(path) as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError(f"expected object, found {type(value).__name__}")
                    yield line_number, value
                except (json.JSONDecodeError, ValueError) as exc:
                    error_rows.append(
                        {
                            "source_host": host,
                            "source_path": source_path,
                            "line": line_number,
                            "category": category,
                            "detail": redact(str(exc)),
                        }
                    )
    except OSError as exc:
        error_rows.append(
            {
                "source_host": host,
                "source_path": source_path,
                "line": "",
                "category": f"{category}_read_error",
                "detail": redact(str(exc)),
            }
        )


def citation_files(manifest: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in manifest
        if is_regular_content(row) and PurePosixPath(row["path"]).name.lower() == "citations.jsonl"
    ]


def normalize_citations(
    manifest: Sequence[dict[str, Any]],
    lookup: dict[tuple[str, str], DataRef],
    error_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    occurrences: list[dict[str, Any]] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    recognized = {"citer", "cited", "file", "artifact", "time", "note"}
    for file_row in citation_files(manifest):
        path = lookup.get((file_row["source_host"], file_row["path"]))
        if path is None:
            continue
        for line_number, record in iter_jsonl(path, file_row["source_host"], file_row["path"], "citation_jsonl_parse_error", error_rows):
            raw_file = record.get("file")
            raw_artifact = record.get("artifact")
            if raw_file is not None and raw_artifact is not None:
                schema_variant = "both_file_and_artifact"
                artifact = raw_artifact
            elif raw_artifact is not None:
                schema_variant = "artifact"
                artifact = raw_artifact
            elif raw_file is not None:
                schema_variant = "file"
                artifact = raw_file
            else:
                schema_variant = "neither"
                artifact = None
            if isinstance(artifact, str):
                artifact = str(PurePosixPath(artifact.replace("\\", "/")))
                if artifact.startswith("./"):
                    artifact = artifact[2:]
            extras = {str(key): value for key, value in record.items() if str(key) not in recognized}
            normalized = {
                "citer": record.get("citer"),
                "cited": record.get("cited"),
                "artifact": artifact,
                "time": record.get("time"),
                "note": record.get("note"),
                "extras": extras,
            }
            event_json = canonical_json(normalized)
            event_hash = sha256_bytes(event_json.encode("utf-8"))
            occurrence = {
                "source_host": file_row["source_host"],
                "source_path": file_row["path"],
                "source_line": line_number,
                "schema_variant": schema_variant,
                "citer": record.get("citer", ""),
                "cited": record.get("cited", ""),
                "artifact": artifact if artifact is not None else "",
                "time": record.get("time", ""),
                "note": record.get("note", ""),
                "extras_json": canonical_json(extras),
                "canonical_event_sha256": event_hash,
                "canonical_event_json": event_json,
            }
            occurrences.append(occurrence)
            grouped[event_hash].append(occurrence)

    deduped: list[dict[str, Any]] = []
    for event_hash in sorted(grouped):
        group = grouped[event_hash]
        first = group[0]
        locations = [
            {"host": item["source_host"], "path": item["source_path"], "line": item["source_line"]}
            for item in group
        ]
        deduped.append(
            {
                "canonical_event_sha256": event_hash,
                "citer": first["citer"],
                "cited": first["cited"],
                "artifact": first["artifact"],
                "time": first["time"],
                "note": first["note"],
                "extras_json": first["extras_json"],
                "canonical_event_json": first["canonical_event_json"],
                "occurrence_count": len(group),
                "source_host_count": len({item["source_host"] for item in group}),
                "source_hosts_json": canonical_json(sorted({item["source_host"] for item in group})),
                "source_locations_json": canonical_json(locations),
            }
        )
    occurrences.sort(key=lambda r: (r["source_host"], r["source_path"], r["source_line"]))
    return occurrences, deduped


def message_files(manifest: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in manifest
        if is_regular_content(row)
        and PurePosixPath(row["path"]).suffix.lower() == ".jsonl"
        and PurePosixPath(row["path"]).name.lower().startswith("messages")
    ]


def parse_messages(
    manifest: Sequence[dict[str, Any]],
    lookup: dict[tuple[str, str], DataRef],
    error_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_acc: dict[tuple[str, str], dict[str, Any]] = {}
    actor_acc: dict[tuple[str, str], dict[str, Any]] = {}
    canonical_occurrences: Counter[str] = Counter()
    global_records = 0
    for file_row in message_files(manifest):
        key = (file_row["source_host"], file_row["path"])
        acc = {
            "source_host": file_row["source_host"],
            "source_path": file_row["path"],
            "record_count": 0,
            "broadcast_count": 0,
            "direct_count": 0,
            "unknown_recipient_count": 0,
            "message_chars": 0,
            "min_time": None,
            "max_time": None,
            "canonical_hashes": Counter(),
        }
        source_acc[key] = acc
        path = lookup.get(key)
        if path is None:
            continue
        for _, record in iter_jsonl(path, file_row["source_host"], file_row["path"], "message_jsonl_parse_error", error_rows):
            global_records += 1
            acc["record_count"] += 1
            from_value = str(record.get("from", record.get("sender", "")))
            to_value = record.get("to", record.get("recipient"))
            to_text = "" if to_value is None else str(to_value)
            message = record.get("message", record.get("content", ""))
            message_text = message if isinstance(message, str) else canonical_json(message)
            timestamp = record.get("time", record.get("timestamp"))
            timestamp_text = "" if timestamp is None else str(timestamp)
            if to_text.lower() in {"all", "everyone", "broadcast", "*"}:
                acc["broadcast_count"] += 1
            elif to_text:
                acc["direct_count"] += 1
            else:
                acc["unknown_recipient_count"] += 1
            acc["message_chars"] += len(message_text)
            if timestamp_text:
                acc["min_time"] = timestamp_text if acc["min_time"] is None else min(acc["min_time"], timestamp_text)
                acc["max_time"] = timestamp_text if acc["max_time"] is None else max(acc["max_time"], timestamp_text)
            event_hash = sha256_bytes(canonical_json(record).encode("utf-8"))
            acc["canonical_hashes"][event_hash] += 1
            canonical_occurrences[event_hash] += 1

            actor_key = (file_row["source_host"], from_value)
            actor = actor_acc.setdefault(
                actor_key,
                {
                    "source_host": file_row["source_host"],
                    "actor": from_value,
                    "sent_count": 0,
                    "broadcast_sent_count": 0,
                    "direct_sent_count": 0,
                    "message_chars": 0,
                    "recipient_counts": Counter(),
                },
            )
            actor["sent_count"] += 1
            actor["message_chars"] += len(message_text)
            actor["recipient_counts"][to_text] += 1
            if to_text.lower() in {"all", "everyone", "broadcast", "*"}:
                actor["broadcast_sent_count"] += 1
            elif to_text:
                actor["direct_sent_count"] += 1

    stats_rows: list[dict[str, Any]] = []
    for key in sorted(source_acc):
        acc = source_acc[key]
        unique_count = len(acc["canonical_hashes"])
        duplicate_count = acc["record_count"] - unique_count
        stats_rows.append(
            {
                "source_host": acc["source_host"],
                "source_path": acc["source_path"],
                "record_count": acc["record_count"],
                "unique_within_source_count": unique_count,
                "duplicate_within_source_count": duplicate_count,
                "broadcast_count": acc["broadcast_count"],
                "direct_count": acc["direct_count"],
                "unknown_recipient_count": acc["unknown_recipient_count"],
                "message_chars": acc["message_chars"],
                "mean_message_chars": round(acc["message_chars"] / acc["record_count"], 3) if acc["record_count"] else 0,
                "min_time_lexical": acc["min_time"] or "",
                "max_time_lexical": acc["max_time"] or "",
            }
        )

    actor_rows: list[dict[str, Any]] = []
    for key in sorted(actor_acc):
        acc = actor_acc[key]
        actor_rows.append(
            {
                "source_host": acc["source_host"],
                "actor": acc["actor"],
                "sent_count": acc["sent_count"],
                "broadcast_sent_count": acc["broadcast_sent_count"],
                "direct_sent_count": acc["direct_sent_count"],
                "message_chars": acc["message_chars"],
                "mean_message_chars": round(acc["message_chars"] / acc["sent_count"], 3) if acc["sent_count"] else 0,
                "distinct_recipients": len(acc["recipient_counts"]),
                "recipient_counts_json": canonical_json(dict(sorted(acc["recipient_counts"].items()))),
            }
        )
    message_summary = {
        "occurrence_count": global_records,
        "canonical_unique_count": len(canonical_occurrences),
        "duplicate_occurrences_count": global_records - len(canonical_occurrences),
        "events_seen_more_than_once_count": sum(1 for count in canonical_occurrences.values() if count > 1),
    }
    return stats_rows, actor_rows, message_summary


def build_execution_evidence(
    snapshots: Sequence[Snapshot],
    planned: dict[str, set[int]],
    spawned: dict[str, Counter[int]],
    log_rows: Sequence[dict[str, Any]],
    session_agents: dict[str, Counter[int]],
) -> list[dict[str, Any]]:
    log_acc: dict[tuple[str, int], dict[str, Any]] = {}
    for row in log_rows:
        if row["agent_number"] == "":
            continue
        key = (row["source_host"], int(row["agent_number"]))
        acc = log_acc.setdefault(
            key,
            {
                "files": [],
                "lines": 0,
                "start": 0,
                "errors": 0,
                "rate_limits": 0,
                "api_requests": 0,
                "api_http_200": 0,
                "tools": 0,
                "responses": 0,
                "response_success": 0,
                "finished": 0,
                "success": False,
                "basis": set(),
            },
        )
        acc["files"].append(row["path"])
        acc["lines"] += int(row["line_count"])
        acc["start"] += int(row["start_marker_count"])
        acc["errors"] += int(row["error_line_count"])
        acc["rate_limits"] += int(row["rate_limit_429_line_count"])
        acc["api_requests"] += int(row["api_http_request_line_count"])
        acc["api_http_200"] += int(row["api_http_200_request_line_count"])
        acc["tools"] += int(row["tool_event_count"])
        acc["responses"] += int(row["response_prefix_count"])
        acc["response_success"] += int(row["response_prefix_success_count"])
        acc["finished"] += int(row["finished_marker_count"])
        acc["success"] = acc["success"] or bool(row["success_evidence"])
        if row["success_evidence_basis"]:
            acc["basis"].update(row["success_evidence_basis"].split("+"))

    rows: list[dict[str, Any]] = []
    for snap in snapshots:
        numbers = set(planned.get(snap.host, set())) | set(spawned.get(snap.host, {})) | set(session_agents.get(snap.host, {}))
        numbers |= {number for host, number in log_acc if host == snap.host}
        for number in sorted(numbers):
            log = log_acc.get((snap.host, number))
            has_plan = number in planned.get(snap.host, set())
            spawn_count = spawned.get(snap.host, Counter()).get(number, 0)
            session_count = session_agents.get(snap.host, Counter()).get(number, 0)
            log_files = log["files"] if log else []
            success = bool(log and log["success"])
            if success:
                evidence_level = "success_evidence"
            elif log_files or spawn_count or session_count:
                evidence_level = "log_or_start_footprint_only"
            elif has_plan:
                evidence_level = "planned_only"
            else:
                evidence_level = "unclassified"
            rows.append(
                {
                    "source_host": snap.host,
                    "agent_id": f"agent-{number}",
                    "agent_number": number,
                    "planned_from_assigned_command": has_plan,
                    "launcher_spawn_line_count": spawn_count,
                    "session_record_count": session_count,
                    "log_file_count": len(log_files),
                    "log_files_json": canonical_json(sorted(log_files)),
                    "log_line_count": log["lines"] if log else 0,
                    "start_marker_count": log["start"] if log else 0,
                    "error_line_count": log["errors"] if log else 0,
                    "rate_limit_429_line_count": log["rate_limits"] if log else 0,
                    "api_http_request_line_count": log["api_requests"] if log else 0,
                    "api_http_200_request_line_count": log["api_http_200"] if log else 0,
                    "api_http_200_interpretation": (
                        "Logged successful API-request count only; multiple API requests can occur inside one model turn, "
                        "and it carries no token quantity."
                    ),
                    "tool_event_count": log["tools"] if log else 0,
                    "response_prefix_count": log["responses"] if log else 0,
                    "response_prefix_success_count": log["response_success"] if log else 0,
                    "finished_marker_count": log["finished"] if log else 0,
                    "success_evidence": success,
                    "success_evidence_basis": "+".join(sorted(log["basis"])) if log else "",
                    "evidence_level": evidence_level,
                    "interpretation_guardrail": (
                        "success_evidence means at least one logged HTTP 200 API request; it does not prove "
                        "a complete outer turn, meaningful response, social action, task completion, tokens, or cost."
                    ),
                }
            )
    return rows


def write_csv(path: Path, rows: Sequence[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def manifest_fingerprint(rows: Sequence[dict[str, Any]]) -> str:
    stable = [
        {
            "host": row["source_host"],
            "path": row["path"],
            "kind": row["kind"],
            "size": row["size_bytes"],
            "mtime_ns": row["mtime_ns"],
            "sha256": row["sha256"],
            "hash_status": row.get("hash_status", ""),
            "symlink_target": row["symlink_target"],
        }
        for row in rows
    ]
    return sha256_bytes(canonical_json(stable).encode("utf-8"))


def summarize_source_variants(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for row in rows:
        groups[(row["component"], row["basename"])][row["sha256"]].add(row["source_host"])
    result: list[dict[str, Any]] = []
    for (component, basename), variants in sorted(groups.items()):
        result.append(
            {
                "component": component,
                "basename": basename,
                "variant_count": len(variants),
                "hash_to_hosts": {digest: sorted(hosts) for digest, hosts in sorted(variants.items())},
            }
        )
    return result


def compact_machine_summary(
    snapshots: Sequence[Snapshot],
    manifest: Sequence[dict[str, Any]],
    logs: Sequence[dict[str, Any]],
    sessions: Sequence[dict[str, Any]],
    evidence: Sequence[dict[str, Any]],
    commons: Sequence[dict[str, Any]],
    citations: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for snap in snapshots:
        host = snap.host
        host_manifest = [row for row in manifest if row["source_host"] == host]
        host_logs = [row for row in logs if row["source_host"] == host]
        host_sessions = [row for row in sessions if row["source_host"] == host]
        host_evidence = [row for row in evidence if row["source_host"] == host]
        host_commons = [row for row in commons if row["source_host"] == host]
        host_citations = [row for row in citations if row["source_host"] == host]
        content_mtimes = [str(row["mtime_utc"]) for row in host_manifest if row.get("mtime_utc")]
        root_info = snap.root.stat()
        result.append(
            {
                "source_host": host,
                "root": str(snap.root),
                "swarm": str(snap.swarm) if snap.swarm else None,
                "swarmctl": str(snap.swarmctl) if snap.swarmctl else None,
                "swarmctl_archive": str(snap.swarmctl_archive) if snap.swarmctl_archive else None,
                "local_snapshot_root_mtime_utc": utc_iso_from_ns(root_info.st_mtime_ns),
                "manifest_content_mtime_min_utc": min(content_mtimes) if content_mtimes else None,
                "manifest_content_mtime_max_utc": max(content_mtimes) if content_mtimes else None,
                "manifest_file_count": len(host_manifest),
                "manifest_bytes": sum(int(row["size_bytes"]) for row in host_manifest),
                "agent_log_file_count": len(host_logs),
                "session_record_count": len(host_sessions),
                "execution_evidence_agent_count": len(host_evidence),
                "planned_agent_count": sum(bool(row["planned_from_assigned_command"]) for row in host_evidence),
                "log_or_start_footprint_agent_count": sum(
                    bool(row["log_file_count"] or row["launcher_spawn_line_count"] or row["session_record_count"])
                    for row in host_evidence
                ),
                "success_evidence_agent_count": sum(bool(row["success_evidence"]) for row in host_evidence),
                "rate_limit_429_line_count": sum(int(row["rate_limit_429_line_count"]) for row in host_logs),
                "api_http_request_line_count": sum(int(row["api_http_request_line_count"]) for row in host_logs),
                "api_http_200_request_line_count": sum(int(row["api_http_200_request_line_count"]) for row in host_logs),
                "error_line_count": sum(int(row["error_line_count"]) for row in host_logs),
                "commons_artifact_count": len(host_commons),
                "citation_occurrence_count": len(host_citations),
            }
        )
    return result


def build_summary(
    args: argparse.Namespace,
    snapshots: Sequence[Snapshot],
    manifest: Sequence[dict[str, Any]],
    source_rows: Sequence[dict[str, Any]],
    plans: Sequence[dict[str, Any]],
    logs: Sequence[dict[str, Any]],
    session_records: Sequence[dict[str, Any]],
    session_schemas: Sequence[dict[str, Any]],
    evidence: Sequence[dict[str, Any]],
    commons: Sequence[dict[str, Any]],
    commons_summary: Sequence[dict[str, Any]],
    citation_occurrences: Sequence[dict[str, Any]],
    citation_deduped: Sequence[dict[str, Any]],
    message_summary: dict[str, Any],
    errors: Sequence[dict[str, Any]],
    baseline_root: Path | None,
) -> dict[str, Any]:
    evidence_levels = Counter(str(row["evidence_level"]) for row in evidence)
    commons_statuses = Counter(str(row["cross_host_status"]) for row in commons_summary)
    baseline_statuses = Counter(str(row["baseline_status"]) for row in commons_summary)
    citation_schema = Counter(str(row["schema_variant"]) for row in citation_occurrences)
    control_archives: list[dict[str, Any]] = []
    for row in manifest:
        if row["plane"] != "archive_container":
            continue
        member_count = sum(
            1
            for candidate in manifest
            if candidate["source_host"] == row["source_host"]
            and candidate["plane"] == "swarmctl"
            and candidate.get("container_path") == row.get("container_path")
        )
        control_archives.append(
            {
                "source_host": row["source_host"],
                "path": row.get("container_path", ""),
                "size_bytes": row["size_bytes"],
                "sha256": row["sha256"],
                "regular_or_link_member_count": member_count,
                "content_status": "empty_no_file_members" if member_count == 0 else "members_present",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "generated_at_utc": generated_at(),
        "source_date_epoch_used": bool(os.environ.get("SOURCE_DATE_EPOCH")),
        "input_snapshot_fingerprint_sha256": manifest_fingerprint(manifest),
        "inputs": [
            {
                "source_host": snap.host,
                "root": str(snap.root),
                "swarm": str(snap.swarm) if snap.swarm else None,
                "swarmctl": str(snap.swarmctl) if snap.swarmctl else None,
                "swarmctl_archive": str(snap.swarmctl_archive) if snap.swarmctl_archive else None,
            }
            for snap in snapshots
        ],
        "baseline_commons_root": str(baseline_root) if baseline_root else None,
        "control_archives": sorted(control_archives, key=lambda item: item["source_host"]),
        "method_guardrails": {
            "read_only": True,
            "planned_definition": "Static launcher defaults or command text only; never counted as execution.",
            "log_footprint_definition": "Agent log, launcher spawn line, or devbox_sessions record exists; not task success.",
            "success_evidence_definition": (
                "At least one logged HTTP 200 API request. This is evidence of provider/API success, not proof of "
                "a complete outer turn, meaningful response, social action, intended-task completion, tokens, or cost."
            ),
            "http_200_definition": (
                "Each logged HTTP 200 is one successful API request. It is not a model turn, complete response, "
                "token count, cost unit, agent, or task completion; one turn can require multiple API requests."
            ),
            "citation_deduplication": "Exact canonical normalized JSON excluding source provenance; provenance retained separately.",
            "message_times": "Min/max are lexical because mixed timestamp schemas/timezones may be present.",
            "attribution_warning": "JSONL from/citer fields are labels, not authenticated actor identities.",
            "log_identity_warning": (
                "An agent log pathname/inode is a snapshot footprint, not an independent session. The launcher opens logs "
                "with write/truncate semantics; duplicate or overlapping launches can replace or interleave evidence."
            ),
            "snapshot_time_warning": (
                "Machine pulls and parsing are not simultaneous. generated_at_utc is parser time; local root and content "
                "mtime fields are recorded per machine, and the content fingerprint identifies the exact observed cut."
            ),
        },
        "counts": {
            "machine_count": len(snapshots),
            "manifest_file_count": len(manifest),
            "source_candidate_count": len(source_rows),
            "plan_observation_count": len(plans),
            "agent_log_file_count": len(logs),
            "session_file_count": len(session_schemas),
            "session_record_count": len(session_records),
            "execution_evidence_agent_count": len(evidence),
            "execution_evidence_levels": dict(sorted(evidence_levels.items())),
            "commons_artifact_occurrence_count": len(commons),
            "commons_unique_path_count": len(commons_summary),
            "commons_cross_host_statuses": dict(sorted(commons_statuses.items())),
            "commons_baseline_statuses": dict(sorted(baseline_statuses.items())),
            "citation_occurrence_count": len(citation_occurrences),
            "citation_canonical_unique_count": len(citation_deduped),
            "citation_duplicate_occurrence_count": len(citation_occurrences) - len(citation_deduped),
            "citation_schema_variants": dict(sorted(citation_schema.items())),
            "parse_or_read_error_count": len(errors),
            "messages": message_summary,
        },
        "machines": compact_machine_summary(
            snapshots, manifest, logs, session_records, evidence, commons, citation_occurrences
        ),
        "source_hash_variants": summarize_source_variants(source_rows),
        "risks": [
            "An interrupted/incremental rsync may yield a temporally inconsistent snapshot; inspect FETCH_COMPLETE and fetch.log outside this parser.",
            "Byte-identical hashes prove content equality only, not when or whether code executed.",
            "Launcher defaults and command lines are plans. Aggregate 'agents launched' lines are self-reports, not response-level evidence.",
            "Response text in runner logs is truncated by the runner; full conversations and exact token use are not recoverable from these logs alone.",
            "devbox_sessions.json may be incomplete or clobbered if writers used unlocked read-modify-write.",
            "A log file, agent label, or devbox_sessions record is not a one-to-one independent-session identifier; relaunches can truncate/overwrite the same log path.",
            "A missing file may mean never-created, not-yet-synced, deleted, or omitted by an incomplete transfer.",
            "The parser does not validate factual quality of artifacts, messages, citations, or response prefixes.",
        ],
    }


CSV_SCHEMAS: dict[str, list[str]] = {
    "manifest.csv": [
        "source_host", "plane", "path", "kind", "size_bytes", "mtime_ns", "mtime_utc", "sha256", "hash_status",
        "symlink_target", "container_path", "member_name",
    ],
    "source_hashes.csv": ["source_host", "component", "basename", "path", "sha256", "size_bytes", "mtime_utc"],
    "plan_observations.csv": [
        "source_host", "source_path", "line", "observation_type", "proof_level", "start", "end_exclusive",
        "batch_index", "batch_count", "max_concurrent", "declared_or_derived_count", "agent_number", "detail",
    ],
    "agent_log_footprints.csv": [
        "source_host", "path", "size_bytes", "sha256", "agent_id", "agent_number", "identity_source",
        "identity_mentions_json", "identity_conflict", "line_count", "nonempty_line_count", "start_marker_count",
        "providers_json", "error_line_count", "error_line_numbers_json", "rate_limit_429_line_count",
        "rate_limit_line_numbers_json", "api_http_request_line_count", "api_http_200_request_line_count",
        "api_http_status_counts_json", "api_http_200_interpretation", "tool_event_count", "tool_names_json", "response_prefix_count",
        "response_prefix_success_count", "response_prefix_failure_count", "response_prefix_examples_json",
        "finished_marker_count", "max_finished_turn", "success_evidence", "success_evidence_basis",
    ],
    "session_records.csv": [
        "source_host", "source_path", "record_index", "agent_id", "agent_number", "raw_id", "provider", "model",
        "pid", "started_at", "host_field", "session_id", "record_keys_json", "extra_json", "canonical_record_sha256",
    ],
    "session_schemas.csv": [
        "source_host", "path", "parse_status", "top_level_type", "record_count", "dict_record_count",
        "non_dict_record_count", "key_presence_json", "key_types_json", "schema_variants_json",
    ],
    "execution_evidence.csv": [
        "source_host", "agent_id", "agent_number", "planned_from_assigned_command", "launcher_spawn_line_count",
        "session_record_count", "log_file_count", "log_files_json", "log_line_count", "start_marker_count",
        "error_line_count", "rate_limit_429_line_count", "api_http_request_line_count", "api_http_200_request_line_count",
        "api_http_200_interpretation", "tool_event_count", "response_prefix_count",
        "response_prefix_success_count", "finished_marker_count", "success_evidence", "success_evidence_basis",
        "evidence_level", "interpretation_guardrail",
    ],
    "commons_artifacts.csv": [
        "source_host", "artifact_path", "sha256", "size_bytes", "mtime_utc", "cross_host_status", "variant_count",
        "host_baseline_status", "baseline_sha256",
    ],
    "commons_path_summary.csv": [
        "artifact_path", "present_host_count", "total_host_count", "present_hosts_json", "missing_hosts_json",
        "variant_count", "hash_to_hosts_json", "cross_host_status", "baseline_present", "baseline_sha256",
        "baseline_size_bytes", "baseline_status",
    ],
    "citations_occurrences.csv": [
        "source_host", "source_path", "source_line", "schema_variant", "citer", "cited", "artifact", "time", "note",
        "extras_json", "canonical_event_sha256", "canonical_event_json",
    ],
    "citations_dedup.csv": [
        "canonical_event_sha256", "citer", "cited", "artifact", "time", "note", "extras_json", "canonical_event_json",
        "occurrence_count", "source_host_count", "source_hosts_json", "source_locations_json",
    ],
    "messages_stats.csv": [
        "source_host", "source_path", "record_count", "unique_within_source_count", "duplicate_within_source_count",
        "broadcast_count", "direct_count", "unknown_recipient_count", "message_chars", "mean_message_chars",
        "min_time_lexical", "max_time_lexical",
    ],
    "messages_actor_stats.csv": [
        "source_host", "actor", "sent_count", "broadcast_sent_count", "direct_sent_count", "message_chars",
        "mean_message_chars", "distinct_recipients", "recipient_counts_json",
    ],
    "parse_errors.csv": ["source_host", "source_path", "line", "category", "detail"],
}


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="ROOT",
        help="Root with workspace-id/{swarm,swarmctl}, a single machine root, or a workspace itself; repeatable.",
    )
    parser.add_argument(
        "--workspace",
        action="append",
        default=[],
        metavar="HOST=PATH",
        help="Explicit host label and machine/workspace path; repeatable.",
    )
    parser.add_argument(
        "--baseline",
        metavar="WORKSPACE",
        help="Optional prior-round workspace (or commons directory) for commons new/same/conflict classification.",
    )
    parser.add_argument(
        "--file-read-timeout",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help=(
            "Per-file alarm in single-worker hashing for offline/cloud stubs; 0 disables. "
            "Parallel worker threads cannot interrupt a blocked OS open (default: 30)."
        ),
    )
    parser.add_argument(
        "--hash-workers",
        type=int,
        default=8,
        metavar="N",
        help="Parallel workers for already-local read-only file hashing (default: 8).",
    )
    parser.add_argument("--output-dir", required=True, metavar="DIR", help="New or empty audit output directory.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    global FILE_READ_TIMEOUT_SECONDS, HASH_WORKERS
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        if args.file_read_timeout < 0:
            raise ValueError("--file-read-timeout must be >= 0")
        if args.hash_workers < 1:
            raise ValueError("--hash-workers must be >= 1")
        FILE_READ_TIMEOUT_SECONDS = float(args.file_read_timeout)
        HASH_WORKERS = int(args.hash_workers)
        snapshots = discover_inputs(args.input, args.workspace)
        baseline_root = baseline_commons_root(args.baseline)
        output_dir = Path(args.output_dir).expanduser().resolve()
        for snap in snapshots:
            if path_is_within(output_dir, snap.root):
                raise ValueError(f"output directory must not be inside an input snapshot: {output_dir}")
        if baseline_root is not None and path_is_within(output_dir, baseline_root):
            raise ValueError(f"output directory must not be inside the baseline: {output_dir}")
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError(f"output directory must be new or empty: {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

        errors: list[dict[str, Any]] = []
        manifest, lookup = build_manifest(snapshots, errors)
        source_rows = source_hash_rows(manifest)
        plan_rows, planned_agents, spawned_agents = scan_plan_observations(source_rows, manifest, lookup, errors)
        log_rows = scan_agent_logs(manifest, lookup, errors)
        session_records, session_schemas, session_agents = parse_sessions(manifest, lookup, errors)
        baseline = hash_baseline_commons(baseline_root, errors)
        commons, commons_summary = commons_rows(snapshots, manifest, baseline)
        citation_occurrences, citation_deduped = normalize_citations(manifest, lookup, errors)
        message_stats, message_actor_stats, message_summary = parse_messages(manifest, lookup, errors)
        execution_evidence = build_execution_evidence(
            snapshots, planned_agents, spawned_agents, log_rows, session_agents
        )

        tables: dict[str, Sequence[dict[str, Any]]] = {
            "manifest.csv": manifest,
            "source_hashes.csv": source_rows,
            "plan_observations.csv": plan_rows,
            "agent_log_footprints.csv": log_rows,
            "session_records.csv": session_records,
            "session_schemas.csv": session_schemas,
            "execution_evidence.csv": execution_evidence,
            "commons_artifacts.csv": commons,
            "commons_path_summary.csv": commons_summary,
            "citations_occurrences.csv": citation_occurrences,
            "citations_dedup.csv": citation_deduped,
            "messages_stats.csv": message_stats,
            "messages_actor_stats.csv": message_actor_stats,
            "parse_errors.csv": errors,
        }
        for filename, rows in tables.items():
            write_csv(output_dir / filename, rows, CSV_SCHEMAS[filename])

        summary = build_summary(
            args,
            snapshots,
            manifest,
            source_rows,
            plan_rows,
            log_rows,
            session_records,
            session_schemas,
            execution_evidence,
            commons,
            commons_summary,
            citation_occurrences,
            citation_deduped,
            message_summary,
            errors,
            baseline_root,
        )
        (output_dir / "audit_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(canonical_json({"output_dir": str(output_dir), "counts": summary["counts"]}))
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
