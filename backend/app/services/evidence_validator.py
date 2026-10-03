import os
from pathlib import Path
from typing import List, Optional, Tuple
import zipfile

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger

logger = get_logger("evidence.validator")

# Standard ZIP magic byte signatures
ZIP_MAGIC_SIGNATURES = [
    b"PK\x03\x04",  # Standard archive header
    b"PK\x05\x06",  # Empty archive end of central directory
    b"PK\x07\x08",  # Spanned / data descriptor header
]

# Security thresholds for archive inspection
MAX_ARCHIVE_FILE_COUNT = 100_000
MAX_COMPRESSION_RATIO = 100.0  # Alert if uncompressed is 100x larger than compressed (for >50MB uncompressed)


class EvidenceValidator:
    """
    Validates uploaded evidence files for forensic integrity, file signature compliance,
    and defends against malicious archive exploits (ZipSlip, ZipBomb, absolute paths).
    """

    def __init__(self, allowed_extensions: Optional[List[str]] = None):
        settings = get_settings()
        self.allowed_extensions = [
            ext.lower() for ext in (allowed_extensions or settings.ALLOWED_EVIDENCE_EXTENSIONS)
        ]

    def validate_file_extension(self, filename: str) -> Tuple[bool, Optional[str], str]:
        """
        Validates that the file extension matches approved forensic formats (.ufdr, .zip).
        Returns (is_valid, error_msg, normalized_extension).
        """
        if not filename or "." not in filename:
            return False, "File must have an explicit forensic extension (.ufdr or .zip).", ""

        ext = Path(filename).suffix.lower()
        if ext not in self.allowed_extensions:
            return (
                False,
                f"Unsupported file format '{ext}'. Allowed forensic formats: {', '.join(self.allowed_extensions)}.",
                ext,
            )
        return True, None, ext

    def validate_stored_archive(
        self, file_path: Path, extension: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Performs in-depth defensive validation on the securely stored archive:
        1. Checks magic byte signatures.
        2. Validates zip file integrity.
        3. Scans for ZipSlip path traversal patterns.
        4. Calculates compression ratios to defend against ZipBomb decompression amplification.
        """
        if not file_path.is_file():
            return False, "Evidence file is missing from storage.", None

        # 1. Magic bytes verification
        try:
            with open(file_path, "rb") as f:
                header = f.read(4)
                if not any(header.startswith(sig) for sig in ZIP_MAGIC_SIGNATURES):
                    logger.warning(
                        f"File failed magic byte signature check: path={file_path}, header={header.hex()}"
                    )
                    return (
                        False,
                        "Invalid file signature: Content is not a valid UFDR or ZIP archive.",
                        None,
                    )
        except Exception as e:
            return False, f"Could not inspect file signature: {str(e)}", None

        # 2. Defensive ZIP Archive Inspection
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # Test structural integrity
                bad_file = zf.testzip()
                if bad_file:
                    return False, f"Archive integrity failure detected in entry: {bad_file}", None

                infolist = zf.infolist()
                total_files = len(infolist)

                if total_files > MAX_ARCHIVE_FILE_COUNT:
                    logger.warning(f"Archive exceeds file count threshold: count={total_files}")
                    return (
                        False,
                        f"Archive contains excessive entries ({total_files} files). Exceeds security threshold.",
                        None,
                    )

                total_uncompressed = 0
                total_compressed = 0

                # 3. ZipSlip and Traversal checks
                for info in infolist:
                    fname = info.filename
                    # Normalize and check for root escapes or traversal indicators
                    normalized = os.path.normpath(fname)

                    if (
                        fname.startswith("/")
                        or fname.startswith("\\")
                        or ":" in fname
                        or ".." in fname.split("/")
                        or ".." in fname.split("\\")
                        or normalized.startswith("..")
                        or os.path.isabs(fname)
                    ):
                        logger.error(f"ZipSlip exploit detected in archive entry: {fname}")
                        return (
                            False,
                            f"Malicious archive structure detected: Path traversal entry '{fname}'.",
                            None,
                        )

                    total_uncompressed += info.file_size
                    total_compressed += info.compress_size

                # 4. ZipBomb heuristic check
                if total_uncompressed > 50 * 1024 * 1024:  # Only evaluate ratio for uncompressed > 50MB
                    ratio = total_uncompressed / max(1, total_compressed)
                    if ratio > MAX_COMPRESSION_RATIO:
                        logger.warning(
                            f"ZipBomb decompression ratio detected: uncompressed={total_uncompressed}, compressed={total_compressed}, ratio={ratio}"
                        )
                        return (
                            False,
                            f"Suspicious archive compression ratio ({ratio:.1f}x). Potential decompression bomb.",
                            None,
                        )

        except zipfile.BadZipFile:
            return False, "File is not a valid or intact ZIP/UFDR archive.", None
        except Exception as e:
            return False, f"Archive security inspection failed: {str(e)}", None

        detected_mime = "application/x-ufdr" if extension.lower() == ".ufdr" else "application/zip"
        return True, None, detected_mime
