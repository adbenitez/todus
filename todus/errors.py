"""todus errors."""


class TokenExpiredError(Exception):
    """Failed to authenticate with the XMPP server, token expired."""


class EndOfStreamError(Exception):
    """Unexpected empty response from the XMPP server."""


class AuthenticationError(Exception):
    """Account password is invalid."""
