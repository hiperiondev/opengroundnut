# SPDX-License-Identifier: WTFPL
#
# This program is free software. It comes without any warranty, to the
# extent permitted by applicable law. You can redistribute it and/or modify
# it under the terms of the Do What The Fuck You Want To Public License,
# Version 2, as published by Sam Hocevar. See LICENSE.md for more details.

"""Persistent data (TinyDB), logbook, bookmarks, RadioID user list, ADIF export,
logbook uploads (eQSL.cc, QRZ.com) and QRZ.com pictures.

Every piece of data the program keeps lives in the database folder, in
TinyDB files (plain JSON, readable with any text editor):

    database/settings.json   the settings (see settings.py)
    database/logbook.json    the logbook ("log" table) and the room bookmarks
                             ("bookmarks" table)
    database/radioid/        the RadioID user list, split into small files
                             so a lookup only reads one of them

Logbook dates are written, shown and stored as yyyy-mm-dd (ISO 8601, UTC),
so they sort correctly and read the same in every country.
"""

# Version of the layout of logbook.json. Stored in its "meta" table so a
# future version knows which conversions an older file needs.
LOGBOOK_SCHEMA_VERSION = 2

# Version of the layout of the RadioID files. A different number in the
# stored index means the list has to be built again.
RADIOID_SCHEMA_VERSION = 1

# The RadioID list is split into this many TinyDB files, chosen by a hash of
# the callsign. About 300,000 stations end up as files of roughly 150 KB, so
# a lookup reads and parses one small file instead of the whole list.
RADIOID_BUCKETS = 256

# While the list is built, this many files are filled per pass over the
# downloaded data. Fewer files per pass means less memory and more passes.
RADIOID_BUCKETS_PER_PASS = 32

# Every TinyDB file keeps its bookkeeping in one document of this table.
META_TABLE = "meta"
META_DOC_ID = 1

# Date format of the logbook (ISO 8601), both on screen and in the database.
DATE_FORMAT = "%Y-%m-%d"

# Band names of the ADIF specification (the "Band" enumeration).
ADIF_BANDS = (
    "2190m", "630m", "560m", "160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m",
    "8m", "6m", "5m", "4m", "2m", "1.25m", "70cm", "33cm", "23cm", "13cm", "9cm", "6cm", "3cm",
    "1.25cm", "6mm", "4mm", "2.5mm", "2mm", "1mm",
)

# How long a failed QRZ.com picture lookup is remembered before trying again.
PICTURE_RETRY_SECONDS = 3600

# Errors raised when a TinyDB file holds something that is not valid JSON
# (ValueError, which includes UnicodeDecodeError) or valid JSON with the
# wrong shape (TypeError, AttributeError).
UNREADABLE_DATA_ERRORS = (ValueError, TypeError, AttributeError)

# TinyDB is not thread-safe, and the logbook and settings are used from the
# interface and from background workers (uploads, lookups). Every access to
# those two files goes through this lock.
_db_lock = threading.RLock()

# The open logbook (a TinyDB instance), set by open_logbook().
_logbook_db = None


def _read_umask():
    """The file creation mask of this process (0 where there is none, such as Windows)."""
    if os.name != "posix":
        return 0
    mask = os.umask(0)
    os.umask(mask)
    return mask


# Read once at start-up: changing the mask is not thread-safe, so it is
# never touched again while the program runs.
_FILE_UMASK = _read_umask()


# ---------------------------------------------------------------------------
# TinyDB storage
# ---------------------------------------------------------------------------

