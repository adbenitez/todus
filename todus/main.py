import argparse
import functools
import os
import time
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from urllib.parse import quote_plus, unquote_plus

import multivolumefile
import py7zr
import tqdm

from . import __version__
from .client import ToDusClient2
from .util import get_logger


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
        path = os.path.abspath(filename + ".txt")
        uploaded_parts = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as txt:
                for line in txt.readlines():
                    line = line.strip()
                    if line:
                        uploaded_parts.append(line.split(maxsplit=1)[1])
            client.logger.debug(
                "Uploads txt found with %s parts already uploaded", len(uploaded_parts)
            )
        parts = sorted(os.listdir(tempdir))
        pool = ThreadPoolExecutor(max_workers=1)
        pbar = tqdm.tqdm(total=len(parts))
        task = functools.partial(
            _upload_task,
            client=client,
            folder=tempdir,
            pbar=pbar,
            uploaded=uploaded_parts,
        )
        client.login()
        with open(path, "a", encoding="utf-8") as txt:
            for url, name in zip(pool.map(task, parts), parts):
                if url:
                    txt.write(f"{url}\t{name}\n")  # TODO: do this in the task
                    uploaded_parts.append(name)
                pbar.refresh()
    return path


def _upload_task(
    name: str, folder: str, uploaded: list, client: ToDusClient2, pbar: tqdm.tqdm
) -> str:
    path = os.path.join(folder, name)
    if name in uploaded:
        tqdm.tqdm.write(f"Skipping: {name}")
        os.remove(path)
        pbar.update(1)
        return ""
    tqdm.tqdm.write(f"Uploading: {name}")
    with open(path, "rb") as file:
        part = file.read()
    while True:
        try:
            url = client.upload_file(part, len(part))
            os.remove(path)
            pbar.update(1)
            return url
        except Exception as err:
            client.logger.exception(err)
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


def _register(client: ToDusClient2, folder: str) -> None:
    client.request_code()
    pin = input("Enter PIN:").strip()
    client.validate_code(pin)
    with open(
        os.path.join(folder, client.phone_number + ".cfg"), "w", encoding="utf-8"
    ) as file:
        file.write("password=" + client.password)


def _get_password(phone: str, folder: str) -> str:
    path = os.path.join(folder, phone + ".cfg")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            return file.read().split("=", maxsplit=1)[-1].strip()
    return ""


def _upload(client: ToDusClient2, args) -> None:
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


def _download(client: ToDusClient2, args) -> None:
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
    client.login()
    for _ in pool.map(
        functools.partial(_download_task, client=client, pbar=pbar), downloads
    ):
        pbar.refresh()


def _download_task(download: tuple, client: ToDusClient2, pbar: tqdm.tqdm) -> None:
    url, name = download
    url_display = url if len(url) < 50 else url[:50] + "..."
    if os.path.exists(name):
        tqdm.tqdm.write(f"Skipping: {name} ({url_display})")
        pbar.update(1)
        return
    tqdm.tqdm.write(f"Downloading: {name} ({url_display})")
    while True:
        try:
            client.download_file(url, name)
            pbar.update(1)
            break
        except Exception as err:
            client.logger.exception(err)
            time.sleep(15)
            client.login()
            tqdm.tqdm.write(f"Retrying: {name} ({url_display})")


def main() -> None:
    """CLI program."""
    parser = _get_parser()
    args = parser.parse_args()
    password = _get_password(args.number, args.folder)
    if not password and args.command != "login":
        print("ERROR: account not authenticated, login first.")
        return
    client = ToDusClient2(args.number, password, logger=get_logger())
    if args.command == "upload":
        _upload(client, args)
    elif args.command == "download":
        _download(client, args)
    elif args.command == "login":
        _register(client, args.folder)
    else:
        parser.print_usage()
