import argparse
import logging
import os
import time
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus, unquote_plus

import multivolumefile
import py7zr  # type: ignore

from . import __version__
from .client import ToDusClient

logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.INFO)


def _split_upload(phone: str, password: str, path: str, part_size: int) -> str:
    with open(path, "rb") as file:
        data = file.read()
    filename = os.path.basename(path)
    with TemporaryDirectory() as tempdir:
        with multivolumefile.open(
            os.path.join(tempdir, filename + ".7z"),
            "wb",
            volume=part_size,
        ) as vol:
            with py7zr.SevenZipFile(vol, "w") as archive:
                archive.writestr(data, filename)
        del data
        parts = sorted(os.listdir(tempdir))
        parts_count = len(parts)
        urls = []
        client = ToDusClient()
        for i, name in enumerate(parts, 1):
            logging.info("Uploading %s/%s: %s", i, parts_count, filename)
            with open(os.path.join(tempdir, name), "rb") as file:
                part = file.read()
            try:
                token = client.login(phone, password)
                urls.append(client.upload_file(token, part, len(part)))
            except Exception as ex:
                logging.exception(ex)
                time.sleep(15)
                try:
                    token = client.login(phone, password)
                    urls.append(client.upload_file(token, part, len(part)))
                except Exception as ex:
                    logging.exception(ex)
                    raise ValueError(
                        f"Failed to upload part {i} ({len(part):,}B): {ex}"
                    ) from ex
        text = "\n".join(f"{down_url}\t{name}" for down_url, name in zip(urls, parts))
        path = os.path.abspath(filename + ".txt")
        with open(path, "w") as txt:
            txt.write(text)
        return path


def _get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__name__.split(".")[0],
        description="ToDus Client",
    )
    parser.add_argument(
        "-n",
        "--number",
        dest="number",
        metavar="PHONE-NUMBER",
        help="account's phone number",
        required=True,
    )
    parser.add_argument(
        "-c",
        "--config-folder",
        dest="folder",
        type=str,
        default="",
        help="folder where account configuration will be saved/loaded",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
        help="show program's version number and exit.",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(name="login", help="authenticate in server")

    up_parser = subparsers.add_parser(name="upload", help="upload file")
    up_parser.add_argument(
        "-p",
        "--part-size",
        dest="part_size",
        type=int,
        default=0,
        help="if given, the file will be split in parts of the given size in bytes",
    )
    up_parser.add_argument("file", nargs="+", help="file to upload")

    down_parser = subparsers.add_parser(name="download", help="download file")
    down_parser.add_argument("url", nargs="+", help="url to download or txt file path")

    return parser


def _register(client: ToDusClient, phone: str) -> str:
    client.request_code(phone)
    pin = input("Enter PIN:").strip()
    password = client.validate_code(phone, pin)
    logging.debug("PASSWORD: %s", password)
    return password


def _get_password(phone: str, folder: str) -> str:
    path = os.path.join(folder, phone + ".cfg")
    if os.path.exists(path):
        with open(path) as file:
            return file.read().split("=", maxsplit=1)[-1].strip()
    return ""


def _set_password(phone: str, password: str, folder: str) -> None:
    with open(os.path.join(folder, phone + ".cfg"), "w") as file:
        file.write("password=" + password)


def _upload(password: str, args) -> None:
    client = ToDusClient()
    for path in args.file:
        logging.info("Uploading: %s", path)
        if args.part_size:
            txt = _split_upload(args.number, password, path, args.part_size)
            logging.info("TXT: %s", txt)
        else:
            with open(path, "rb") as file:
                data = file.read()
            token = client.login(args.number, password)
            logging.debug("Token: '%s'", token)
            url = client.upload_file(token, data, len(data))
            url += "?name=" + quote_plus(os.path.basename(path))
            logging.info("URL: %s", url)


def _download(password: str, args) -> None:
    client = ToDusClient()
    token = client.login(args.number, password)
    logging.debug("Token: '%s'", token)
    while args.url:
        url = args.url.pop(0)
        if os.path.exists(url):
            with open(url) as file:
                urls = []
                for line in file.readlines():
                    line = line.strip()
                    if line:
                        url, name = line.split(maxsplit=1)
                        urls.append(f"{url}?name={name}")
                args.url = urls + args.url
                continue
        logging.info("Downloading: %s", url)
        url, name = url.split("?name=", maxsplit=1)
        name = unquote_plus(name)
        try:
            size = client.download_file(token, url, name)
        except Exception:
            token = client.login(args.number, password)
            size = client.download_file(token, url, name)
        logging.debug("File Size: %s", size // 1024)


def main() -> None:
    """CLI program."""
    parser = _get_parser()
    args = parser.parse_args()
    password = _get_password(args.number, args.folder)
    if not password and args.command != "loging":
        print("ERROR: account not authenticated, login first.")
        return
    if args.command == "upload":
        _upload(password, args)
    elif args.command == "download":
        _download(password, args)
    elif args.command == "login":
        client = ToDusClient()
        _set_password(args.number, _register(client, args.number), args.folder)
    else:
        parser.print_usage()
