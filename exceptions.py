class BadRequest(Exception):
    """Catch all for invalid mode, unauthorized bucket, missing file, etc."""
    pass

class TimeoutError(Exception):
    """The extraction process timed out."""
    pass

class ExtractionFailure(Exception):
    """All extraction engines failed to process the file."""
    pass