class SafeJSONStorage(TinyStorage):
    """TinyDB storage that never leaves a half-written file behind.

    TinyDB's own JSON storage rewrites the file in place, so a crash or a
    full disk in the middle of a write can destroy it. This storage writes
    the new content to a temporary file in the same folder and then puts it
    in place of the old one in a single step.

    Reading a missing or empty file returns None, which TinyDB treats as an
    empty database; the file is only created by the first write.

    private=True makes the file readable by its owner only on Linux and
    macOS (used for the settings, which hold passwords). Every other file
    gets the usual permissions of new files (normally readable by everyone,
    writable by its owner). indent=None writes compact JSON (used for the
    large RadioID files).
    """

    def __init__(self, path, private=False, indent=2):
        super().__init__()
        self.path = path
        self.private = private
        self.indent = indent

    def read(self):
        try:
            with open(self.path, encoding="utf-8") as data_file:
                text = data_file.read()
        except FileNotFoundError:
            return None
        if not text.strip():
            return None
        return json.loads(text)

    def write(self, data):
        folder = os.path.dirname(os.path.abspath(self.path))
        ensure_dir(folder)
        handle, temp_name = tempfile.mkstemp(prefix=".tinydb-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as data_file:
                json.dump(data, data_file, ensure_ascii=False, indent=self.indent)
                data_file.flush()
                os.fsync(data_file.fileno())
            if os.name == "posix":
                # The temporary file starts as owner-only; give it the
                # permissions the final file should have.
                os.chmod(temp_name, 0o600 if self.private else 0o666 & ~_FILE_UMASK)
            os.replace(temp_name, self.path)
        except BaseException:
            try:
                os.remove(temp_name)
            except OSError:
                pass
            raise

    def close(self):
        # Nothing stays open between reads and writes.
        pass


def open_tinydb(file_path, private=False, indent=2):
    """Open a TinyDB file with the safe storage. The file is created on the first write."""
    return TinyDB(file_path, storage=SafeJSONStorage, private=private, indent=indent)


def set_aside_unreadable_file(file_path):
    """Move a file that cannot be read to <file>.bak and return the backup name.

    The program then starts with an empty file, and the damaged one is kept
    so its content can still be rescued by hand.
    """
    backup = file_path + ".bak"
    try:
        os.replace(file_path, backup)
    except OSError as exc:
        log.error("%s cannot be moved to %s: %s", file_path, backup, exc)
    return backup


def _remove_quietly(file_path):
    try:
        os.remove(file_path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Logbook file
# ---------------------------------------------------------------------------

def logbook_path():
    """Location of the logbook TinyDB file, in the database folder of the user data folder."""
    return os.path.join(database_dir(), "logbook.json")


def _log_table():
    return _logbook_db.table("log")


def _bookmarks_table():
    return _logbook_db.table("bookmarks")


def open_logbook():
    """Open the logbook (creating the database folder when missing).

    A logbook file that cannot be read is kept as logbook.json.bak and a
    new, empty one is started; the problem is reported in config_warnings.
    """
    global _logbook_db
    ensure_dir(database_dir())
    with _db_lock:
        _logbook_db = open_tinydb(logbook_path())
        try:
            meta = _logbook_db.table(META_TABLE).get(doc_id=META_DOC_ID)
        except UNREADABLE_DATA_ERRORS as exc:
            log.error("%s cannot be read (%s); an empty logbook is used.", logbook_path(), exc)
            backup = set_aside_unreadable_file(logbook_path())
            config_warnings.append(("storage.file_unreadable", (logbook_path(), backup)))
            _logbook_db = open_tinydb(logbook_path())
            meta = None
        if meta is None:
            _logbook_db.table(META_TABLE).upsert(
                TinyDocument({"schema_version": LOGBOOK_SCHEMA_VERSION}, doc_id=META_DOC_ID)
            )


def _clean_date(text):
    """A logbook date as yyyy-mm-dd with leading zeros; a text that is not a date is kept unchanged."""
    text = str(text or "").strip()
    try:
        return datetime.strptime(text, DATE_FORMAT).strftime(DATE_FORMAT)
    except ValueError:
        return text


# ---------------------------------------------------------------------------
# Bookmarks (favorite rooms, per server)
# ---------------------------------------------------------------------------

# Bookmarked rooms of one server, kept in memory: {"server": address,
# "rooms": {room: record id}}. TinyDB reads the whole logbook file on every
# query, and the Monitor tab asks whether a room is bookmarked many times a
# second, so the bookmarks are read from the file only when the server
# changes or a bookmark is added or removed.
_bookmark_cache = {"server": None, "rooms": {}}


def _bookmark_query(room_name):
    bookmark = TinyQuery()
    return (bookmark.room == str(room_name).strip()) & (bookmark.server == str(master_host).strip())


def _bookmarks_of_current_server():
    """{room: record id} of the bookmarks of the current server, from memory when possible."""
    server = str(master_host).strip()
    with _db_lock:
        if _bookmark_cache["server"] != server:
            found = _bookmarks_table().search(TinyQuery().server == server)
            _bookmark_cache["rooms"] = {str(doc.get("room", "")): doc.doc_id for doc in found}
            _bookmark_cache["server"] = server
        return dict(_bookmark_cache["rooms"])


def _forget_bookmarks():
    """Read the bookmarks from the file again on the next question."""
    with _db_lock:
        _bookmark_cache["server"] = None


def bookmarked_rooms():
    """Bookmarked rooms of the current server as (room, id) rows, sorted by room."""
    return sorted(_bookmarks_of_current_server().items(), key=lambda row: row[0])


def add_bookmark(room_name):
    """Bookmark a room on the current server (once)."""
    with _db_lock:
        if not find_bookmark(room_name):
            _bookmarks_table().insert({"room": str(room_name).strip(), "server": str(master_host).strip()})
            _forget_bookmarks()


def remove_bookmark(room_name):
    """Remove a room from the bookmarks of the current server."""
    with _db_lock:
        _bookmarks_table().remove(_bookmark_query(room_name))
        _forget_bookmarks()


def find_bookmark(room_name):
    """The (room, id) row of a bookmark, or an empty list when the room is not bookmarked."""
    room = str(room_name).strip()
    record_id = _bookmarks_of_current_server().get(room)
    return (room, record_id) if record_id is not None else []


# ---------------------------------------------------------------------------
# Logbook records
# ---------------------------------------------------------------------------

def _sorted_records(documents):
    """Logbook documents ordered by record number, oldest first."""
    return sorted(documents, key=lambda doc: doc.doc_id)


def _field(doc, name):
    """A text field of a logbook document ("" when it is missing or empty)."""
    value = doc.get(name)
    return "" if value is None else value


def logbook_rows():
    """Every logbook record as (callsign, name, date, time, band, comment, id), oldest first."""
    with _db_lock:
        documents = _sorted_records(_log_table().all())
    return [
        (
            _field(doc, "callsign"), _field(doc, "name"), _field(doc, "date"),
            _field(doc, "time"), _field(doc, "band"), _field(doc, "comment"), doc.doc_id,
        )
        for doc in documents
    ]


def _record_tuple(doc):
    """(callsign, name, date, time, band, frequency, comment) of a document."""
    return (
        _field(doc, "callsign"), _field(doc, "name"), _field(doc, "date"),
        _field(doc, "time"), _field(doc, "band"), _field(doc, "frequency"), _field(doc, "comment"),
    )


def logbook_last_record():
    """(band, frequency, comment) of the newest logbook record, or None."""
    with _db_lock:
        documents = _log_table().all()
    if not documents:
        return None
    newest = max(documents, key=lambda doc: doc.doc_id)
    return (_field(newest, "band"), _field(newest, "frequency"), _field(newest, "comment"))


def logbook_get_record(record_id):
    """(callsign, name, date, time, band, frequency, comment) of one record, or None."""
    try:
        record_id = int(record_id)
    except (TypeError, ValueError):
        return None
    with _db_lock:
        doc = _log_table().get(doc_id=record_id)
    return _record_tuple(doc) if doc is not None else None


def logbook_find_by_call(call_sign):
    """First record logged with this callsign, or None.

    The row is (callsign, name, date, time, band, frequency, comment, id).
    """
    with _db_lock:
        found = _sorted_records(_log_table().search(TinyQuery().callsign == call_sign))
    if not found:
        return None
    return _record_tuple(found[0]) + (found[0].doc_id,)


def logbook_save_record(record, record_id=None):
    """Insert a new record, or update record_id when it is given.

    record is a dictionary with the keys callsign, name, date (yyyy-mm-dd),
    time, band, comment and frequency. An edited record is marked as not
    uploaded, so the corrected contact is sent again.
    """
    document = {
        "callsign": str(record.get("callsign", "")),
        "name": str(record.get("name", "")),
        "date": _clean_date(record.get("date", "")),
        "time": str(record.get("time", "")),
        "band": str(record.get("band", "")),
        "comment": str(record.get("comment", "")),
        "frequency": str(record.get("frequency", "")),
        "uploaded_qrz": False,
        "uploaded_eqsl": False,
    }
    with _db_lock:
        table = _log_table()
        if record_id is not None and table.contains(doc_id=int(record_id)):
            table.update(document, doc_ids=[int(record_id)])
        else:
            # A new record, or one deleted while it was being edited.
            table.insert(document)


def delete_record(record):
    """Delete one logbook record by id."""
    with _db_lock:
        table = _log_table()
        if table.contains(doc_id=int(record)):
            table.remove(doc_ids=[int(record)])


def delete_all_records():
    """Delete every logbook record."""
    with _db_lock:
        _log_table().truncate()


def _logbook_records(pending_for=None):
    """Logbook records as dictionaries, oldest first.

    pending_for="qrz" or "eqsl" returns only the records not yet uploaded
    to that service.
    """
    with _db_lock:
        documents = _log_table().all()
    if pending_for in ("qrz", "eqsl"):
        flag = "uploaded_" + pending_for
        documents = [doc for doc in documents if not doc.get(flag)]
    keys = ("callsign", "name", "date", "time", "band", "frequency", "comment")
    return [dict({"id": doc.doc_id}, **{key: _field(doc, key) for key in keys}) for doc in _sorted_records(documents)]


def count_pending_uploads(service):
    """Number of logbook records not yet uploaded to "qrz" or "eqsl"."""
    return len(_logbook_records(pending_for=service))


def _mark_uploaded(service, record_ids):
    """Remember that these records were uploaded to "qrz" or "eqsl"."""
    flag = {"qrz": "uploaded_qrz", "eqsl": "uploaded_eqsl"}[service]
    with _db_lock:
        table = _log_table()
        # A record deleted while the upload was running is simply skipped.
        existing = [record_id for record_id in record_ids if table.contains(doc_id=record_id)]
        if existing:
            table.update({flag: True}, doc_ids=existing)


# ---------------------------------------------------------------------------
# RadioID user list
# ---------------------------------------------------------------------------

# Held while the RadioID files are built or swapped, so two builds never
# run at the same time.
_radioid_index_lock = threading.Lock()


def radioid_index_dir():
    """Folder holding the RadioID TinyDB files."""
    return os.path.join(database_dir(), "radioid")


def _radioid_meta_path(folder=None):
    return os.path.join(folder or radioid_index_dir(), "index.json")


def _radioid_bucket(_callsign):
    """Number of the RadioID file that holds a callsign."""
    return zlib.crc32(_callsign.encode("utf-8")) % RADIOID_BUCKETS


def _radioid_bucket_path(bucket, folder=None):
    return os.path.join(folder or radioid_index_dir(), "users-{:02x}.json".format(bucket))


def radioid_index_info():
    """The bookkeeping document of the RadioID files, or None when the list is not usable."""
    meta_path = _radioid_meta_path()
    if not exists(meta_path):
        return None
    try:
        with open_tinydb(meta_path) as db:
            meta = db.table(META_TABLE).get(doc_id=META_DOC_ID)
    except UNREADABLE_DATA_ERRORS + (OSError,) as exc:
        log.warning("The RadioID index cannot be read: %s", exc)
        return None
    if not meta or meta.get("schema_version") != RADIOID_SCHEMA_VERSION or meta.get("buckets") != RADIOID_BUCKETS:
        return None
    return meta


def radioid_index_ready():
    """True when the RadioID list is stored and can be searched."""
    return radioid_index_info() is not None


def _radioid_csv_rows(csv_path):
    """Rows of a RadioID CSV file as (id, callsign, first, last, city, state, country)."""
    with open(csv_path, encoding="utf-8", errors="replace", newline="") as csv_file:
        reader = csv.reader(csv_file)
        next(reader, None)
        for row in reader:
            if len(row) >= 7 and row[1].strip():
                yield row[:7]


def build_radioid_index(rows_factory, source_name):
    """Store the RadioID list in TinyDB files and put them in place of the old ones.

    rows_factory() must return a fresh iterator of rows (id, callsign, first,
    last, city, state, country) every time it is called, because the data is
    read once per pass. Only the first row of each callsign is kept (it is the
    one the lookups always used). The new files are written to a temporary
    folder first, so the list in use is never left half-built. Returns the
    number of stations stored.
    """
    with _radioid_index_lock:
        final_dir = radioid_index_dir()
        temp_dir = final_dir + ".part"
        old_dir = final_dir + ".old"
        shutil.rmtree(temp_dir, ignore_errors=True)
        ensure_dir(temp_dir)
        stations = 0
        try:
            for first_bucket in range(0, RADIOID_BUCKETS, RADIOID_BUCKETS_PER_PASS):
                buckets = range(first_bucket, min(first_bucket + RADIOID_BUCKETS_PER_PASS, RADIOID_BUCKETS))
                users = {bucket: {} for bucket in buckets}
                for row in rows_factory():
                    call = row[1].strip().upper()
                    bucket_users = users.get(_radioid_bucket(call))
                    if bucket_users is None or call in bucket_users:
                        continue
                    bucket_users[call] = {
                        "callsign": call,
                        "id": row[0].strip(),
                        "first": row[2].strip(),
                        "last": row[3].strip(),
                        "city": row[4].strip(),
                        "state": row[5].strip(),
                        "country": row[6].strip(),
                    }
                for bucket, bucket_users in users.items():
                    with open_tinydb(_radioid_bucket_path(bucket, temp_dir), indent=None) as db:
                        db.table("users").insert_multiple(bucket_users.values())
                    stations += len(bucket_users)
            with open_tinydb(_radioid_meta_path(temp_dir)) as db:
                db.table(META_TABLE).insert(
                    TinyDocument(
                        {
                            "schema_version": RADIOID_SCHEMA_VERSION,
                            "buckets": RADIOID_BUCKETS,
                            "stations": stations,
                            "source": source_name,
                            "built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                        },
                        doc_id=META_DOC_ID,
                    )
                )
        except BaseException:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        # Swap the folders: the old list is moved away first, so the new one
        # can take its name, and is deleted once the new one is in place.
        shutil.rmtree(old_dir, ignore_errors=True)
        if exists(final_dir):
            os.replace(final_dir, old_dir)
        os.replace(temp_dir, final_dir)
        shutil.rmtree(old_dir, ignore_errors=True)
    log.info("RadioID list stored: %d stations", stations)
    return stations


def radioid_find(_callsign):
    """The stored RadioID entry of a callsign as a dictionary, or None.

    The dictionary has the keys id, first, last, city, state and country.
    """
    _callsign = str(_callsign or "").strip().upper()
    if not _callsign or not radioid_index_ready():
        return None
    bucket_path = _radioid_bucket_path(_radioid_bucket(_callsign))
    if not exists(bucket_path):
        return None
    with open_tinydb(bucket_path, indent=None) as db:
        return db.table("users").get(TinyQuery().callsign == _callsign)


# ---------------------------------------------------------------------------
# ADIF
# ---------------------------------------------------------------------------

def adif_field(name, value):
    """One ADIF field, "<NAME:length>value", or "" when the value is empty.

    ADIF files are plain ASCII, so accents are removed first; the length is
    then the exact number of bytes written.
    """
    text = ascii_text(value).strip()
    return "<{}:{}>{}".format(name, len(text), text) if text else ""


def adif_header():
    """ADIF header naming the program, ended by <EOH>."""
    created = datetime.now(timezone.utc).strftime("%Y%m%d %H%M%S")
    return "Logbook exported by {} {}\n{} {} {} {} <EOH>\n".format(
        APP_NAME,
        APP_DISPLAY_VERSION,
        adif_field("ADIF_VER", "3.1.4"),
        adif_field("PROGRAMID", APP_NAME),
        adif_field("PROGRAMVERSION", APP_DISPLAY_VERSION),
        adif_field("CREATED_TIMESTAMP", created),
    )


def adif_record(record, comment_tag="COMMENT", extra_fields=""):
    """One QSO as an ADIF record, ended by <EOR>.

    STATION_CALLSIGN is the callsign configured in the program. Signal
    reports are not logged by the program, so the usual 59 is exported.
    """
    qso_date = _clean_date(record["date"]).replace("-", "")
    parts = [
        adif_field("STATION_CALLSIGN", callsign),
        adif_field("CALL", record["callsign"]),
        adif_field("NAME", record["name"]),
        adif_field("QSO_DATE", qso_date),
        adif_field("TIME_ON", str(record["time"]).replace(":", "")),
        adif_field("BAND", str(record["band"]).lower()),
        adif_field("FREQ", record["frequency"]),
        adif_field("MODE", "DIGITALVOICE"),
        adif_field("RST_RCVD", "59"),
        adif_field("RST_SENT", "59"),
        adif_field(comment_tag, record["comment"]),
        extra_fields,
    ]
    return "".join(part for part in parts if part) + "<EOR>\n"


def export_adif_text():
    """The whole logbook as an ADIF document (header and every record)."""
    return adif_header() + "".join(adif_record(record) for record in _logbook_records())


# ---------------------------------------------------------------------------
# eQSL.cc upload
# ---------------------------------------------------------------------------

def upload_to_eqsl(user, password, qth=""):
    """Upload the contacts not yet sent to eQSL.cc, in the background.

    The answer of eQSL.cc is published as an "eqsl_reply" event.
    """
    start_worker(_eqsl_upload_worker, str(user), str(password), str(qth or ""), name="eqsl-upload")


def _eqsl_upload_worker(user, password, qth):
    records = _logbook_records(pending_for="eqsl")
    if not records:
        emit_event("eqsl_reply", text=tr("logbook.nothing_to_upload"))
        return
    nickname = adif_field("APP_EQSL_QTH_NICKNAME", qth) if qth else ""
    document = adif_header() + "".join(adif_record(record, "QSLMSG", nickname) for record in records)
    try:
        answer = post_eqsl_adif(user, password, document)
    except requests.exceptions.RequestException as exc:
        log.warning("eQSL upload failed: %s", exc)
        emit_event("eqsl_reply", text=tr("logbook.eqsl_unreachable") + "\n\n" + str(exc))
        return
    if eqsl_upload_complete(answer, len(records)):
        _mark_uploaded("eqsl", [record["id"] for record in records])
    emit_event("eqsl_reply", text=answer)


def eqsl_upload_complete(answer, sent):
    """True when eQSL.cc took every one of the `sent` records.

    eQSL answers "Result: N out of M records added" and writes one warning
    line for every record it did not add. A record it already had (a
    warning line that says "Duplicate") counts as delivered. When any record
    was refused for another reason, nothing is marked as uploaded, so every
    contact is offered again once the problem is corrected; eQSL ignores the
    ones it already has.

    Only warning lines are counted, so the word "duplicate" in any other
    part of the page (help texts, notes) never counts as a delivered record.
    """
    result = re.search(r"Result:\s*(\d+)\s+out of\s+(\d+)\s+records added", answer, re.IGNORECASE)
    if result is None:
        return False
    added, total = int(result.group(1)), int(result.group(2))
    if total != sent:
        return False
    duplicate_lines = [
        line for line in str(answer).splitlines()
        if re.search(r"\b(warning|error)\b", line, re.IGNORECASE) and re.search(r"duplicate", line, re.IGNORECASE)
    ]
    duplicates = min(len(duplicate_lines), total - added)
    return added + duplicates >= total


# ---------------------------------------------------------------------------
# QRZ.com logbook upload
# ---------------------------------------------------------------------------

def upload_to_qrz(api_key=None):
    """Upload the contacts not yet sent to the QRZ.com logbook; return a readable summary.

    api_key is the QRZ.com Logbook API key to use; without it the saved one
    is used. Uploads stop at the first authentication or network problem,
    since every following record would fail the same way.
    """
    api_key = str(api_key if api_key is not None else qrz_api_key).strip()
    records = _logbook_records(pending_for="qrz")
    if not records:
        return tr("logbook.nothing_to_upload")
    lines = []
    uploaded = []
    for record in records:
        answer = qrz_api_call(
            urllib.parse.urlencode({"KEY": api_key, "ACTION": "INSERT", "ADIF": adif_record(record)})
        )
        result = answer.get("RESULT", "ERROR").upper()
        label = "{} {} {}".format(record["callsign"], record["date"], record["time"])
        reason = answer.get("REASON", "")
        if result in ("OK", "REPLACE"):
            uploaded.append(record["id"])
            lines.append(tr("logbook.qrz_record_ok").format(label, answer.get("LOGID", "-")))
        elif result == "FAIL" and "duplicate" in reason.lower():
            # QRZ.com already has this contact.
            uploaded.append(record["id"])
            lines.append(tr("logbook.qrz_record_failed").format(label, reason))
        else:
            lines.append(tr("logbook.qrz_record_failed").format(label, reason or result))
            if result in ("AUTH", "ERROR") or "invalid api key" in reason.lower():
                break
    if uploaded:
        _mark_uploaded("qrz", uploaded)
    return tr("logbook.qrz_summary").format(len(uploaded), len(records)) + "\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# QRZ.com XML data (station pictures)
# ---------------------------------------------------------------------------

_qrz_session_key = None


def get_session_qrz():
    """Log in to the QRZ.com XML service and return a session key, or None.

    Needs the QRZ.com user name and password of the Platforms settings.
    """
    global _qrz_session_key
    if not qrz_username or not qrz_password:
        return None
    try:
        result = http_session.post(
            "https://xmldata.qrz.com/xml/current/",
            data={"username": qrz_username, "password": qrz_password, "agent": http_user_agent()},
            headers=http_headers(),
            timeout=HTTP_TIMEOUT,
        )
        if result.status_code != 200:
            return None
        session_data = (xmltodict.parse(result.content).get("QRZDatabase") or {}).get("Session") or {}
        if session_data.get("Error"):
            log.warning("QRZ.com login failed: %s", session_data.get("Error"))
            return None
        _qrz_session_key = session_data.get("Key")
        return _qrz_session_key
    except Exception as exc:
        log.warning("QRZ.com login failed: %s", exc)
        return None


def qrz_xml_picture_url(_callsign):
    """Picture address of a callsign from the QRZ.com XML service, "" when it has none.

    Returns None when the service cannot be used (no account, no subscription,
    network error), so the caller can fall back to the public page.
    """
    global _qrz_session_key
    for attempt in range(2):
        key = _qrz_session_key or get_session_qrz()
        if not key:
            return None
        try:
            result = http_session.get(
                "https://xmldata.qrz.com/xml/current/",
                params={"s": key, "callsign": _callsign},
                headers=http_headers(),
                timeout=HTTP_TIMEOUT,
            )
            database = xmltodict.parse(result.content).get("QRZDatabase") or {}
        except Exception as exc:
            log.warning("QRZ.com lookup of %s failed: %s", _callsign, exc)
            return None
        error = str((database.get("Session") or {}).get("Error") or "")
        if "session" in error.lower() and attempt == 0:
            # The key expired: log in again once.
            _qrz_session_key = None
            continue
        record = database.get("Callsign") or {}
        return str(record.get("image") or "")
    return None


def person_icon_path():
    """Path of the generic person icon shown when a station has no picture.

    Used while the QRZ.com picture is being looked up, and kept on screen
    when the station never uploaded a picture to QRZ.com.
    """
    return resource_path(os.path.join("data", "station.png"))


# File extension used to store a downloaded picture, by its MIME type.
PICTURE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}


def _picture_extension(content_type, image_url):
    """Pick the file extension of a downloaded picture from its MIME type or URL."""
    mime = str(content_type or "").split(";")[0].strip().lower()
    if mime in PICTURE_EXTENSIONS:
        return PICTURE_EXTENSIONS[mime]
    suffix = os.path.splitext(urllib.parse.urlparse(image_url).path)[1].lower()
    if suffix in CALLSIGN_PICTURE_EXTENSIONS:
        return suffix
    return ".jpg"


def download_qrz_picture(_callsign):
    """Download the QRZ.com picture of a callsign into images and return its path.

    The file is stored exactly as QRZ.com serves it, named after the callsign.
    Returns None when the station has no picture or the download fails.
    """
    _callsign = clean_callsign(_callsign)
    if not _callsign:
        return None
    image_url = qrz_picture_url(_callsign)
    if not image_url:
        return None
    cached = qrz_cache.get(_callsign, {})
    if cached.get("image") and os.path.isfile(cached["image"]):
        return cached["image"]
    try:
        resp = http_session.get(image_url, headers=http_headers(), timeout=20)
        content_type = resp.headers.get("Content-Type", "")
        if resp.status_code != 200 or not resp.content:
            raise ValueError("no picture received")
        if content_type and not content_type.lower().startswith("image/"):
            raise ValueError("not a picture: " + content_type)
        file_name = os.path.join(images_dir(), picture_file_stem(_callsign) + _picture_extension(content_type, image_url))
        with open(file_name, "wb") as picture_file:
            picture_file.write(resp.content)
    except Exception as exc:
        log.debug("No QRZ.com picture for %s: %s", _callsign, exc)
        return None
    qrz_cache.setdefault(_callsign, {})["image"] = file_name
    return file_name
