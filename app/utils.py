import sys
import datetime
import traceback
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, Field
from typing import Annotated, Literal, TYPE_CHECKING, Self, TypeVar, overload, override, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
import math
import orjson
import json
import re
from pathlib import Path as FilePath
from uuid import uuid4
from dateutil import parser
from dateutil.parser import ParserError
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from uuid import UUID
from decimal import Decimal
from .db import Session, get_db, select, col, or_
from .models import User
from collections.abc import Iterable, Mapping
from email.utils import formataddr, getaddresses, parseaddr
import nh3
from bleach_allowlist import bleach_allowlist

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class FilterParams(BaseModel):
    model_config = {"extra": "forbid"} # optionally restrict the query parameters that you want to receive. Here, if a client tries to send some extra data in the query parameters, they will receive an error response.
    limit: int | None = Field(100, gt=0, le=500)
    offset: int | None = Field(0, ge=0)
    page: int | None = Field(0, ge=0)
    order_by: Literal["created_at", "updated_at"] | None = "created_at"
    tags: list[str] | None = []
    search: str | None = None

# openssl rand -hex 32
SECRET_KEY = "4463234cf682cd70cdc0e87601d321e1dd0474741db08e9379d8a82c9324c4dd"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        print(f"Token: {token}")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        print(f"Email: {email}")
        if email is None:
            raise credentials_exception
    except InvalidTokenError as exc:
        raise credentials_exception from exc
    statement = select(User).where(User.email == email)
    user = db.exec(statement).first()
    if user is None:
        raise credentials_exception
    if user.disabled:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user

def validate_user_type(user: User, allowed_types: str | list[str] = "system"):
    if isinstance(allowed_types, str):
        allowed_types = allowed_types.replace(" ","").split(",")

    if user.user_type not in allowed_types:
        raise HTTPException(status_code=403, detail="Not allowed")

BASE_DIR = FilePath(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "public" / "files"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_SIZE = 5 * 1024 * 1024  # 5 MB

def get_size_bytes(file) -> int:
    if file.size is not None:
        return file.size
    # Fallback: seek to the end to measure, then rewind
    file.file.seek(0, 2)   # 2 = os.SEEK_END
    size = file.file.tell()
    file.file.seek(0)
    return size

def format_size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} PB"

def upload_file(file):
    """
    Upload file to server
    """
    ext = FilePath(file.filename or "").suffix.lower()
    filename = f"{uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    size = 0
    try:
        with dest.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):  # 1 MB chunks
                size += len(chunk)
                if size > MAX_SIZE:
                    raise HTTPException(status_code=413, detail="File too large")
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)  # remove the partial file
        raise
    finally:
        file.file.close()

    file_size = format_size(get_size_bytes(file))
    return {
        "filename": filename, 
        "file_type": file.content_type, 
        "file_size": file_size, 
        "url": f"/public/files/{filename}"
    }

def get_url(path: str | None = None):
    url = "https://api.trakla.africa"
    if path:
        url += path
    return url

def get_app_url(path: str | None = None):
    url = "https://app.trakla.africa"
    if path:
        url += path
    return url

