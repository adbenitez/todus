class AuthenticationError(Exception):
    """Failed to authenticate with the server."""


class EndOfStreamError(Exception):
    """Unexpected empty response from the xmpp server."""
