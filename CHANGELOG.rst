Changelog
=========

`Unreleased`_
-------------

- added ``todus.util.normalize_phone_number()`` utility.
- added ``todus.client.ToDusClient2`` class.
- removed ``todus.util.ResultProcess`` and ``todus.errors.AbortError`` classes.
- avoid incomplete file downloads, check file size match ``Content-Length``.
- ``todus.client.ToDusClient.download_file()`` will now resume partial downloads.
- CLI: now links can be downloaded concurrently.
- CLI: register ``todus`` command, should be available in the shell.
- CLI: added progress bar.
- CLI: fixed bug that prevented from using "login" subcommand.
- CLI: skip already downloaded/uploaded files.
- added logging to ``todus.client`` and make the CLI write logs to ``~/.todus/log.txt`` file.
- renamed ``--part-size`` option to ``--split``.

0.1.0
-----

- initial release

.. _Unreleased: https://github.com/adbenitez/todus/compare/v0.1.0...HEAD