def abs_url(path):
    """Deconstructs and Reconstructs a URL into an absolute URL or a URL relative from root '/'"""
    if not path:
        return
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("tel:"):
        return path
    if path.startswith("data:"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return path

def parse_json(val: Any):
    """
    Parses json if string else return
    """
    if isinstance(val, str):
        val = orjson.loads(val) # pylint: disable=no-member
    if isinstance(val, dict):
        val = _dict(val)
    return val

def safe_encode(param, encoding="utf-8"):
    try:
        param = param.encode(encoding)
    except Exception:
        pass
    return param

URLS_NOT_HTTP_TAG_PATTERN = re.compile(
	r'(href|src){1}([\s]*=[\s]*[\'"]?)((?!http)[^\'" >]+)([\'"]?)'
)  # href=/assets/...
URL_NOTATION_PATTERN = re.compile(
	r'(:[\s]?url)(\([\'"]?)((?!http)[^\'" >]+)([\'"]?\))'
)  # background-image: url('/assets/...')

def scrub_urls(html: str) -> str:
    """Expand relative urls in the given `html`.

    e.g. If HTML is '<a href="/files/abc.jpeg">View Image</a>' and site URL is 'https://frappe.io',
            returns '<a href="https://frappe.io/files/abc.jpeg">View Image</a>'.
    """
    return expand_relative_urls(html)

def expand_relative_urls(html: str) -> str:
    """Expand relative urls in the given `html`.

    e.g. If HTML is '<a href="/files/abc.jpeg">View Image</a>' and site URL is 'https://frappe.io',
            returns '<a href="https://frappe.io/files/abc.jpeg">View Image</a>'.
    """
    # expand relative urls
    url = get_url()
    if url.endswith("/"):
        url = url[:-1]

    def _expand_relative_urls(match):
        to_expand = list(match.groups())

        if not to_expand[2].startswith(("mailto", "data:", "tel:")):
            if not to_expand[2].startswith("/"):
                to_expand[2] = "/" + to_expand[2]
            to_expand.insert(2, url)

        if "url" in to_expand[0] and to_expand[1].startswith("(") and to_expand[-1].endswith(")"):
            # background-image: url('/assets/...') - workaround for wkhtmltopdf print-media-type
            to_expand.append(" !important")

        return "".join(to_expand)

    html = URLS_NOT_HTTP_TAG_PATTERN.sub(_expand_relative_urls, html)
    html = URL_NOTATION_PATTERN.sub(_expand_relative_urls, html)
    return html

EMAIL_NAME_PATTERN = re.compile(r"[^A-Za-z0-9\u00C0-\u024F\/\_\' ]+")
EMAIL_STRING_PATTERN = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
NON_MD_HTML_PATTERN = re.compile(r"<p[\s]*>|<br[\s]*>")
HTML_TAGS_PATTERN = re.compile(r"\<[^>]*\>")
INCLUDE_DIRECTIVE_PATTERN = re.compile("""({% include ['"]([^'"]*)['"] %})""")
PHONE_NUMBER_PATTERN = re.compile(r"([0-9\ \+\_\-\,\.\*\#\(\)]){1,20}$")
PERSON_NAME_PATTERN = re.compile(r"^[\w][\w\'\-]*( \w[\w\'\-]*)*$")
WHITESPACE_PATTERN = re.compile(r"[\t\n\r]")
MULTI_EMAIL_STRING_PATTERN = re.compile(r'[,\n](?=(?:[^"]|"[^"]*")*$)')
EMAIL_MATCH_PATTERN = re.compile(
	r"[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?",
	re.IGNORECASE,
)

def strip(val: str, chars: str | None = None) -> str:
    """Strip the given characters from the given string.

    e.g. strip(',hello,bye,', ',') -> 'hello,bye'
    """
    # \ufeff is no-width-break, \u200b is no-width-space
    return (val or "").replace("\ufeff", "").replace("\u200b", "").strip(chars)

def split_emails(txt):
    email_list = []

    # emails can be separated by comma or newline
    s = WHITESPACE_PATTERN.sub(" ", cstr(txt))
    for email in MULTI_EMAIL_STRING_PATTERN.split(s):
        email = strip(cstr(email))
        if email:
            email_list.append(email)

    return email_list

def get_string_between(start: str, string: str, end: str) -> str:
    if not string:
        return ""

    out = re.search(f"{start}(.*){end}", string)

    return out.group(1) if out else string

def random_string(length: int) -> str:
    """generate a random string"""
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for i in range(length))

DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S.%f"
DATETIME_FORMAT = f"{DATE_FORMAT} {TIME_FORMAT}"
DateTimeLikeObject = str | datetime.date | datetime.datetime
NumericType = int | float

def is_invalid_date_string(date_string: str) -> bool:
    """Return True if the date string is invalid or None or empty."""
    # dateutil parser does not agree with dates like "0001-01-01" or "0000-00-00"
    return not isinstance(date_string, str) or (
        (not date_string) or (date_string or "").startswith(("0001-01-01", "0000-00-00"))
    )

def get_system_timezone() -> str:
	"""Return the system timezone."""
	return "Africa/Lagos"

def now_datetime() -> datetime.datetime:
	"""Return the current datetime in system timezone."""
	return datetime.datetime.now(ZoneInfo(get_system_timezone())).replace(tzinfo=None)

def get_datetime(
    datetime_str: DateTimeLikeObject | None | tuple | list = None,
) -> datetime.datetime | None:
    """Return the below mentioned values based on the given `datetime_str`:

    * If `datetime_str` is None, returns datetime object of current datetime
    * If `datetime_str` is already a datetime object, returns the same
    * If `datetime_str` is a timedelta object, returns the same
    * If `datetime_str` is a list or tuple, returns a datetime object
    * If `datetime_str` is a date object, returns a datetime object
    * If `datetime_str` is a valid date string, returns a datetime object for the same
    * If `datetime_str` is an invalid date string, returns None
    """

    if datetime_str is None:
        return now_datetime()

    elif isinstance(datetime_str, datetime.datetime | datetime.timedelta):
        return datetime_str

    elif isinstance(datetime_str, list | tuple):
        return datetime.datetime(datetime_str)

    elif isinstance(datetime_str, datetime.date):
        return datetime.datetime.combine(datetime_str, datetime.time())

    elif is_invalid_date_string(datetime_str):
        return None

    try:
        # PERF: Our DATETIME_FORMAT is same as ISO format.
        # fromisoformat is written in C so it's better than using strptime parser
        return datetime.datetime.fromisoformat(datetime_str)
    except ValueError:
        return parser.parse(datetime_str)

