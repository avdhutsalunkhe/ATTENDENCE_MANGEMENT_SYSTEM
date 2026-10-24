import pytest
from datetime import datetime, date, time
from typing import List

from app.models.attendance import AttendancePunchEvent
from app.services.attendance_service import (
    DEFAULT_SETTINGS,
    check_first_half_start_window,
    check_first_half_end_window,
    check_second_half_start_window,
    check_second_half_end_window,
    evaluate_daily_attendance_rules,
    parse_time_with_seconds,
)


def make_punch(punch_id: int, emp_id: str, ts_str: str) -> AttendancePunchEvent:
    """Helper to construct punch event with explicit seconds."""
    dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
    return AttendancePunchEvent(
        id=punch_id,
        employee_id=emp_id,
        raw_timestamp=ts_str,
        punched_at=dt,
        source_direction="AUTO",
        source_id="TEST"
    )


class TestMiddayBoundaryWindows:
    """
    Boundary tests confirming:
    - 11:59:58 does not qualify for either midday slot.
    - 11:59:59 qualifies for FIRST_HALF_END.
    - 12:30:00 qualifies for FIRST_HALF_END.
    - 12:30:01 qualifies for SECOND_HALF_START.
    - 13:00:00 qualifies for SECOND_HALF_START.
    - 13:00:01 qualifies for neither midday slot.
    """

    def setup_method(self):
        self.fh_end_start = parse_time_with_seconds("11:59:59", time(11, 59, 59))
        self.fh_end_end = parse_time_with_seconds("12:30:00", time(12, 30, 0))
        self.sh_start_start = parse_time_with_seconds("12:30:01", time(12, 30, 1))
        self.sh_start_end = parse_time_with_seconds("13:00:00", time(13, 0, 0))

    def test_11_59_58_qualifies_for_neither_midday_slot(self):
        t = time(11, 59, 58)
        assert check_first_half_end_window(t, self.fh_end_start, self.fh_end_end) is False, (
            "11:59:58 must NOT qualify for FIRST_HALF_END"
        )
        assert check_second_half_start_window(t, self.sh_start_start, self.sh_start_end) is False, (
            "11:59:58 must NOT qualify for SECOND_HALF_START"
        )

    def test_11_59_59_qualifies_for_first_half_end(self):
        t = time(11, 59, 59)
        assert check_first_half_end_window(t, self.fh_end_start, self.fh_end_end) is True, (
            "11:59:59 must qualify for FIRST_HALF_END"
        )
        assert check_second_half_start_window(t, self.sh_start_start, self.sh_start_end) is False

    def test_12_30_00_qualifies_for_first_half_end(self):
        t = time(12, 30, 0)
        assert check_first_half_end_window(t, self.fh_end_start, self.fh_end_end) is True, (
            "12:30:00 must qualify for FIRST_HALF_END"
        )
        assert check_second_half_start_window(t, self.sh_start_start, self.sh_start_end) is False

    def test_12_30_01_qualifies_for_second_half_start(self):
        t = time(12, 30, 1)
        assert check_second_half_start_window(t, self.sh_start_start, self.sh_start_end) is True, (
            "12:30:01 must qualify for SECOND_HALF_START"
        )
        assert check_first_half_end_window(t, self.fh_end_start, self.fh_end_end) is False

    def test_13_00_00_qualifies_for_second_half_start(self):
        t = time(13, 0, 0)
        assert check_second_half_start_window(t, self.sh_start_start, self.sh_start_end) is True, (
            "13:00:00 must qualify for SECOND_HALF_START"
        )
        assert check_first_half_end_window(t, self.fh_end_start, self.fh_end_end) is False

    def test_13_00_01_qualifies_for_neither_midday_slot(self):
        t = time(13, 0, 1)
        assert check_first_half_end_window(t, self.fh_end_start, self.fh_end_end) is False, (
            "13:00:01 must NOT qualify for FIRST_HALF_END"
        )
        assert check_second_half_start_window(t, self.sh_start_start, self.sh_start_end) is False, (
            "13:00:01 must NOT qualify for SECOND_HALF_START"
        )


