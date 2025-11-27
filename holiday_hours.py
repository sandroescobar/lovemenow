"""
Holiday hours and store closure management

This module manages holiday closures and special hours.
Easy to update for different dates and times.
"""
from datetime import datetime, date
from typing import Optional, Dict


# Holiday closures configuration
# Format: (month, day, year, closing_hour, closing_minute, message_override)
HOLIDAY_CLOSURES = [
    # Thanksgiving 2025
    (11, 27, 2025, 17, 0, None),  # November 27, 2025 at 5:00 PM
    
    # Christmas 2025
    # (12, 25, 2025, 18, 0, None),  # December 25, 2025 at 6:00 PM (example)
]


def get_today_closure_info() -> Optional[Dict]:
    """
    Check if today is a holiday closure day and return closure info.
    
    Returns:
        Dict with keys: {
            'is_closed': bool,
            'closing_hour': int (24-hour format),
            'closing_minute': int,
            'closing_time_str': str (e.g., "5:00 PM"),
            'message': str (full holiday message)
        }
        or None if not a holiday closure day
    """
    today = date.today()
    
    for month, day, year, hour, minute, custom_msg in HOLIDAY_CLOSURES:
        if today.month == month and today.day == day and today.year == year:
            # Convert to 12-hour format for display
            if hour == 0:
                hour_12 = 12
                am_pm = "AM"
            elif hour < 12:
                hour_12 = hour
                am_pm = "AM"
            elif hour == 12:
                hour_12 = 12
                am_pm = "PM"
            else:
                hour_12 = hour - 12
                am_pm = "PM"
            
            closing_time_str = f"{hour_12}:{minute:02d} {am_pm}"
            
            # Use custom message if provided, otherwise use default
            if custom_msg:
                message = custom_msg
            else:
                message = f"🕓 <strong>Store Closed at {closing_time_str}</strong><br>Because of the holiday, our store will be closed at {closing_time_str} today. Any orders placed after {closing_time_str} will be delivered tomorrow."
            
            return {
                'is_closed': True,
                'closing_hour': hour,
                'closing_minute': minute,
                'closing_time_str': closing_time_str,
                'message': message
            }
    
    return None


def add_holiday_closure(month: int, day: int, year: int, hour: int, minute: int = 0, custom_message: Optional[str] = None) -> None:
    """
    Add a new holiday closure to the configuration.
    
    Args:
        month: Month (1-12)
        day: Day (1-31)
        year: Year (e.g., 2025)
        hour: Closing hour in 24-hour format (0-23)
        minute: Closing minute (default 0)
        custom_message: Optional custom message to override default
    """
    new_closure = (month, day, year, hour, minute, custom_message)
    # Note: In production, this should save to a database
    # For now, we're modifying the module constant which works for development
    HOLIDAY_CLOSURES.append(new_closure)
    print(f"✅ Added holiday closure: {month}/{day}/{year} at {hour:02d}:{minute:02d}")


def get_all_closures() -> list:
    """Get all configured holiday closures"""
    return HOLIDAY_CLOSURES


def clear_past_closures() -> None:
    """Remove past holiday closures (optional cleanup)"""
    today = date.today()
    global HOLIDAY_CLOSURES
    HOLIDAY_CLOSURES = [
        (m, d, y, h, min, msg) for m, d, y, h, min, msg in HOLIDAY_CLOSURES
        if date(y, m, d) >= today
    ]