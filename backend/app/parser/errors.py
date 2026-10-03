class ParserError(Exception):
    """Base exception for all forensic parser errors."""
    def __init__(self, message: str, details: dict = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ParserSecurityError(ParserError):
    """Raised when an archive or file violates forensic security boundaries."""
    pass


class ZipSlipError(ParserSecurityError):
    """Raised when an archive member attempts directory traversal."""
    pass


class ZipBombError(ParserSecurityError):
    """Raised when an archive exceeds decompression ratio or uncompressed size limits."""
    pass


class NestedArchiveExceededError(ParserSecurityError):
    """Raised when archive nesting exceeds MAX_ARCHIVE_DEPTH."""
    pass


class MalformedXMLError(ParserError):
    """Raised when an XML file cannot be safely or validly parsed."""
    pass


class UnsupportedUFDRFormatError(ParserError):
    """Raised when an evidence package does not match any supported UFDR container schema."""
    pass


class ArtifactExtractionError(ParserError):
    """Raised when a specific artifact record cannot be extracted."""
    pass