class TestStartAndEndBoundaryWindows:
    """
    Boundary tests for Slot 1 (FIRST_HALF_START <= 08:14:59 margin of error) and Slot 4 (SECOND_HALF_END > 17:00:00).
    """

    def setup_method(self):
        self.fh_start_cutoff = parse_time_with_seconds("08:14:59", time(8, 14, 59))
        self.sh_end_cutoff = parse_time_with_seconds("17:00:00", time(17, 0, 0))

    def test_first_half_start_cutoff_margin_of_error(self):
        # Through 08:14:59 inclusive
        assert check_first_half_start_window(time(7, 59, 59), self.fh_start_cutoff) is True
        assert check_first_half_start_window(time(8, 0, 0), self.fh_start_cutoff) is True
        assert check_first_half_start_window(time(8, 14, 59), self.fh_start_cutoff) is True
        assert check_first_half_start_window(time(8, 15, 0), self.fh_start_cutoff) is False
        assert check_first_half_start_window(time(8, 15, 1), self.fh_start_cutoff) is False

    def test_second_half_end_cutoff(self):
        # Strictly after 17:00:00
        assert check_second_half_end_window(time(17, 0, 0), self.sh_end_cutoff) is False
        assert check_second_half_end_window(time(17, 0, 1), self.sh_end_cutoff) is True
        assert check_second_half_end_window(time(17, 15, 30), self.sh_end_cutoff) is True


class TestAttendanceClassificationRules:
    """
    Test suite for attendance classification:
    - Both first-half slots satisfied = First Half Present.
    - Both second-half slots satisfied = Second Half Present.
    - Both halves satisfied = Full Day Present (P).
    - Only one half satisfied = Half Day (HD).
    - Neither half satisfied = Absent (A).
    - Distinct biometric event records: A single event must not satisfy multiple punch requirements.
    - Preserve original timestamps including seconds.
    """

    def setup_method(self):
        self.settings = dict(DEFAULT_SETTINGS)

    def test_full_day_present_both_halves_satisfied(self):
        punches = [
            make_punch(1, "EMP001", "2026-09-01 07:50:35"),  # Slot 1 (< 08:00:00)
            make_punch(2, "EMP001", "2026-09-01 12:15:10"),  # Slot 2 (11:59:59 - 12:30:00)
            make_punch(3, "EMP001", "2026-09-01 12:45:45"),  # Slot 3 (12:30:01 - 13:00:00)
            make_punch(4, "EMP001", "2026-09-01 17:05:22"),  # Slot 4 (> 17:00:00)
        ]
        res = evaluate_daily_attendance_rules(punches, self.settings)
        assert res["first_half_present"] is True
        assert res["second_half_present"] is True
        assert res["status"] == "P"
        assert res["missing_punch_flag"] is False
        assert "Full Day Present" in res["remarks"]
        assert "07:50:35" in res["remarks"]
        assert "17:05:22" in res["remarks"]

    def test_half_day_first_half_only_satisfied(self):
        punches = [
            make_punch(1, "EMP002", "2026-09-01 07:45:00"),  # Slot 1 satisfied
            make_punch(2, "EMP002", "2026-09-01 12:20:00"),  # Slot 2 satisfied (11:59:59 - 12:30:00)
            # Second half missing
        ]
        res = evaluate_daily_attendance_rules(punches, self.settings)
        assert res["first_half_present"] is True
        assert res["second_half_present"] is False
        assert res["status"] == "HD"
        assert res["missing_punch_flag"] is True
        assert "Half Day: First Half Present" in res["remarks"]

    def test_half_day_second_half_only_satisfied(self):
        punches = [
            # First half missing
            make_punch(1, "EMP003", "2026-09-01 12:48:30"),  # Slot 3 satisfied (12:30:01 - 13:00:00)
            make_punch(2, "EMP003", "2026-09-01 17:10:05"),  # Slot 4 satisfied (> 17:00:00)
        ]
        res = evaluate_daily_attendance_rules(punches, self.settings)
        assert res["first_half_present"] is False
        assert res["second_half_present"] is True
        assert res["status"] == "HD"
        assert res["missing_punch_flag"] is True
        assert "Half Day: Second Half Present" in res["remarks"]

    def test_absent_neither_half_satisfied_with_unmatched_punches(self):
        # Punches at 09:15:00 and 15:00:00 (outside all 4 required slots)
        punches = [
            make_punch(1, "EMP004", "2026-09-01 09:15:00"),
            make_punch(2, "EMP004", "2026-09-01 15:00:00"),
        ]
        res = evaluate_daily_attendance_rules(punches, self.settings)
        assert res["first_half_present"] is False
        assert res["second_half_present"] is False
        assert res["status"] == "A"
        assert res["missing_punch_flag"] is True
        assert "Absent: Neither half satisfied" in res["remarks"]

    def test_absent_no_punches_on_workday(self):
        punches = []
        res = evaluate_daily_attendance_rules(punches, self.settings, is_weekend=False)
        assert res["status"] == "A"
        assert res["first_half_present"] is False
        assert res["second_half_present"] is False
        assert "Absent: No biometric punches" in res["remarks"]

    def test_weekly_off_no_punches_on_weekend(self):
        punches = []
        res = evaluate_daily_attendance_rules(punches, self.settings, is_weekend=True)
        assert res["status"] == "WO"
        assert res["remarks"] == "Weekly Off"

    def test_distinct_events_requirement_cannot_reuse_punch(self):
        """
        Confirm that a single biometric event cannot satisfy multiple slot requirements.
        Even if an event were near a boundary, distinct event tracking guarantees 1-to-1 matching.
        """
        # Only 1 punch at 07:45:00 (matches Slot 1 only, cannot satisfy Slot 2)
        punches = [
            make_punch(1, "EMP005", "2026-09-01 07:45:00"),
        ]
        res = evaluate_daily_attendance_rules(punches, self.settings)
        # Cannot be first half present with only 1 punch
        assert res["first_half_present"] is False
        assert res["status"] == "A"


