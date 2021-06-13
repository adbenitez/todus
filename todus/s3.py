import json
import re
import socket
import ssl
from base64 import b64decode, b64encode

from .errors import AuthenticationError
from .util import generate_token


def _get_socket() -> ssl.SSLSocket:
    sock = socket.socket(socket.AF_INET)
    sock.settimeout(15)
    so = ssl.wrap_socket(sock, ssl_version=ssl.PROTOCOL_TLSv1_2)
    so.connect(("im.todus.cu", 1756))
    so.send(b"<stream:stream xmlns='jc' o='im.todus.cu' xmlns:stream='x1' v='1.0'>")
    return so


def _negociate_start(m: str, so: ssl.SSLSocket, authstr: bytes, sid: str) -> bool:
    if m.startswith("<?xml version='1.0'?><stream:stream i='") and m.endswith(
        "xmlns:stream='x1' f='im.todus.cu' xmlns='jc'>"
    ):
        return True

    if (
        m
        == "<stream:features><es xmlns='x2'><e>PLAIN</e><e>X-OAUTH2</e></es><register xmlns='http://jabber.org/features/iq-register'/></stream:features>"
    ):
        so.send(b"<ah xmlns='ah:ns' e='PLAIN'>" + authstr + b"</ah>")
        return True

    if m == "<ok xmlns='x2'/>":
        so.send(b"<stream:stream xmlns='jc' o='im.todus.cu' xmlns:stream='x1' v='1.0'>")
        return True

    if "<stream:features><b1 xmlns='x4'/>" in m:
        so.send("<iq i='{}-1' t='set'><b1 xmlns='x4'></b1></iq>".format(sid).encode())
        return True

    return False


def _parse_token(token: str) -> tuple:
    phone = json.loads(b64decode(token.split(".")[1]).decode())["username"]
    authstr = b64encode((chr(0) + phone + chr(0) + token).encode("utf-8"))
    return phone, authstr


def reserve_url(token: str, filesize: int) -> tuple:
    """Reserve file URL to upload.

    Returns a tuple with upload and download URLs.
    """
    phone, authstr = _parse_token(token)
    sid = generate_token(5)
    so = _get_socket()

    while True:
        m = so.recv().decode()
        if _negociate_start(m, so, authstr, sid):
            continue

        if "t='result' i='{}-1'>".format(sid) in m:
            so.send(b"<en xmlns='x7' u='true' max='300'/>")
            so.send(
                (
                    "<iq i='"
                    + sid
                    + "-3' t='get'><query xmlns='todus:purl' type='0' persistent='false' size='"
                    + str(filesize)
                    + "' room=''></query></iq>"
                ).encode()
            )
            continue

        if m.startswith("<ed u='true' max='300'"):
            so.send(("<p i='" + sid + "-4'></p>").encode())
            continue

        if m.startswith("<iq o='" + phone + "@im.todus.cu"):
            match = re.match(r".*put='(.*)' get='(.*)' stat.*", m)
            up_url = match.group(1).replace("amp;", "")
            down_url = match.group(2)
            return (up_url, down_url)

        if "<not-authorized/>" in m:
            raise AuthenticationError()


def get_real_url(token: str, url: str) -> str:
    """Get authenticated URL."""
    phone, authstr = _parse_token(token)
    sid = generate_token(5)
    so = _get_socket()

    while True:
        m = so.recv().decode()
        if _negociate_start(m, so, authstr, sid):
            continue

        if "t='result' i='{}-1'>".format(sid) in m:
            so.send(
                "<iq i='{}-2' t='get'><query xmlns='todus:gurl' url='{}'></query></iq>".format(
                    sid, url
                ).encode(),
            )
            continue

        if "t='result' i='{}-2'>".format(sid) in m and "status='200'" in m:
            return re.match(".*du='(.*)' stat.*", m).group(1).replace("amp;", "")

        if "<not-authorized/>" in m:
            raise AuthenticationError()
