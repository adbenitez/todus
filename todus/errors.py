class AuthenticationError(Exception):
    """Failed to authenticate with the server."""


class AbortError(Exception):
    """User canceled the operation."""


class EndOfStreamError(Exception):
    """Unexpected empty response from the xmpp server."""
