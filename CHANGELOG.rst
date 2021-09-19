Changelog
=========

`Unreleased`_
-------------

- ``todus.errors.AuthenticationError`` is now raised when account fails to login, ``todus.errors.TokenExpiredError`` will be raised when token expired.
- CLI: print program usage if no sub-command is provided.
- CLI: if session expired account password is deleted (session is logged out)

`1.1.0`_
--------

- ``py7zr`` is now an optional dependency, ``zipfile`` will be used if ``py7zr`` is not installed.

`1.0.0`_
--------

- added ``todus.util.normalize_phone_number()`` utility.
- added ``todus.client.ToDusClient2`` class.
- removed ``todus.util.ResultProcess`` and ``todus.errors.AbortError`` classes.
- avoid incomplete file downloads, check file size match ``Content-Length``.
- ``todus.client.ToDusClient.download_file()`` will now resume partial downloads.
- added logger parameter to ``todus.client.ToDusClient``.
- updated fake client version.
- CLI: now links can be downloaded concurrently.
- CLI: register ``todus`` command, should be available in the shell.
- CLI: added progress bar.
- CLI: fixed bug that prevented from using "login" subcommand.
- CLI: skip already downloaded/uploaded files.
- CLI: renamed ``--part-size`` option to ``--split``.
- CLI: removed ``--config-folder`` option.
- CLI: save logs in ``~/.todus/``.
- CLI: terminate program gracefully on ``Ctl+C``.
- CLI: improved account management, now logins are saved in ``~/.todus/config.json``.
- CLI: added ``token`` subcommand to get a new token that could be used in other ToDus tools.
- CLI: added ``accounts`` subcomand to list added accounts.

0.1.0
-----

- initial release

.. _Unreleased: https://github.com/adbenitez/todus/compare/v1.1.0...HEAD
.. _1.1.0: https://github.com/adbenitez/todus/compare/v1.0.0...v1.1.0
.. _1.0.0: https://github.com/adbenitez/todus/compare/v0.1.0...v1.0.0
