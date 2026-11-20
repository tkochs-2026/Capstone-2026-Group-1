#Market hours: when the market is open.
    #Administrators set the hours and trading days on the Administration page 
    #The market is also closed on the dates in holidays.json
    #price_generator.py only moves prices while it is open

import json
from datetime import datetime, timedelta
from datetime import time as time_of_day
from pathlib import Path

from app.common import EASTERN, now_utc
from app.models import MarketSchedule


# The three settings of the Market Control on the Administration page
FOLLOW_SCHEDULE = "Schedule"
FORCE_OPEN = "Open"
FORCE_CLOSED = "Closed"

#The days the market is closed for a holiday, from holidays.json
HOLIDAYS_FILE = Path(__file__).parent / "holidays.json"
with open(HOLIDAYS_FILE) as holidays_file:
    HOLIDAYS = json.load(holidays_file)


def get_schedule():
    #The market hours, as a dictionary.
    #Uses the newest schedule saved on the Administration page, or else 9 to 5, Monday to Friday

    saved = MarketSchedule.query.order_by(MarketSchedule.schedule_id.desc()).first()
    if saved is None:
        return {
            "open_time": time_of_day(9, 0),
            "close_time": time_of_day(17, 0),
            "trading_days": {0, 1, 2, 3, 4},
            "override": FOLLOW_SCHEDULE,
        }

    # The days are saved as one number
    trading_days = set()
    for day_number in range(7):
        if saved.trading_days & (2 ** day_number):
            trading_days.add(day_number)

    return {
        "open_time": saved.open_time,
        "close_time": saved.close_time,
        "trading_days": trading_days,
        "override": saved.market_override,
    }


def is_trading_day(day, schedule):
    #True if the market opens on this date: one of the chosen weekdays, and not a holiday
    if day.weekday() not in schedule["trading_days"]:
        return False
    if day.isoformat() in HOLIDAYS:
        return False
    return True


def is_open(schedule=None):
    """True if the market is open right now."""
    if schedule is None:
        schedule = get_schedule()

    #Force open and Force closed beat the hours, the days, and the holidays
    if schedule["override"] == FORCE_OPEN:
        return True
    if schedule["override"] == FORCE_CLOSED:
        return False

    now = now_utc().astimezone(EASTERN)
    if not is_trading_day(now.date(), schedule):
        return False
    return schedule["open_time"] <= now.time() < schedule["close_time"]


def get_status():
    #Whether the market is open, and when it closes or next opens
    schedule = get_schedule()
    status = {
        "is_open": is_open(schedule),
        "closes_at": None,
        "next_open": None,
        "forced_open": schedule["override"] == FORCE_OPEN,
        "forced_closed": schedule["override"] == FORCE_CLOSED,
    }
    if schedule["override"] != FOLLOW_SCHEDULE:
        #Forced open or closed: there is no next opening or closing time
        return status

    now = now_utc().astimezone(EASTERN)
    if status["is_open"]:
        status["closes_at"] = datetime.combine(now.date(), schedule["close_time"], EASTERN)
        return status

    #Look at today and the next two weeks for the next opening time.
    for days_ahead in range(15):
        day = now.date() + timedelta(days=days_ahead)
        opening = datetime.combine(day, schedule["open_time"], EASTERN)
        if is_trading_day(day, schedule) and opening > now:
            status["next_open"] = opening
            break
    return status


def clock_text(moment):
    #A time like "9:00 AM"
    return moment.strftime("%I:%M %p").lstrip("0")


def status_text(status):
    #Like "Market open · closes 5:00 PM" or "Market closed · opens Mon 9:00 AM"
    if status["is_open"]:
        if status["closes_at"] is None:
            return "Market open"
        return "Market open · closes " + clock_text(status["closes_at"])

    if status["next_open"] is None:
        return "Market closed"
    day = status["next_open"].strftime("%a")
    return "Market closed · opens " + day + " " + clock_text(status["next_open"])


