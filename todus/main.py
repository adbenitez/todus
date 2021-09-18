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
from .util import get_config, get_logger, normalize_phone_number, save_config


def _split_upload(
    client: ToDusClient2, path: str, part_size: int, max_workers: int
) -> str:
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
        pool = ThreadPoolExecutor(max_workers=max_workers)
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
        default="",
        help="account's phone number, if not given the default account will be used",
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
        "-s",
        "--split",
        dest="part_size",
        type=int,
        default=0,
        help="if given, the file will be split in parts of the given size (in bytes)",
    )
    up_parser.add_argument(
        "-w",
        "--max-workers",
        dest="max_workers",
        type=int,
        default=1,
        help="Number of simultaneous uploads (default: %(default)s)",
    )
    up_parser.add_argument("file", nargs="+", help="file to upload")

    down_parser = subparsers.add_parser(name="download", help="download file")
    down_parser.add_argument(
        "-w",
        "--max-workers",
        dest="max_workers",
        type=int,
        default=4,
        help="Number of simultaneous downloads (default: %(default)s)",
    )
    down_parser.add_argument("url", nargs="+", help="url to download or txt file path")

    return parser


def _register(client: ToDusClient2, acc: dict, config: dict) -> None:
    if not client.phone_number:
        client.phone_number = normalize_phone_number(input("Enter Phone Number: "))
    client.request_code()
    pin = input("Enter PIN: ").strip()
    client.validate_code(pin)
    acc["phone_number"] = client.phone_number
    acc["password"] = client.password
    if acc not in config["accounts"]:
        config["accounts"].append(acc)
    save_config(config)


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
            txt = _split_upload(client, path, args.part_size, args.max_workers)
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

    pool = ThreadPoolExecutor(max_workers=args.max_workers)
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


def _select_account(phone_number: str, config: dict) -> dict:
    if phone_number:
        phone_number = normalize_phone_number(phone_number)
        for acc in config["accounts"]:
            if acc["phone_number"] == phone_number:
                return acc
        return dict(phone_number=phone_number, password="")

    if config["accounts"]:
        acc = config["accounts"][0]
    else:
        acc = dict(phone_number="", password="")
    return acc


def main() -> None:
    """CLI program."""
    try:
        parser = _get_parser()
        args = parser.parse_args()

        config = get_config()
        if args.command == "login":
            acc = dict(phone_number=args.number, password="")
        else:
            acc = _select_account(args.number, config)

        client = ToDusClient2(acc["phone_number"], acc["password"], logger=get_logger())
        if not client.registered and args.command != "login":
            print("ERROR: account not authenticated, login first.")
            return
        if args.command == "upload":
            _upload(client, args)
        elif args.command == "download":
            _download(client, args)
        elif args.command == "login":
            _register(client, acc, config)
        else:
            parser.print_usage()
    except KeyboardInterrupt:
        print("\nOperation canceled by user.")
        os._exit(1)  # noqa