def getdate(
    string_date: DateTimeLikeObject | None = None, parse_day_first: bool = False
) -> datetime.date | None:
    """
    Convert string date (yyyy-mm-dd) to datetime.date object.
    If no input is provided, current date is returned.
    """
    if not string_date:
        return get_datetime().date()
    elif isinstance(string_date, datetime.datetime):
        return string_date.date()

    elif isinstance(string_date, datetime.date):
        return string_date

    elif is_invalid_date_string(string_date):
        return None

    try:
        # PERF: Our DATE_FORMAT is same as ISO format.
        # fromisoformat is written in C so it's better than using strptime parser
        return datetime.date.fromisoformat(string_date)
    except ValueError:
        try:
            return parser.parse(string_date, dayfirst=parse_day_first).date()
        except ParserError as exc:
            raise Exception("Invalid Date", f"{string_date} is not a valid date string.") from exc

def add_to_date(
	date: DateTimeLikeObject | None = None,
	years=0,
	months=0,
	weeks=0,
	days=0,
	hours=0,
	minutes=0,
	seconds=0,
	as_string=False,
	as_datetime=False,
) -> DateTimeLikeObject:
    """Adds `days` to the given date"""

    if date is None:
        date = now_datetime()

    if hours:
        as_datetime = True

    if isinstance(date, str):
        as_string = True
        if " " in date:
            as_datetime = True
        try:
            date = get_datetime(date)
        except ParserError as exc:
            raise Exception("Invalid Date", f"Please select a valid date filter.") from exc

    date = date + relativedelta(
        years=years, months=months, weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds
    )

    if as_string:
        if as_datetime:
            return date.strftime(DATETIME_FORMAT)
        else:
            return date.strftime(DATE_FORMAT)
    else:
        return date

def get_first_day(dt, d_years: int = 0, d_months: int = 0, as_str: bool = False) -> str | datetime.date:
    """Return the first day of the month for the date specified by date object.

    Also, add `d_years` and `d_months` if specified.
    """
    dt = getdate(dt)

    # d_years, d_months are "deltas" to apply to dt
    overflow_years, month = divmod(dt.month + d_months - 1, 12)
    year = dt.year + d_years + overflow_years

    # divmod by 12 always yields a remainder in [0, 11]; month + 1 must be a valid 1..12 month
    assert 0 <= month <= 11, "month index out of range after divmod by 12"

    return (
        datetime.date(year, month + 1, 1).strftime(DATE_FORMAT)
        if as_str
        else datetime.date(year, month + 1, 1)
    )

def add_days(date: DateTimeLikeObject, days: NumericType) -> DateTimeLikeObject:
    """Return a new date after adding the given number of `days` to the given `date`."""
    return add_to_date(date, days=days)

def nowdate() -> str:
    """Return current date as `yyyy-mm-dd`."""
    return now_datetime().strftime(DATE_FORMAT)

def rounded(num, precision=0, rounding_method=None):
    """Round according to method set in system setting, defaults to banker's rounding"""
    precision = cint(precision)

    rounding_method = (
        rounding_method or "Banker's Rounding (legacy)"
    )

    if rounding_method == "Banker's Rounding":
        return _bankers_rounding(num, precision)
    elif rounding_method == "Banker's Rounding (legacy)":
        return _bankers_rounding_legacy(num, precision)
    elif rounding_method == "Commercial Rounding":
        return _round_away_from_zero(num, precision)
    else:
        raise Exception("InvalidRoundingMethod", f"Unknown Rounding Method: {rounding_method}")

def _bankers_rounding_legacy(num, precision):
    # avoid rounding errors
    multiplier = 10**precision
    num = round(num * multiplier if precision else num, 8)

    floor_num = math.floor(num)
    decimal_part = num - floor_num

    if not precision and decimal_part == 0.5:
        num = floor_num if (floor_num % 2 == 0) else floor_num + 1
    else:
        if decimal_part == 0.5:
            num = floor_num + 1
        else:
            num = round(num)

    return (num / multiplier) if precision else num


