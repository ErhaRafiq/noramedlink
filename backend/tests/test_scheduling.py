"""Availability, slots, booking rules, reviews and notifications (Module 5), on a throwaway in-memory
SQLite database. Times are clinic time (UTC+5)."""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import Appointment, DoctorAvailability, DoctorProfile, Notification, PatientProfile, User
from routers.appointments import doctor_to_out, filter_doctors
from services import appointments as booking
from services import notifications, scheduling
from services.scheduling import CLINIC_TZ, WindowInput

# A Monday far from "now", so the test never depends on today's date.
NOW = datetime(2030, 1, 6, 4, 0, tzinfo=UTC)  # Sunday 09:00 clinic time
MONDAY = date(2030, 1, 7)


def clinic(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=CLINIC_TZ).astimezone(UTC)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(scheduling, "now_utc", lambda: NOW)
    monkeypatch.setattr(booking, "datetime", type("D", (datetime,), {"now": staticmethod(lambda tz=None: NOW)}))
    monkeypatch.setattr(notifications, "datetime", type("D", (datetime,), {"now": staticmethod(lambda tz=None: NOW)}))
    with sessionmaker(bind=engine)() as session:
        yield session


def make_user(db, name: str, role: str) -> User:
    user = User(full_name=name, email=f"{name.lower().replace(' ', '')}@test.com", hashed_password="x", role=role,
                phone=f"0300{abs(hash(name)) % 10**7}", is_active=True)  # fmt: skip
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def doctor(db):
    user = make_user(db, "Doc Tor", "DOCTOR")
    db.add(DoctorProfile(user_id=user.id, pmdc_number="1", specialization="Cardiology", hospital_name="H",
                         verification_status="approved", consultation_modes="in_clinic,online"))  # fmt: skip
    scheduling.save_windows(db, user.id, [WindowInput(0, time(9), time(11), 30)])  # Mondays 09:00-11:00
    db.refresh(user)
    return user


@pytest.fixture
def patient(db):
    user = make_user(db, "Pat Ient", "PATIENT")
    db.add(PatientProfile(user_id=user.id, cnic="12345-1234567-1", date_of_birth=date(1990, 1, 1), gender="Male"))
    db.commit()
    return user


# --- slots --------------------------------------------------------------------------------------


def test_a_window_is_cut_into_slots_and_a_taken_one_is_closed(db, doctor):
    [(_, slots)] = scheduling.slots_range(db, doctor.id, MONDAY, 1, now=NOW)
    assert [s.start for s in slots] == [
        clinic(MONDAY, 9),
        clinic(MONDAY, 9, 30),
        clinic(MONDAY, 10),
        clinic(MONDAY, 10, 30),
    ]
    assert all(s.available and s.minutes == 30 for s in slots)


def test_other_weekdays_have_no_slots(db, doctor):
    [(_, slots)] = scheduling.slots_range(db, doctor.id, date(2030, 1, 8), 1, now=NOW)
    assert slots == []


def test_slots_that_are_too_soon_or_too_far_are_closed():
    window = DoctorAvailability(weekday=0, start_time=time(9), end_time=time(10), slot_minutes=30)
    soon = clinic(MONDAY, 9) - timedelta(minutes=10)  # now is 10 minutes before the first slot
    slots = scheduling.day_slots([window], MONDAY, [], soon)
    assert [s.available for s in slots] == [False, True]
    far = scheduling.day_slots([window], MONDAY, [], clinic(MONDAY, 9) - timedelta(days=scheduling.HORIZON_DAYS + 5))
    assert not any(s.available for s in far)


def test_a_booked_slot_stays_visible_but_closed(db, doctor, patient):
    booking.create(db, patient, doctor, clinic(MONDAY, 9, 30), "in_clinic", None, None)
    db.commit()
    [(_, slots)] = scheduling.slots_range(db, doctor.id, MONDAY, 1, now=NOW)
    assert [s.available for s in slots] == [True, False, True, True]