class TestDatabaseAndSettingsIntegration:
    """
    Tests checking database persistence of configurable punch windows
    and full end-to-end punch processing into DailyAttendance records.
    """

    def setup_method(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.base import Base

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def teardown_method(self):
        self.db.close()

    def test_settings_persistence_and_configuration(self):
        from app.services.attendance_service import get_settings, save_settings

        # Initial settings include 4 windows defaults
        init_s = get_settings(self.db)
        assert init_s["first_half_start_cutoff"] == "08:14:59"
        assert init_s["first_half_end_start"] == "11:59:59"
        assert init_s["first_half_end_end"] == "12:30:00"
        assert init_s["second_half_start_start"] == "12:30:01"
        assert init_s["second_half_start_end"] == "13:00:00"
        assert init_s["second_half_end_cutoff"] == "17:00:00"

        # Update windows
        updated = save_settings(self.db, {
            "first_half_start_cutoff": "08:15:00",
            "first_half_end_start": "12:00:00",
            "first_half_end_end": "12:35:00",
            "second_half_start_start": "12:36:00",
            "second_half_start_end": "13:10:00",
            "second_half_end_cutoff": "17:30:00"
        })
        assert updated["first_half_start_cutoff"] == "08:15:00"
        assert updated["first_half_end_start"] == "12:00:00"
        assert updated["first_half_end_end"] == "12:35:00"

        # Verify retrieved from DB
        fetched = get_settings(self.db)
        assert fetched["first_half_start_cutoff"] == "08:15:00"
        assert fetched["first_half_end_start"] == "12:00:00"

    def test_process_punches_for_date_end_to_end(self):
        from app.models.employee import Employee
        from app.models.attendance import DailyAttendance
        from app.services.attendance_service import process_punches_for_date

        # Create active employee
        emp = Employee(id="EMP999", name="Test Worker", department="IT", designation="Engineer", status="Active")
        self.db.add(emp)
        self.db.commit()

        target_date = date(2026, 9, 2) # Wednesday

        # Add 4 qualifying punches with full seconds
        p1 = AttendancePunchEvent(employee_id="EMP999", raw_timestamp="2026-09-02 07:45:15", punched_at=datetime(2026, 9, 2, 7, 45, 15))
        p2 = AttendancePunchEvent(employee_id="EMP999", raw_timestamp="2026-09-02 12:15:40", punched_at=datetime(2026, 9, 2, 12, 15, 40))
        p3 = AttendancePunchEvent(employee_id="EMP999", raw_timestamp="2026-09-02 12:45:10", punched_at=datetime(2026, 9, 2, 12, 45, 10))
        p4 = AttendancePunchEvent(employee_id="EMP999", raw_timestamp="2026-09-02 17:15:55", punched_at=datetime(2026, 9, 2, 17, 15, 55))
        self.db.add_all([p1, p2, p3, p4])
        self.db.commit()

        count = process_punches_for_date(self.db, target_date)
        assert count == 1

        record = self.db.query(DailyAttendance).filter_by(employee_id="EMP999").first()
        assert record is not None
        assert record.attendance_status == "P"
        assert record.punch_count == 4
        # Seconds are preserved in first_valid_in_at and last_valid_out_at
        assert record.first_valid_in_at == datetime(2026, 9, 2, 7, 45, 15)
        assert record.last_valid_out_at == datetime(2026, 9, 2, 17, 15, 55)
        assert "Full Day Present" in record.remarks
        assert "07:45:15" in record.remarks
        assert "17:15:55" in record.remarks

