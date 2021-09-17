import argparse
import functools
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus, unquote_plus

import multivolumefile
import py7zr
import tqdm

from . import __version__
from .client import ToDusClient, ToDusClient2

logging.basicConfig(format="%(levelname)s - %(message)s", level=logging.INFO)
logger = logging


def _split_upload(client: ToDusClient2, path: str, part_size: int) -> str:
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
        pool = ThreadPoolExecutor(max_workers=1)
        pbar = tqdm.tqdm(total=len(parts))
        task = functools.partial(_upload_task, client=client, folder=tempdir)
        urls = []
        client.login()
        for url in pool.map(task, parts):
            urls.append(url)
            pbar.update(1)
            pbar.refresh()
    path = os.path.abspath(filename + ".txt")
    with open(path, "w", encoding="utf-8") as txt:
        for down_url, name in zip(urls, parts):
            txt.write(f"{down_url}\t{name}\n")
    return path


def _upload_task(name: str, folder: str, client: ToDusClient2) -> str:
    tqdm.tqdm.write(f"Uploading: {name}")
    with open(os.path.join(folder, name), "rb") as file:
        part = file.read()
    while True:
        try:
            return client.upload_file(part, len(part))
        except Exception as err:
            logger.exception(err)
            time.sleep(15)
            client.login()
            tqdm.tqdm.write(f"Retrying: {name}")


def _get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__name__.split(".", maxsplit=1)[0],
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
    return password


def _get_password(phone: str, folder: str) -> str:
    path = os.path.join(folder, phone + ".cfg")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            return file.read().split("=", maxsplit=1)[-1].strip()
    return ""


def _set_password(phone: str, password: str, folder: str) -> None:
    with open(os.path.join(folder, phone + ".cfg"), "w", encoding="utf-8") as file:
        file.write("password=" + password)


def _upload(password: str, args) -> None:
    client = ToDusClient2(args.number, password)
    for path in args.file:
        if args.part_size:
            tqdm.tqdm.write(f"Splitting: {path}")
            txt = _split_upload(client, path, args.part_size)
            tqdm.tqdm.write(f"TXT: {txt}")
        else:
            tqdm.tqdm.write(f"Uploading: {path}")
            pbar = tqdm.tqdm(total=1)
            with open(path, "rb") as file:
                data = file.read()
            client.login()
            url = client.upload_file(data, len(data))
            pbar.update(1)
            pbar.refresh()
            url += "?name=" + quote_plus(os.path.basename(path))
            tqdm.tqdm.write(f"URL: {url}")


def _download(password: str, args) -> None:
    downloads = []
    for url in args.url:
        if url.startswith("http"):
            url, name = url.split("?name=", maxsplit=1)
            downloads.append((url, unquote_plus(name)))
        else:
            with open(url, encoding="utf-8") as file:
                for line in file.readlines():
                    line = line.strip()
                    if line:
                        url, name = line.split(maxsplit=1)
                        downloads.append((url, name))

    pool = ThreadPoolExecutor(max_workers=4)
    pbar = tqdm.tqdm(total=len(downloads))
    client = ToDusClient2(args.number, password)
    client.login()
    for _ in pool.map(functools.partial(_download_task, client=client), downloads):
        pbar.update(1)
        pbar.refresh()


def _download_task(download: tuple, client: ToDusClient2) -> None:
    url, name = download
    url_display = url if len(url) < 50 else url[:50] + "..."
    tqdm.tqdm.write(f"Downloading: {name} ({url_display})")
    while True:
        try:
            client.download_file(url, name)
            break
        except Exception as err:
            logger.exception(err)
            time.sleep(15)
            client.login()
            tqdm.tqdm.write(f"Retrying: {name} ({url_display})")


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