def test_a_cancelled_booking_frees_its_slot(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    booking.cancel(db, appointment, patient, by_doctor=False)
    db.commit()
    assert scheduling.find_open_slot(db, doctor.id, clinic(MONDAY, 9)).available


# --- the weekly schedule ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "windows",
    [
        [WindowInput(7, time(9), time(10), 30)],
        [WindowInput(0, time(10), time(9), 30)],
        [WindowInput(0, time(9), time(9, 20), 30)],
        [WindowInput(0, time(9), time(10), 25)],
        [WindowInput(0, time(9), time(11), 30), WindowInput(0, time(10), time(12), 30)],
        [WindowInput(0, time(h), time(h, 30), 30) for h in range(8, 13)],
    ],
)
def test_bad_schedules_are_refused(db, doctor, windows):
    with pytest.raises(HTTPException) as caught:
        scheduling.save_windows(db, doctor.id, windows)
    assert caught.value.status_code == 422


def test_a_refused_schedule_leaves_the_old_one_alone(db, doctor):
    with pytest.raises(HTTPException):
        scheduling.save_windows(db, doctor.id, [WindowInput(0, time(10), time(9), 30)])
    assert db.query(DoctorAvailability).filter_by(doctor_id=doctor.id).count() == 1


def test_changing_the_schedule_keeps_existing_appointments(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    scheduling.save_windows(db, doctor.id, [WindowInput(1, time(14), time(15), 30)])  # now Tuesdays only
    assert db.get(Appointment, appointment.id).status == "BOOKED"


def test_adjacent_windows_are_allowed(db, doctor):
    scheduling.save_windows(
        db, doctor.id, [WindowInput(0, time(9), time(10), 30), WindowInput(0, time(10), time(11), 30)]
    )


# --- booking ------------------------------------------------------------------------------------


def test_booking_an_open_slot_records_the_visit_and_notifies_both(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 10), "online", "Chest pain follow-up", None)
    db.commit()
    assert (appointment.status, appointment.duration_minutes, appointment.mode) == ("BOOKED", 30, "online")
    kinds = {(n.user_id, n.kind) for n in db.query(Notification)}
    assert (patient.id, "appointment_confirmed") in kinds and (doctor.id, "appointment_confirmed") in kinds


@pytest.mark.parametrize(
    "start", [clinic(MONDAY, 9, 10), clinic(MONDAY, 8), clinic(MONDAY, 11), clinic(date(2030, 1, 8), 9)]
)
def test_a_time_that_is_not_a_slot_is_refused(db, doctor, patient, start):
    with pytest.raises(HTTPException) as caught:
        booking.create(db, patient, doctor, start, "in_clinic", None, None)
    assert caught.value.status_code == 409


