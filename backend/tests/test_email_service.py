import pytest
from datetime import time

from app.services.email_service import compute_next_send


def test_compute_next_send_daily():
    result = compute_next_send({"frequency": "daily", "send_time": "09:00"})
    assert result is not None


def test_compute_next_send_weekly():
    result = compute_next_send({
        "frequency": "weekly",
        "send_time": time(9, 0),
        "day_of_week": 1,
    })
    assert result is not None