def _round_away_from_zero(num, precision):
    if num == 0:
        return 0.0

    # Epsilon is small correctional value added to correctly round numbers which can't be
    # represented in IEEE 754 representation.

    # In simplified terms, the representation optimizes for absolute errors in representation
    # so if a number is not representable it might be represented by a value ever so slighly
    # smaller than the value itself. This becomes a problem when breaking ties for numbers
    # ending with 5 when it's represented by a smaller number. By adding a very small value
    # close to what's "least count" or smallest representable difference in the scale we force
    # the number to be bigger than actual value, this increases representation error but
    # removes rounding error.

    # References:
    # - https://docs.oracle.com/cd/E19957-01/806-3568/ncg_goldberg.html
    # - https://docs.python.org/3/tutorial/floatingpoint.html#representation-error
    # - https://docs.python.org/3/library/functions.html#round
    # - easier to understand: https://www.youtube.com/watch?v=pQs_wx8eoQ8

    epsilon = 2.0 ** (math.log(abs(num), 2) - 52.0)

    return round(num + math.copysign(epsilon, num), precision)


def _bankers_rounding(num, precision):
    if num == 0:
        return 0.0

    sign = -1 if num < 0 else 1
    multiplier = 10**precision
    num = round(abs(num) * multiplier, 12)

    if num == 0:
        return 0.0

    floor_num = math.floor(num)
    decimal_part = num - floor_num

    epsilon = 2.0 ** (math.log(num, 2) - 52.0)
    if abs(decimal_part - 0.5) < epsilon:
        num = floor_num if (floor_num % 2 == 0) else floor_num + 1
    else:
        num = round(num)

    return sign * num / multiplier

def flt(
    s: NumericType | str | None, precision: int | None = None, rounding_method: str | None = None
) -> float:
    """Convert to float (ignoring commas in string).

    :param s: Number in string or other numeric format.
    :param precision: optional argument to specify precision for rounding.
    :returns: Converted number in python float type.

    Return 0 if input can not be converted to float.

    Examples:

    >>> flt("43.5", precision=0)
    44
    >>> flt("42.5", precision=0)
    42
    >>> flt("10,500.5666", precision=2)
    10500.57
    >>> flt("a")
    0.0
    >>> flt(None)
    0.0
    """

    if s is None:
        return 0.0

    if isinstance(s, str):
        s = s.replace(",", "")

    try:
        num = float(s)
        if precision is not None:
            num = rounded(num, precision, rounding_method)
    except Exception:
        num = 0.0

    return num

def cint(s: NumericType | str | None, default: int = 0) -> int:
    """Convert to integer.

    :param s: Number in string or other numeric format.
    :returns: Converted number in python integer type.

    Return default if input cannot be converted to integer.

    Examples:
    >>> cint("100")
    100
    >>> cint("a")
    0
    >>> cint(None)
    0

    """
    if s is None:
        return default

    try:
        return int(s)
    except Exception:
        try:
            return int(float(s))
        except Exception:
            return default

def as_unicode(text, encoding: str = "utf-8") -> str:
    """Convert to unicode if required."""
    if isinstance(text, str):
        return text
    elif text is None:
        return ""
    elif isinstance(text, bytes):
        return str(text, encoding)
    else:
        return str(text)

def cstr(s, encoding="utf-8") -> str:
    """Convert the given argument to string."""
    return as_unicode(s, encoding)

DateOrTimeTypes = datetime.date | datetime.datetime | datetime.time

def format_timedelta(o: datetime.timedelta | str) -> str:
    # MariaDB allows a wide range - https://mariadb.com/kb/en/time/
    # but Frappe doesn't - I think via babel : only allows 0..23 range for hour
    if isinstance(o, datetime.timedelta):
        total_seconds = o.total_seconds()
    else:
        total_seconds = cint(o)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    rounded_seconds = round(seconds, 6)
    int_seconds = int(seconds)

    if rounded_seconds == int_seconds:
        seconds = int_seconds
    else:
        seconds = rounded_seconds

    return f"{int(hours):01}:{int(minutes):02}:{seconds:02}"

def json_handler(obj):
    """serialize non-serializable data for json"""

    timedelta = datetime.timedelta

    if isinstance(obj, DateOrTimeTypes):
        return str(obj)

    elif isinstance(obj, timedelta):
        return format_timedelta(obj)

    elif hasattr(obj, "__json__"):
        return obj.__json__()

    elif isinstance(obj, Iterable):
        return list(obj)

    elif isinstance(obj, Decimal):
        return float(obj)

    elif isinstance(obj, re.Match):
        return obj.string

    elif type(obj) is type or isinstance(obj, Exception):
        return repr(obj)

    elif callable(obj):
        return repr(obj)

    elif isinstance(obj, FilePath):
        return str(obj)

    # orjson does this already
    # but json_handler needs to be compatible with built-in json module also
    elif isinstance(obj, UUID):
        return str(obj)

    else:
        raise TypeError(f"""Object of type {type(obj)} with value of {obj!r} is not JSON serializable""")