def test_the_same_slot_cannot_be_booked_twice(db, doctor, patient):
    other = make_user(db, "Other Pat", "PATIENT")
    booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    with pytest.raises(HTTPException) as caught:
        booking.create(db, other, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    assert caught.value.status_code == 409 and "taken" in caught.value.detail


def test_the_database_itself_refuses_a_double_booking(db, doctor, patient):
    """Even if the check above were skipped (two requests racing), the unique index stops the second."""
    booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    db.add(
        Appointment(user_id=patient.id, doctor_id=doctor.id, doctor_name="x", date=clinic(MONDAY, 9), status="BOOKED")
    )
    with pytest.raises(HTTPException) as caught:
        booking.flush_or_conflict(db)
    assert caught.value.status_code == 409


def test_a_patient_cannot_be_in_two_places_at_once(db, doctor, patient):
    second = make_user(db, "Second Doc", "DOCTOR")
    db.add(DoctorProfile(user_id=second.id, pmdc_number="2", specialization="ENT", hospital_name="H",
                         verification_status="approved", consultation_modes="in_clinic"))  # fmt: skip
    scheduling.save_windows(db, second.id, [WindowInput(0, time(9), time(11), 30)])
    db.refresh(second)
    booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    with pytest.raises(HTTPException) as caught:
        booking.create(db, patient, second, clinic(MONDAY, 9), "in_clinic", None, None)
    assert caught.value.status_code == 409 and "already have an appointment" in caught.value.detail


def test_a_consultation_type_the_doctor_does_not_offer_is_refused(db, doctor, patient):
    with pytest.raises(HTTPException) as caught:
        booking.create(db, patient, doctor, clinic(MONDAY, 9), "home", None, None)
    assert caught.value.status_code == 422


def test_a_doctor_without_a_schedule_cannot_be_booked(db, patient):
    bare = make_user(db, "No Schedule", "DOCTOR")
    db.add(DoctorProfile(user_id=bare.id, pmdc_number="3", specialization="ENT", hospital_name="H",
                         verification_status="approved", consultation_modes="in_clinic"))  # fmt: skip
    db.commit()
    db.refresh(bare)
    with pytest.raises(HTTPException):
        booking.create(db, patient, bare, clinic(MONDAY, 9), "in_clinic", None, None)


# --- rescheduling, cancelling, finishing --------------------------------------------------------


def test_rescheduling_moves_the_booking_and_its_reminders(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    booking.reschedule(db, appointment, clinic(MONDAY, 10, 30), patient)
    db.commit()
    assert appointment.date.replace(tzinfo=UTC) == clinic(MONDAY, 10, 30)
    assert db.query(Notification).filter_by(kind="appointment_rescheduled").count() == 2
    due = sorted(
        n.scheduled_for.replace(tzinfo=UTC) for n in db.query(Notification).filter_by(kind="appointment_reminder")
    )
    # Both people get a 24-hour and a 1-hour reminder before the NEW time; none is left for the old one.
    assert due == sorted(
        [clinic(MONDAY, 10, 30) - timedelta(hours=24)] * 2 + [clinic(MONDAY, 10, 30) - timedelta(hours=1)] * 2
    )
    assert scheduling.find_open_slot(db, doctor.id, clinic(MONDAY, 9)).available  # the old slot is free again


def test_a_booking_can_move_to_a_slot_that_overlaps_its_own_old_time(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    booking.reschedule(db, appointment, clinic(MONDAY, 9), patient)  # to itself: allowed, nothing else is in the way


def test_moving_onto_a_taken_slot_is_refused(db, doctor, patient):
    other = make_user(db, "Other Pat", "PATIENT")
    booking.create(db, other, doctor, clinic(MONDAY, 10), "in_clinic", None, None)
    mine = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    with pytest.raises(HTTPException):
        booking.reschedule(db, mine, clinic(MONDAY, 10), patient)


def test_nothing_changes_once_an_appointment_is_final(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    booking.cancel(db, appointment, patient, by_doctor=False)
    for action in (
        lambda: booking.cancel(db, appointment, patient, by_doctor=False),
        lambda: booking.reschedule(db, appointment, clinic(MONDAY, 10), patient),
    ):
        with pytest.raises(HTTPException) as caught:
            action()
        assert caught.value.status_code == 409


def test_cancelling_tells_the_other_side(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    booking.cancel(db, appointment, patient, by_doctor=True)
    db.commit()
    text = {(n.user_id, n.title) for n in db.query(Notification).filter_by(kind="appointment_cancelled")}
    assert text == {(patient.id, "Appointment cancelled")}
    assert db.query(Notification).filter_by(kind="appointment_reminder").count() == 0  # reminders removed


def test_only_a_visit_that_has_started_can_be_completed(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    with pytest.raises(HTTPException) as caught:
        booking.finish(db, appointment, "COMPLETED")
    assert caught.value.status_code == 409
    appointment.date = NOW - timedelta(hours=1)
    assert booking.finish(db, appointment, "COMPLETED").status == "COMPLETED"


def test_a_patient_cannot_cancel_a_visit_that_has_started(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    appointment.date = NOW - timedelta(minutes=5)
    with pytest.raises(HTTPException):
        booking.cancel(db, appointment, patient, by_doctor=False)
    assert booking.cancel(db, appointment, patient, by_doctor=True).status == "CANCELLED"  # the doctor still can


# --- reviews and directory ----------------------------------------------------------------------


def test_only_a_completed_visit_can_be_rated_and_only_once(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    with pytest.raises(HTTPException):
        booking.create_review(db, appointment, 5, None)
    appointment.date, appointment.status = NOW - timedelta(hours=1), "COMPLETED"
    booking.create_review(db, appointment, 4, "Kind and clear")
    db.commit()
    with pytest.raises(HTTPException) as caught:
        booking.create_review(db, appointment, 1, None)
    assert caught.value.status_code == 409
    assert booking.ratings_for(db, [doctor.id]) == {doctor.id: (4.0, 1)}


def test_the_directory_shows_real_ratings_and_the_next_open_slot(db, doctor):
    [info] = [doctor_to_out(doctor, None, scheduling.directory_availability(db, [doctor.id], NOW)[doctor.id], True)]
    assert info.rating is None and info.rating_count == 0  # never an invented rating
    assert info.next_available == clinic(MONDAY, 9) and info.available_today is False
    on_monday = scheduling.directory_availability(db, [doctor.id], clinic(MONDAY, 7))[doctor.id]
    assert on_monday == (True, clinic(MONDAY, 9))


def test_filters_and_sorting():
    def card(name, fee, rating, city="Lahore", modes=("in_clinic",), exp=None, today=False):
        from schemas import AppointmentDoctorOut

        return AppointmentDoctorOut(id=1, doctor_id=1, name=name, specialty="Cardiology", location="H", city=city,
                                    consultation_fee=fee, rating=rating, rating_count=1 if rating else 0,
                                    consultation_modes=list(modes), experience_years=exp, available_today=today)  # fmt: skip

    cards = [
        card("A", 3000, 4.5, exp=5),
        card("B", 1000, None, "Karachi", ("online",), 20, True),
        card("C", None, 5.0, exp=1),
    ]
    names = lambda result: [c.name for c in result]  # noqa: E731
    assert names(filter_doctors(cards, sort="fee")) == ["B", "A", "C"]  # no fee sorts last
    assert names(filter_doctors(cards, sort="rating")) == ["C", "A", "B"]
    assert names(filter_doctors(cards, sort="experience")) == ["B", "A", "C"]
    assert names(filter_doctors(cards, max_fee=2000)) == ["B"]  # an unset fee is not "cheap"
    assert names(filter_doctors(cards, min_rating=4.6)) == ["C"]  # unrated is not "high"
    assert names(filter_doctors(cards, city="karachi")) == ["B"]
    assert names(filter_doctors(cards, mode="online")) == ["B"]
    assert names(filter_doctors(cards, available_today=True)) == ["B"]
    assert names(filter_doctors(cards, query="zzz")) == []


# --- notifications ------------------------------------------------------------------------------


def test_times_are_written_in_clinic_time():
    assert notifications.when_text(datetime(2030, 1, 7, 4, 30, tzinfo=UTC)) == "Mon 7 Jan, 9:30 AM"
    assert notifications.when_text(datetime(2030, 1, 7, 12, 0, tzinfo=UTC)) == "Mon 7 Jan, 5:00 PM"


def test_reminders_are_hidden_until_due_and_removed_when_the_visit_moves(db, doctor, patient):
    appointment = booking.create(db, patient, doctor, clinic(MONDAY, 9), "in_clinic", None, None)
    db.commit()
    reminders = db.query(Notification).filter_by(kind="appointment_reminder", user_id=patient.id).all()
    assert len(reminders) == 1  # the 24-hour one is already in the past at NOW (Sunday 09:00); 1 hour is ahead
    visible = {n.kind for n in notifications.due_for(db, patient.id)}
    assert "appointment_confirmed" in visible and "appointment_reminder" not in visible
    notifications.clear_reminders(db, appointment.id)
    assert db.query(Notification).filter_by(kind="appointment_reminder").count() == 0
