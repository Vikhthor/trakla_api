import sys
import datetime
import traceback
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, Field
from typing import Annotated, Literal
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt.exceptions import InvalidTokenError
import math
from dateutil import parser
from dateutil.parser import ParserError
from dateutil.relativedelta import relativedelta
from .db import Session, get_db, select, col, or_
from .models import User

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
