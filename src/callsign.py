# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Callsign, flag, picture and radio ID lookups, and the program version check.

Pictures are handled as file paths only: this module finds and downloads
them, and whoever shows them decides how to load and draw them.
"""

import functools

# File extensions accepted for the local callsign pictures, in search order.
CALLSIGN_PICTURE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


@functools.lru_cache(maxsize=1)
def _prefix_table():
    """Callsign prefix table (data/prefix.json), read once."""
    with open(resource_path(os.path.join("data", "prefix.json")), encoding="utf-8") as table:
        return json.load(table)


def prefix_info(_callsign):
    """{"country", "flag"} of the longest known prefix of a callsign, or {}.

    Prefixes of four, three, two and one characters are tried in that order,
    so "KH6ABC" finds Hawaii before the plain "K" of the United States.
    """
    call = str(_callsign).upper()
    table = _prefix_table()
    for length in (4, 3, 2, 1):
        entry = table.get(call[:length])
        if entry:
            return entry
    return {}


def flag_picture_path(flag_code):
    """Path of the flag picture flags/<flag_code>.png, or None when there is no such flag."""
    if len(str(flag_code or "")) > 0:
        file = resource_path(os.path.join("flags", str(flag_code) + ".png"))
        if os.path.isfile(file):
            return file
    return None


def images_dir():
    """Folder holding the local callsign pictures (created when missing)."""
    return ensure_dir(app_path("images"))


def picture_file_stem(_callsign):
    """File name (without extension) of a callsign picture; "/" becomes "_"."""
    return clean_callsign(_callsign).replace("/", "_")


def local_picture_path(_callsign):
    """Path of the local picture of a callsign in images, or None when there is none."""
    stem = picture_file_stem(_callsign)
    if stem:
        base = os.path.join(images_dir(), stem)
        for extension in CALLSIGN_PICTURE_EXTENSIONS:
            if os.path.isfile(base + extension):
                return base + extension
    return None


def publish_station_identity(_callsign):
    """Publish the id, name and address of a callsign, looking it up when needed."""
    if _callsign in radioid_cache:
        emit_event(
            "station_identity",
            identity=radioid_cache[_callsign]["id"],
            name=radioid_cache[_callsign]["full_name"],
            location=radioid_cache[_callsign]["location"],
        )
    else:
        start_worker(lookup_radioid, _callsign, name="radioid-lookup")


def lookup_station(_callsign, name):
    """Publish the picture and identity of a station that just started talking.

    The local picture is shown right away. Without one, the person icon is
    shown first and replaced when QRZ.com returns a picture; it stays when
    the station has no picture on QRZ.com.
    """
    if not _callsign or _callsign == "NOCALL":
        return
    picture = local_picture_path(_callsign)
    if picture:
        emit_event("station_photo", callsign=_callsign, picture=picture, name=name)
    else:
        emit_event("station_photo", callsign=_callsign, picture=person_icon_path(), name=name)
        picture = download_qrz_picture(_callsign)
        if picture:
            emit_event("station_photo", callsign=_callsign, picture=picture, name=name)
    publish_station_identity(_callsign)


def is_qrz_placeholder_picture(image_url):
    """True when an address points to the stock artwork QRZ.com shows instead of a photo.

    Members who never uploaded a picture still get an image on their QRZ.com
    page: the site logo, served from the QRZ.com "static" folder. That image
    says nothing about the station, so it is treated as "no picture" and the
    person icon is shown instead.
    """
    parts = urllib.parse.urlparse(str(image_url or ""))
    # QRZ.com files may be served from its own host or from a storage host
    # that keeps "files.qrz.com" in the path, so both are checked together.
    address = (parts.netloc + parts.path).lower()
    file_name = parts.path.lower().rsplit("/", 1)[-1]
    return "qrz.com" in address and ("/static/" in address or file_name.startswith("qrz_com"))


def qrz_picture_url(_callsign):
    """Address of the QRZ.com picture of a callsign, or "" when there is none.

    The QRZ.com XML service is used when an account is configured; otherwise
    the public QRZ.com page is read. The stock artwork QRZ.com shows for
    members without a photo counts as no picture. Answers are remembered, and
    a failed lookup is retried only after PICTURE_RETRY_SECONDS.
    """
    _callsign = clean_callsign(_callsign)
    cached = qrz_cache.get(_callsign)
    if cached is not None and (cached.get("url") or monotonic() - cached.get("checked", 0) < PICTURE_RETRY_SECONDS):
        return cached.get("url", "")

    img = qrz_xml_picture_url(_callsign)
    if img is None:
        img = ""
        try:
            page_url = "https://www.qrz.com/db/" + urllib.parse.quote(_callsign, safe="/")
            page = http_session.get(page_url, headers=http_headers(), timeout=20)
            if page.status_code == 200:
                picture = BeautifulSoup(page.text, "html.parser").find(id="mypic")
                if picture is not None and picture.get("src"):
                    img = urllib.parse.urljoin(page_url, picture["src"])
        except requests.exceptions.RequestException as exc:
            log.debug("QRZ.com page of %s not available: %s", _callsign, exc)
    if is_qrz_placeholder_picture(img):
        img = ""
    qrz_cache[_callsign] = {"url": img, "checked": monotonic()}
    return img


def lookup_dmr_ids(station_call):
    """Look up the DMR ids of a callsign on radioid.net and publish them as "dmr_ids".

    The ids found are published (an empty list when there are none), or None
    when no callsign was given. When the service does not answer, a
    "warning" event is published instead and the typed id stays as it is.
    """
    station_call = clean_callsign(station_call)
    if not station_call:
        emit_event("dmr_ids", ids=None)
        return
    dmrids = []
    try:
        resp = http_session.get(
            "https://radioid.net/api/dmr/user/",
            params={"callsign": station_call},
            headers=http_headers(),
            timeout=HTTP_TIMEOUT,
        )
        # radioid.net may answer "404 Not Found" for a callsign it does not know.
        if resp.status_code != 404:
            resp.raise_for_status()
            data = resp.json()
            if int(data.get("count") or 0) > 0:
                for item in data.get("results") or []:
                    if isinstance(item, dict) and item.get("id"):
                        dmrids.append(str(item["id"]))
    except (requests.exceptions.RequestException, ValueError, TypeError, AttributeError) as exc:
        log.warning("radioid.net lookup failed: %s", exc)
        emit_event("warning", title=tr("app.title"), message=tr("settings.dmr_lookup_failed"))
        return
    emit_event("dmr_ids", ids=dmrids)


def query_dmr_ids(station_call):
    """Look up the DMR ids of a callsign in the background."""
    start_worker(lookup_dmr_ids, station_call, name="dmrid-lookup")


def parse_version(text):
    """Turn a version string like "1.10" into a tuple of ints, e.g. (1, 10).

    Tuples compare number by number, so (1, 10) > (1, 9) as a human expects.
    Comparing the raw strings would say "1.9" > "1.10", which is wrong.
    Returns None when the text is not a plain dotted number.
    """
    try:
        return tuple(int(part) for part in str(text).strip().split("."))
    except ValueError:
        return None


def check_for_update():
    """Announce (with an "info" event) when a newer program version is published.

    The address of the plain-text version file is the update version_url
    setting (edited by hand in database/settings.json, see README.md). It is
    compared with the program version (APP_DISPLAY_VERSION), not with the
    protocol version sent to the Peanut server. When it is empty (the
    default) no check is made. The certificate is always verified, like for
    every other HTTPS site.
    """
    url = str(config.get("update", "version_url", fallback="") or "").strip()
    if not url:
        return
    try:
        resp = http_session.get(url, headers=http_headers(), timeout=HTTP_TIMEOUT)
        if resp.status_code == 200:
            published_text = resp.content.decode("utf-8").strip()
            published_version = parse_version(published_text)
            own_version = parse_version(APP_DISPLAY_VERSION)
            # Only announce an update when both versions could be read
            # and the server one is really newer.
            if published_version and own_version and published_version > own_version:
                emit_event("info", title="Info", message=tr("update.available").format(published_text))
    except requests.exceptions.SSLError as e_ssl:
        # The server certificate could not be trusted (expired, wrong name...).
        # The check is skipped instead of bypassing the security test.
        log.warning("Skipping the version check, the update server certificate is not valid: %s", e_ssl)
    except requests.exceptions.RequestException as e_req:
        log.info("The latest version could not be checked: %s", e_req)
    except ValueError as e_text:
        # The file is not plain text (UnicodeDecodeError is a ValueError).
        log.info("The version file is not readable text: %s", e_text)


def radioid_first_name(lookup_call):
    """First name of a callsign from the RadioID list, or the "unknown" text."""
    if lookup_call in radioid_cache:
        return radioid_cache[lookup_call]["name"]
    return tr("station.unknown")
