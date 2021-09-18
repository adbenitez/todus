Changelog
=========

`Unreleased`_
-------------

- added ``todus.util.normalize_phone_number()`` utility.
- added ``todus.client.ToDusClient2`` class.
- removed ``todus.util.ResultProcess`` and ``todus.errors.AbortError`` classes.
- avoid incomplete file downloads, check file size match ``Content-Length``.
- ``todus.client.ToDusClient.download_file()`` will now resume partial downloads.
- added logger parameter to ``todus.client.ToDusClient``.
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

0.1.0
-----

- initial release

.. _Unreleased: https://github.com/adbenitez/todus/compare/v0.1.0...HEAD