def as_json(obj: dict | list, indent=1, separators=None, ensure_ascii=True) -> str:
    """Return the JSON string representation of the given `obj`."""

    if separators is None:
        separators = (",", ": ")

    try:
        return json.dumps(
            obj,
            indent=indent,
            sort_keys=True,
            default=json_handler,
            separators=separators,
            ensure_ascii=ensure_ascii,
        )
    except TypeError:
        # this would break in case the keys are not all os "str" type - as defined in the JSON
        # adding this to ensure keys are sorted (expected behaviour)
        sorted_obj = dict(sorted(obj.items(), key=lambda kv: str(kv[0])))
        return json.dumps(
            sorted_obj,
            indent=indent,
            default=json_handler,
            separators=separators,
            ensure_ascii=ensure_ascii,
        )

    

def html_to_plain_text(html: str) -> str:
    """Return the given `html` as plain text."""

    if not html:
        return ""

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style"]):
        element.decompose()

    # Introduce explicit newlines for block-level elements while keeping inline content on the same line.
    for br in soup.find_all("br"):
        br.replace_with("\n")

    for block in soup.find_all(["p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
        block.append("\n")

    # Use a space separator between text nodes so inline tags don't break lines
    text = soup.get_text(separator=" ")

    lines = [line.strip() for line in text.splitlines()]
    cleaned = []
    previous_blank = False

    for line in lines:
        if line:
            cleaned.append(line)
            previous_blank = False
        else:
            if not previous_blank:
                cleaned.append("")
            previous_blank = True

    return "\n".join(cleaned).strip()

class InvalidEmailAddressError(Exception):
    pass

def escape_html(text: str) -> str:
    """Return the given text with HTML special characters escaped.

    e.g. '<h1>Hello</h1>' -> '&lt;h1&gt;Hello&lt;/h1&gt;'
    """
    if not isinstance(text, str):
        return text

    html_escape_table = {
        "&": "&amp;",
        '"': "&quot;",
        "'": "&apos;",
        ">": "&gt;",
        "<": "&lt;",
    }

    return "".join(html_escape_table.get(c, c) for c in text)

def validate_email_address(email_str, throw=False):
    """Validates the email string"""

    email_str = (email_str or "").strip()
    out = []

    # split_emails collapses \n/\r to spaces *before* splitting, so newlines
    # would no longer act as separators. Convert them to commas up front.
    email_str = email_str.replace("\n", ",").replace("\r", ",")

    # Fast path: parse the whole string in one shot. Strict mode either gives
    # us all entries cleanly or bails to [('', '')] on malformed input.
    addresses = getaddresses([email_str])

    # Slow path: if nothing usable came back, re-parse each piece in isolation
    # so one malformed entry can't reject its valid neighbours. split_emails
    # is quote-aware, so `"Last, First" <addr>` survives the split intact.
    if not any(addr for _, addr in addresses):
        addresses = []
        for piece in split_emails(email_str):
            addresses.extend(getaddresses([piece]))

    for name, addr in addresses:
        if not addr:
            if throw:
                raise InvalidEmailAddressError(f"{escape_html(name or email_str)} is not a valid Email Address")
            continue

        # Skip undisclosed recipients
        if "undisclosed-recipient" in addr:
            continue

        if not EMAIL_MATCH_PATTERN.fullmatch(addr):
            if throw:
                raise InvalidEmailAddressError(f"{escape_html(addr)} is not a valid Email Address")
            continue

        out.append(addr)

    return ", ".join(out)

def check_format(email_id):
    """
    Check if email_id is valid. valid email:text@example.com
    String check ensures that email_id contains both '.' and
    '@' and index of '@' is less than '.'
    """
    is_valid = False
    try:
        pos = email_id.rindex("@")
        is_valid = pos > 0 and (email_id.rindex(".") > pos) and (len(email_id) - pos > 4)
    except Exception:
        # print(e)
        pass
    return is_valid

def get_name_from_email_string(email_string, email_id, name):
    name = email_string.replace(email_id, "")
    name = EMAIL_NAME_PATTERN.sub("", name).strip()
    if not name:
        name = email_id
    return name

def parse_addr(email_string):
    """
    Return email_id and user_name based on email string
    Raise error if email string is not valid
    """
    name, email = parseaddr(email_string)
    if check_format(email):
        name = get_name_from_email_string(email_string, email, name)
        return (name, email)
    else:
        email_list = EMAIL_STRING_PATTERN.findall(email_string)
        if len(email_list) > 0 and check_format(email_list[0]):
            # take only first email address
            email = email_list[0]
            name = get_name_from_email_string(email_string, email, name)
            return (name, email)
    return (None, email)

def sanitize_email(emails):
    sanitized = []
    for e in split_emails(emails):
        if not validate_email_address(e):
            continue

        full_name, email_id = parse_addr(e)
        sanitized.append(formataddr((full_name, email_id)))

    return ", ".join(sanitized)

class UnicodeWithAttrs(str):
    def __init__(self, text):
        self.toc_html = text.toc_html
        self.metadata = text.metadata

def md_to_html(markdown_text: str) -> "UnicodeWithAttrs" | None:
    """Convert the given markdown text to HTML and returns it."""
    from markdown2 import MarkdownError
    from markdown2 import markdown as _markdown

    extras = {
        "fenced-code-blocks": None,
        "tables": None,
        "header-ids": None,
        "toc": None,
        "highlightjs-lang": None,
        "html-classes": {"table": "table table-bordered", "img": "screenshot"},
    }

    try:
        return UnicodeWithAttrs(_markdown(markdown_text or "", extras=extras))
    except MarkdownError:
        pass

HTML_TAG_PATTERN = re.compile("<[^>]+>")

def is_html(text: str) -> bool:
    """Return True if the given `text` contains any HTML tags."""
    if not isinstance(text, str):
        return False
    return HTML_TAG_PATTERN.search(text)

def sanitize_html(html, linkify=False, always_sanitize=False, disallowed_tags=None):
    """
    Sanitize HTML tags, attributes and style to prevent XSS attacks
    Based on nh3 clean, bleach whitelist and html5lib's Sanitizer defaults

    Content without any HTML tags is returned unchanged; everything else is sanitized.
    """
    # pylint: disable=no-member
    from bs4 import BeautifulSoup

    if not isinstance(html, str):
        return html

    if not always_sanitize:
        if not bool(BeautifulSoup(html, "html.parser").find()):
            return html

    tags = (
        acceptable_elements.union(svg_elements)
        .union(mathml_elements)
        .union(["html", "head", "meta", "link", "body", "o:p"])
    )

    # Allow caller to explicitly disallow some tags
    if disallowed_tags:
        if disallowed_tags == "*":
            tags = set()
        else:
            tags.difference_update(disallowed_tags)

    attributes = {"*": acceptable_attributes, "svg": svg_attributes}

    # returns sanitized HTML with unsafe tags and attributes removed
    escaped_html = nh3.clean(
        html,
        tags=tags,
        attributes=attributes,
        generic_attribute_prefixes={"data-"},
        strip_comments=False,
        filter_style_properties=set(bleach_allowlist.all_styles),
        url_schemes=nh3.ALLOWED_URL_SCHEMES.union({"cid"}),
    )

    return escaped_html

def markdown(text, sanitize=True, linkify=True):
    html = text if is_html(text) else md_to_html(text)

    if sanitize:
        html = html.replace("<!-- markdown -->", "")
        html = sanitize_html(html, linkify=linkify)

    return html

def html2text(html: str, strip_links=False, wrap=True) -> str:
    """Return the given `html` as markdown text."""
    from markdownify import markdownify as md

    strip_link = ["a"] if strip_links else None
    return md(html, heading_style="ATX", strip=strip_link, wrap=wrap)

def to_markdown(html: str) -> str:
    """Convert the given HTML to markdown and returns it."""
    # pylint: disable=no-member
    from html.parser import HTMLParser

    try:
        return html2text(html or "")
    except HTMLParser.HTMLParseError:
        pass

def unescape_html(value):
    from html import unescape

    return unescape(value)


@lru_cache(maxsize=1)
def _get_traceback_sanitizer():
    from traceback_with_variables import Format

    blocklist = [
        "password",
        "passwd",
        "secret",
        "token",
        "key",
        "pwd",
    ]

    placeholder = "********"

    def dict_printer(v: dict) -> str:
        v = v.copy()
        for key in blocklist:
            if key in v:
                v[key] = placeholder

        return str(v)

def get_traceback(with_context: bool = False) -> str:
    """Return the traceback of the Exception."""
    from traceback_with_variables import iter_exc_lines

    exc_type, exc_value, exc_tb = sys.exc_info()

    if not any([exc_type, exc_value, exc_tb]):
        return ""

    if with_context:
        trace_list = iter_exc_lines(fmt=_get_traceback_sanitizer())
        tb = "\n".join(trace_list)
    else:
        trace_list = traceback.format_exception(exc_type, exc_value, exc_tb)
        tb = "".join(cstr(t) for t in trace_list)
    return tb

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class _dict(dict[_KT, _VT]):
    """dict like object that exposes keys as attributes"""

    __slots__ = ()

    # NOTE(perf): Do NOT use super() here, it's an unnecessary function call!
    # Refer: https://github.com/frappe/frappe/pull/16449

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__
    __setstate__ = dict.update

    @override
    def __getstate__(self) -> Self:
        return self

    @overload  # type: ignore[override]
    def update(self, m: Mapping[_KT, _VT], /, **kwargs: _VT) -> Self: ...

    @overload
    def update(self, m: Iterable[tuple[_KT, _VT]], /, **kwargs: _VT) -> Self: ...

    @overload
    def update(self, /, **kwargs: _VT) -> Self: ...

    @override
    def update(
        self, m: Mapping[_KT, _VT] | Iterable[tuple[_KT, _VT]] | None = None, /, **kwargs: _VT
    ) -> Self:
        """update and return self -- the missing dict feature in python"""
        if m:
            super().update(m, **kwargs)
        else:
            super().update(**kwargs)
        return self

    @override
    def copy(self) -> "_dict[_KT, _VT]":
        return _dict(self)

acceptable_elements = {
	"a",
	"abbr",
	"acronym",
	"address",
	"area",
	"article",
	"aside",
	"audio",
	"b",
	"big",
	"blockquote",
	"br",
	"button",
	"canvas",
	"caption",
	"center",
	"cite",
	"code",
	"col",
	"colgroup",
	"command",
	"datagrid",
	"datalist",
	"dd",
	"del",
	"details",
	"dfn",
	"dialog",
	"dir",
	"div",
	"dl",
	"dt",
	"em",
	"event-source",
	"fieldset",
	"figcaption",
	"figure",
	"footer",
	"font",
	"form",
	"header",
	"h1",
	"h2",
	"h3",
	"h4",
	"h5",
	"h6",
	"hr",
	"i",
	"img",
	"input",
	"ins",
	"keygen",
	"kbd",
	"label",
	"legend",
	"li",
	"m",
	"map",
	"mark",
	"menu",
	"meter",
	"multicol",
	"nav",
	"nextid",
	"ol",
	"output",
	"optgroup",
	"option",
	"p",
	"pre",
	"progress",
	"q",
	"s",
	"samp",
	"section",
	"select",
	"small",
	"sound",
	"source",
	"spacer",
	"span",
	"strike",
	"strong",
	"sub",
	"summary",
	"sup",
	"table",
	"tbody",
	"td",
	"textarea",
	"time",
	"tfoot",
	"th",
	"thead",
	"tr",
	"tt",
	"u",
	"ul",
	"var",
	"video",
}

mathml_elements = {
	"maction",
	"math",
	"merror",
	"mfrac",
	"mi",
	"mmultiscripts",
	"mn",
	"mo",
	"mover",
	"mpadded",
	"mphantom",
	"mprescripts",
	"mroot",
	"mrow",
	"mspace",
	"msqrt",
	"mstyle",
	"msub",
	"msubsup",
	"msup",
	"mtable",
	"mtd",
	"mtext",
	"mtr",
	"munder",
	"munderover",
	"none",
}

svg_elements = {
	"a",
	"animate",
	"animateColor",
	"animateMotion",
	"animateTransform",
	"clipPath",
	"circle",
	"defs",
	"desc",
	"ellipse",
	"font-face",
	"font-face-name",
	"font-face-src",
	"g",
	"glyph",
	"hkern",
	"linearGradient",
	"line",
	"marker",
	"metadata",
	"missing-glyph",
	"mpath",
	"path",
	"polygon",
	"polyline",
	"radialGradient",
	"rect",
	"set",
	"stop",
	"svg",
	"switch",
	"text",
	"title",
	"tspan",
	"use",
}

acceptable_attributes = {
	"abbr",
	"accept",
	"accept-charset",
	"accesskey",
	"action",
	"align",
	"alt",
	"autocomplete",
	"autofocus",
	"axis",
	"background",
	"balance",
	"bgcolor",
	"bgproperties",
	"border",
	"bordercolor",
	"bordercolordark",
	"bordercolorlight",
	"bottompadding",
	"cellpadding",
	"cellspacing",
	"ch",
	"challenge",
	"char",
	"charoff",
	"choff",
	"charset",
	"checked",
	"cite",
	"class",
	"clear",
	"color",
	"cols",
	"colspan",
	"compact",
	"content",
	"contenteditable",
	"controls",
	"coords",
	"data",
	"datafld",
	"datapagesize",
	"datasrc",
	"datetime",
	"default",
	"delay",
	"dir",
	"disabled",
	"draggable",
	"dynsrc",
	"enctype",
	"end",
	"face",
	"for",
	"form",
	"frame",
	"galleryimg",
	"gutter",
	"headers",
	"height",
	"hidefocus",
	"hidden",
	"high",
	"href",
	"hreflang",
	"hspace",
	"icon",
	"id",
	"inputmode",
	"ismap",
	"keytype",
	"label",
	"leftspacing",
	"lang",
	"list",
	"longdesc",
	"loop",
	"loopcount",
	"loopend",
	"loopstart",
	"low",
	"lowsrc",
	"max",
	"maxlength",
	"media",
	"method",
	"min",
	"multiple",
	"name",
	"nohref",
	"noshade",
	"nowrap",
	"open",
	"optimum",
	"pattern",
	"ping",
	"point-size",
	"poster",
	"pqg",
	"preload",
	"prompt",
	"radiogroup",
	"readonly",
	"repeat-max",
	"repeat-min",
	"replace",
	"required",
	"rev",
	"rightspacing",
	"rows",
	"rowspan",
	"rules",
	"scope",
	"selected",
	"shape",
	"size",
	"span",
	"src",
	"start",
	"step",
	"style",
	"summary",
	"suppress",
	"tabindex",
	"target",
	"template",
	"title",
	"toppadding",
	"type",
	"unselectable",
	"usemap",
	"urn",
	"valign",
	"value",
	"variable",
	"volume",
	"vspace",
	"vrml",
	"width",
	"wrap",
	"xml:lang",
	"data-row",
	"data-list",
	"data-language",
	"data-value",
	"role",
	"frameborder",
	"allowfullscreen",
	"spellcheck",
	"data-mode",
	"data-gramm",
	"data-placeholder",
	"data-comment",
	"data-id",
	"data-denotation-char",
	"itemprop",
	"itemscope",
	"itemtype",
	"itemid",
	"itemref",
	"data-is-group",
}

mathml_attributes = {
	"actiontype",
	"align",
	"columnalign",
	"columnlines",
	"columnspacing",
	"columnspan",
	"depth",
	"display",
	"displaystyle",
	"equalcolumns",
	"equalrows",
	"fence",
	"fontstyle",
	"fontweight",
	"frame",
	"height",
	"linethickness",
	"lspace",
	"mathbackground",
	"mathcolor",
	"mathvariant",
	"maxsize",
	"minsize",
	"other",
	"rowalign",
	"rowlines",
	"rowspacing",
	"rowspan",
	"rspace",
	"scriptlevel",
	"selection",
	"separator",
	"stretchy",
	"width",
	"xlink:href",
	"xlink:show",
	"xlink:type",
	"xmlns",
	"xmlns:xlink",
}

svg_attributes = {
	"accent-height",
	"accumulate",
	"additive",
	"alphabetic",
	"arabic-form",
	"ascent",
	"attributeName",
	"attributeType",
	"baseProfile",
	"bbox",
	"begin",
	"by",
	"calcMode",
	"cap-height",
	"class",
	"clip-path",
	"color",
	"color-rendering",
	"content",
	"colwidth",
	"cx",
	"cy",
	"d",
	"dx",
	"dy",
	"descent",
	"display",
	"dur",
	"end",
	"fill",
	"fill-opacity",
	"fill-rule",
	"font-family",
	"font-size",
	"font-stretch",
	"font-style",
	"font-variant",
	"font-weight",
	"from",
	"fx",
	"fy",
	"g1",
	"g2",
	"glyph-name",
	"gradientUnits",
	"hanging",
	"height",
	"horiz-adv-x",
	"horiz-origin-x",
	"id",
	"ideographic",
	"k",
	"keyPoints",
	"keySplines",
	"keyTimes",
	"lang",
	"marker-end",
	"marker-mid",
	"marker-start",
	"markerHeight",
	"markerUnits",
	"markerWidth",
	"mathematical",
	"max",
	"min",
	"name",
	"offset",
	"opacity",
	"orient",
	"origin",
	"overline-position",
	"overline-thickness",
	"panose-1",
	"path",
	"pathLength",
	"points",
	"preserveAspectRatio",
	"r",
	"refX",
	"refY",
	"repeatCount",
	"repeatDur",
	"requiredExtensions",
	"requiredFeatures",
	"restart",
	"rotate",
	"rx",
	"ry",
	"slope",
	"stemh",
	"stemv",
	"stop-color",
	"stop-opacity",
	"strikethrough-position",
	"strikethrough-thickness",
	"stroke",
	"stroke-dasharray",
	"stroke-dashoffset",
	"stroke-linecap",
	"stroke-linejoin",
	"stroke-miterlimit",
	"stroke-opacity",
	"stroke-width",
	"systemLanguage",
	"target",
	"text-anchor",
	"to",
	"transform",
	"type",
	"u1",
	"u2",
	"underline-position",
	"underline-thickness",
	"unicode",
	"unicode-range",
	"units-per-em",
	"values",
	"version",
	"viewBox",
	"visibility",
	"width",
	"widths",
	"x",
	"x-height",
	"x1",
	"x2",
	"xlink:actuate",
	"xlink:arcrole",
	"xlink:href",
	"xlink:role",
	"xlink:show",
	"xlink:title",
	"xlink:type",
	"xml:base",
	"xml:lang",
	"xml:space",
	"xmlns",
	"xmlns:xlink",
	"y",
	"y1",
	"y2",
	"zoomAndPan",
}