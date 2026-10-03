import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Tuple

from backend.app.core.config import get_settings
from backend.app.parser.errors import (
    NestedArchiveExceededError,
    ParserSecurityError,
    ZipBombError,
    ZipSlipError,
)
from backend.app.parser.models import ArchiveInventoryItem

logger = logging.getLogger(__name__)


class SafeArchiveInspector:
    """
    Forensic archive inspection and controlled extraction engine.
    Guarantees isolation against ZipSlip, ZipBomb, nested archive recursion, and resource exhaustion.
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def inspect_and_build_inventory(
        self,
        archive_path: str,
        current_depth: int = 0,
    ) -> List[ArchiveInventoryItem]:
        """
        Inspect an archive's member table without decompressing to RAM.
        Validates paths and security constraints, returning a structured inventory.
        """
        if current_depth > self.settings.MAX_ARCHIVE_DEPTH:
            raise NestedArchiveExceededError(
                f"Archive nesting depth {current_depth} exceeds configured maximum {self.settings.MAX_ARCHIVE_DEPTH}"
            )

        if not os.path.exists(archive_path):
            raise ParserSecurityError(f"Evidence archive file does not exist: {archive_path}")

        inventory: List[ArchiveInventoryItem] = []
        total_uncompressed = 0
        total_compressed = 0

        max_entries = self.settings.MAX_ARCHIVE_ENTRIES
        max_single_entry = self.settings.MAX_SINGLE_ENTRY_SIZE_MB * 1024 * 1024
        max_total_size = self.settings.MAX_TOTAL_UNCOMPRESSED_SIZE_MB * 1024 * 1024
        max_ratio = self.settings.MAX_COMPRESSION_RATIO

        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                infolist = zf.infolist()

                if len(infolist) > max_entries:
                    raise ZipBombError(
                        f"Archive entry count {len(infolist)} exceeds threshold of {max_entries}"
                    )

                for info in infolist:
                    filename = info.filename

                    # 1. ZipSlip Path Traversal Protection
                    self._validate_path_traversal(filename)

                    # Skip directory records in file accounting
                    if filename.endswith('/') or filename.endswith('\\') or info.is_dir():
                        continue

                    # 2. Single Entry Decompression Limit
                    if info.file_size > max_single_entry:
                        raise ZipBombError(
                            f"Archive entry '{filename}' uncompressed size ({info.file_size} bytes) "
                            f"exceeds single entry limit ({max_single_entry} bytes)"
                        )

                    # 3. Total Uncompressed Limit
                    total_uncompressed += info.file_size
                    total_compressed += info.compress_size
                    if total_uncompressed > max_total_size:
                        raise ZipBombError(
                            f"Archive cumulative uncompressed size ({total_uncompressed} bytes) "
                            f"exceeds threshold of {max_total_size} bytes"
                        )

                    # 4. Compression Ratio (Zip Bomb Heuristic)
                    if info.file_size > 1024 * 1024:  # Check only if uncompressed > 1MB
                        compressed_base = max(info.compress_size, 1)
                        ratio = info.file_size / compressed_base
                        if ratio > max_ratio:
                            raise ZipBombError(
                                f"Archive entry '{filename}' suspicious compression ratio {ratio:.1f}:1 "
                                f"exceeds safety threshold {max_ratio}:1"
                            )

                    # Determine extension and type
                    ext = Path(filename).suffix.lower()
                    is_nested = ext in [".zip", ".ufdr", ".tar", ".gz"]
                    detected_type = "xml" if ext == ".xml" else ("archive" if is_nested else "data")

                    item = ArchiveInventoryItem(
                        path=filename,
                        file_size=info.file_size,
                        compressed_size=info.compress_size,
                        extension=ext,
                        detected_type=detected_type,
                        depth=current_depth,
                        is_nested_archive=is_nested,
                    )
                    inventory.append(item)

        except zipfile.BadZipFile as e:
            raise ParserSecurityError(f"Evidence file is not a valid ZIP/UFDR archive: {e}")

        logger.info(
            f"Inspected archive '{archive_path}': {len(inventory)} valid entries, "
            f"{total_uncompressed} bytes uncompressed."
        )
        return inventory

    def _validate_path_traversal(self, filename: str) -> None:
        """Reject paths with absolute prefixes or parent traversal sequences."""
        clean_name = filename.replace("\\", "/")
        if clean_name.startswith("/") or clean_name.startswith("//"):
            raise ZipSlipError(f"Malicious archive member with absolute path: {filename}")

        if ":" in clean_name and (clean_name[1:2] == ":" or clean_name[0:1].isalpha()):
            raise ZipSlipError(f"Malicious archive member with Windows drive path: {filename}")

        parts = clean_name.split("/")
        depth = 0
        for part in parts:
            if not part or part == ".":
                continue
            if part == "..":
                depth -= 1
                if depth < 0:
                    raise ZipSlipError(f"Malicious ZipSlip path traversal detected: {filename}")
            else:
                depth += 1

    def safe_extract_to_sandbox(
        self,
        archive_path: str,
        sandbox_dir: str,
        file_filter: List[str] = None,
    ) -> List[Tuple[str, str]]:
        """
        Safely extracts allowed entries into an isolated temporary directory.
        Never calls zipfile.extractall().
        Returns list of (archive_path, local_extracted_path).
        """
        sandbox_path = Path(sandbox_dir).resolve()
        sandbox_path.mkdir(parents=True, exist_ok=True)
        extracted: List[Tuple[str, str]] = []

        with zipfile.ZipFile(archive_path, 'r') as zf:
            for info in zf.infolist():
                filename = info.filename
                if filename.endswith('/') or filename.endswith('\\') or info.is_dir():
                    continue

                self._validate_path_traversal(filename)

                if file_filter is not None and filename not in file_filter:
                    continue

                # Target path strictly under sandbox
                target_file_path = (sandbox_path / filename).resolve()
                if not str(target_file_path).startswith(str(sandbox_path)):
                    raise ZipSlipError(f"Target path escapes sandbox: {filename}")

                target_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Stream extraction to disk with bounded chunk size (never in full memory)
                with zf.open(info, 'r') as source_stream, open(target_file_path, 'wb') as dest_file:
                    while True:
                        chunk = source_stream.read(64 * 1024)  # 64KB buffer
                        if not chunk:
                            break
                        dest_file.write(chunk)

                extracted.append((filename, str(target_file_path)))

        return extracted

    @staticmethod
    def cleanup_sandbox(sandbox_dir: str) -> bool:
        """Safely remove the temporary extraction directory."""
        if not sandbox_dir or not os.path.exists(sandbox_dir):
            return True
        try:
            shutil.rmtree(sandbox_dir, ignore_errors=False)
            logger.info(f"Cleaned up temporary extraction sandbox: {sandbox_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup temporary sandbox directory {sandbox_dir}: {e}")
            return False
