"""Module 6 rules: state machine, distance, coordinates, the emergency gate, ranking and offer windows."""

import itertools
import math
from datetime import UTC, datetime, timedelta

import pytest

from services.home_visits import gate, geo, matching, offers, states, suitability
from services.home_visits.matching import AVAILABLE_NOW, AVAILABLE_SOON, Candidate
from services.symptom_checker import EMERGENCY_NOTICE

# ---- state machine ---------------------------------------------------------------------------------------------

ACTORS = (states.PATIENT, states.DOCTOR, states.SYSTEM)


@pytest.mark.parametrize(("current", "target", "actor"), list(itertools.product(states.STATES, states.STATES, ACTORS)))
def test_every_pair_of_states_and_actors(current, target, actor):
    """All 11 x 11 x 3 combinations: allowed exactly when the table says so, an error otherwise."""
    allowed = current not in states.TERMINAL and actor in states.TRANSITIONS.get((current, target), frozenset())
    assert states.can_transition(current, target, actor) == (actor in states.TRANSITIONS.get((current, target), ()))
    if allowed:
        assert states.transition(current, target, actor) == target
    else:
        with pytest.raises(states.InvalidTransition):
            states.transition(current, target, actor)


def test_the_happy_path_runs_in_order():
    path = [states.OFFERED, states.ACCEPTED, states.EN_ROUTE, states.ARRIVED, states.COMPLETED, states.CLOSED]
    for a, b in itertools.pairwise(path):
        assert states.transition(a, b, states.DOCTOR) == b


def test_a_step_cannot_be_skipped_or_reversed():
    for current, target in [
        (states.OFFERED, states.EN_ROUTE),
        (states.ACCEPTED, states.ARRIVED),
        (states.EN_ROUTE, states.COMPLETED),
        (states.ARRIVED, states.CLOSED),
        (states.ARRIVED, states.EN_ROUTE),
        (states.ARRIVED, states.OFFERED),
        (states.COMPLETED, states.OFFERED),
        (states.OFFERED, states.OFFERED),
    ]:
        assert not states.can_transition(current, target, states.DOCTOR)


def test_terminal_states_never_move_again():
    for end in states.TERMINAL:
        for target in states.STATES:
            for actor in ACTORS:
                assert not states.can_transition(end, target, actor)


def test_only_the_system_ends_a_request_by_timeout_or_no_doctor():
    for target in (states.EXPIRED, states.NO_DOCTOR_FOUND):
        assert states.can_transition(states.OFFERED, target, states.SYSTEM)
        assert not states.can_transition(states.OFFERED, target, states.DOCTOR)
        assert not states.can_transition(states.OFFERED, target, states.PATIENT)


def test_a_patient_cannot_accept_or_advance_a_visit():
    for target in (states.ACCEPTED, states.EN_ROUTE, states.ARRIVED, states.COMPLETED, states.CLOSED):
        assert not any(states.can_transition(s, target, states.PATIENT) for s in states.STATES)


def test_a_doctor_can_refer_to_emergency_care_from_every_live_state_but_a_patient_cannot():
    for live in states.ACTIVE:
        assert states.can_transition(live, states.REFERRED_EMERGENCY, states.DOCTOR)
        assert not states.can_transition(live, states.REFERRED_EMERGENCY, states.PATIENT)


def test_a_patient_cannot_cancel_once_the_doctor_arrived():
    assert states.can_transition(states.EN_ROUTE, states.CANCELLED, states.PATIENT)
    assert not states.can_transition(states.ARRIVED, states.CANCELLED, states.PATIENT)


def test_every_state_has_a_timestamp_column_and_a_label():
    assert set(states.TIMESTAMP_FIELD) == set(states.STATES) == set(states.LABELS)
    from models import HomeVisitRequest

    assert set(states.TIMESTAMP_FIELD.values()) <= set(HomeVisitRequest.__table__.columns.keys())


def test_unknown_states_are_refused():
    with pytest.raises(states.InvalidTransition):
        states.transition("offered", "flying", states.DOCTOR)


# ---- a doctor cancels ------------------------------------------------------------------------------------------


def test_a_doctor_who_cancels_before_arriving_sends_the_request_back_to_matching():
    for before in (states.ACCEPTED, states.EN_ROUTE):
        assert states.doctor_cancel_target(before) == states.OFFERED
        assert states.can_transition(before, states.OFFERED, states.DOCTOR)
        assert states.transition(before, states.OFFERED, states.DOCTOR) == states.OFFERED
        # and nobody else can send it back
        assert not states.can_transition(before, states.OFFERED, states.PATIENT)
        assert not states.can_transition(before, states.OFFERED, states.SYSTEM)
        # a doctor's cancel never ends the request by itself before arrival
        assert not states.can_transition(before, states.CANCELLED, states.DOCTOR)


def test_a_doctor_who_cancels_after_arriving_ends_the_visit():
    assert states.doctor_cancel_target(states.ARRIVED) == states.CANCELLED
    assert states.transition(states.ARRIVED, states.CANCELLED, states.DOCTOR) == states.CANCELLED
    assert not states.can_transition(states.ARRIVED, states.OFFERED, states.DOCTOR)


def test_a_doctor_cannot_cancel_a_visit_that_is_finished_or_not_theirs_yet():
    for state in (states.OFFERED, states.COMPLETED, states.CLOSED, states.CANCELLED, states.REFERRED_EMERGENCY):
        with pytest.raises(states.InvalidTransition):
            states.doctor_cancel_target(state)


def test_the_patient_can_still_cancel_until_the_doctor_arrives():
    for state in (states.ACCEPTED, states.EN_ROUTE):
        assert states.can_transition(state, states.CANCELLED, states.PATIENT)


def test_the_cancel_reasons_are_fixed_choices_with_words_for_the_audit_log():
    assert set(states.CANCEL_REASONS) == {"unwell", "urgent_elsewhere", "too_far", "patient_unreachable", "other"}
    assert all(text == text.strip() and text for text in states.CANCEL_REASONS.values())


def test_after_a_doctor_cancels_the_next_ranked_doctor_is_offered_never_the_one_who_cancelled():
    ranked = ranked_of(4)  # doctors 1 to 4, best first
    cancelled = {1}  # doctor 1 accepted, then cancelled: their offer is on record
    following = offers.next_candidate(ranked, cancelled)
    assert following.doctor_id == 2
    # even if everyone else is tried and doctor 1 is still the best-ranked, they are not offered again
    assert offers.next_candidate(ranked, {2, 3, 4, 1}) is None
    assert offers.next_candidate(ranked[:1], {1}) is None


def test_the_five_offers_include_the_doctor_who_cancelled():
    ranked = ranked_of(8)
    tried = {1, 2, 3, 4}  # four offered so far, the fourth accepted and then cancelled
    assert offers.next_candidate(ranked, tried).doctor_id == 5
    assert offers.next_candidate(ranked, tried | {5}) is None  # five offers in all, then "no doctor found"


# ---- distance and coordinates ----------------------------------------------------------------------------------

F10 = (33.6938, 73.0129)
BLUE_AREA = (33.7100, 73.0551)


def test_haversine_known_distances():
    assert geo.haversine_km(*F10, *F10) == 0
    # one degree of latitude is about 111.2 km
    assert geo.haversine_km(0, 0, 1, 0) == pytest.approx(111.195, abs=0.05)
    # Islamabad to Lahore is about 270 km in a straight line
    assert geo.haversine_km(33.6844, 73.0479, 31.5204, 74.3587) == pytest.approx(268, abs=5)
    # across the date line and over the pole the answer stays sensible
    assert geo.haversine_km(0, 179.5, 0, -179.5) == pytest.approx(111.195, abs=0.05)
    assert geo.haversine_km(89, 0, 89, 180) == pytest.approx(222.39, abs=0.1)


def test_haversine_is_symmetric_and_never_negative():
    a = geo.haversine_km(*F10, *BLUE_AREA)
    assert a == pytest.approx(geo.haversine_km(*BLUE_AREA, *F10))
    assert 0 < a < 10


@pytest.mark.parametrize(
    ("km", "rounded"),
    [(0, 0), (0.24, 0), (0.25, 0.5), (0.74, 0.5), (0.75, 1.0), (3.2, 3.0), (3.26, 3.5), (12.9, 13.0)],
)
def test_distance_rounds_to_half_a_km(km, rounded):
    assert geo.round_to_half_km(km) == rounded


def test_distance_wording_says_straight_line_and_never_road_or_travel():
    assert geo.distance_label(3.2) == "straight-line distance, about 3 km"
    assert geo.distance_label(3.3) == "straight-line distance, about 3.5 km"
    assert geo.distance_label(0.1) == "straight-line distance, less than 0.5 km"
    for km in (0.1, 2, 9.9):
        text = geo.distance_label(km).lower()
        assert "straight-line" in text and "road" not in text and "travel" not in text and "minute" not in text


@pytest.mark.parametrize(
    ("lat", "lon"), [(0, 0), (90, 180), (-90, -180), (33.69, 73.01), ("33.69", "73.01"), (33, -73)]
)
def test_valid_coordinates_are_accepted(lat, lon):
    assert geo.validate_coordinates(lat, lon) == (float(lat), float(lon))


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (90.0001, 0),
        (-90.0001, 0),
        (0, 180.0001),
        (0, -180.0001),
        (None, 5),
        (5, None),
        ("north", "east"),
        ("", ""),
        (math.nan, 5),
        (5, math.inf),
        (float("-inf"), 0),
    ],
)
def test_invalid_coordinates_are_refused(lat, lon):
    with pytest.raises(geo.InvalidLocation):
        geo.validate_coordinates(lat, lon)


def test_accuracy_validation_and_wording():
    assert geo.validate_accuracy(None) is None
    assert geo.validate_accuracy("120") == 120.0
    for bad in (-1, math.nan, math.inf, "wide", 100_001):
        with pytest.raises(geo.InvalidLocation):
            geo.validate_accuracy(bad)
    assert geo.accuracy_label(120) == "accurate to about 120 m"
    assert geo.accuracy_label(2500) == "accurate to about 2.5 km"
    assert geo.accuracy_label(None) == "Typed by you"


# ---- suitability -----------------------------------------------------------------------------------------------


def test_suitability_table():
    assert suitability.is_suitable("General Physician") and suitability.suitability("General Physician") == 1.0
    assert suitability.is_suitable("Pediatrician")
    for clinic_only in ("Cardiologist", "Neurologist", "Pulmonologist", "Orthopedic Specialist", "Dentist"):
        assert not suitability.is_suitable(clinic_only) and suitability.suitability(clinic_only) == 0.0
        assert suitability.note(clinic_only)
    assert not suitability.is_suitable("Not a specialty") and not suitability.is_suitable(None)


@pytest.mark.parametrize(
    ("listed", "expected"),
    [
        ("General Physician", "General Physician"),
        ("Consultant Physician", "General Physician"),
        ("Dentist", "Dentist"),
        ("Pediatric Specialist", "Pediatrician"),
        ("Consultant Gastroenterologist", "Gastroenterologist"),
        ("Cardiologist", "Cardiologist"),
        ("Astrologer", None),
        ("", None),
        (None, None),
    ],
)
def test_a_listed_specialty_resolves_to_the_table(listed, expected):
    assert suitability.specialty_of(listed) == expected


# ---- the emergency gate ----------------------------------------------------------------------------------------

ALL_NO = {q["id"]: False for q in gate.checklist()}


def test_a_red_flag_in_the_reason_blocks_the_request():
    result = gate.assess("I have chest pain since morning", ALL_NO)
    assert result.status == gate.EMERGENCY and not result.allowed
    assert result.message == EMERGENCY_NOTICE and result.red_flags and result.specialty is None


def test_one_yes_on_the_checklist_blocks_the_request():
    for qid in ALL_NO:
        result = gate.assess("mild cough and sore throat", {**ALL_NO, qid: True})
        assert result.status == gate.EMERGENCY and result.checklist_yes == [qid]
        assert result.message == EMERGENCY_NOTICE


def test_an_emergency_is_reported_even_when_other_answers_are_missing():
    assert gate.assess("cannot breathe", {}).status == gate.EMERGENCY


def test_a_negated_warning_sign_does_not_block():
    assert gate.assess("fever, no chest pain, mild cough", ALL_NO).status == gate.CLEAR


def test_missing_answers_or_reason_are_incomplete_not_clear():
    partial = dict(list(ALL_NO.items())[:-1])
    result = gate.assess("mild fever and cough", partial)
    assert result.status == gate.INCOMPLETE and result.unanswered == [list(ALL_NO)[-1]]
    assert gate.assess("", ALL_NO).status == gate.INCOMPLETE
    assert gate.assess("   ", ALL_NO).status == gate.INCOMPLETE
    assert gate.assess("mild fever", {**ALL_NO, "HC-01": None}).status == gate.INCOMPLETE


def test_a_mild_everyday_reason_is_clear_and_matched():
    result = gate.assess("mild fever and a cold for two days", ALL_NO)
    assert result.allowed and result.specialty == "General Physician" and result.message == ""


def test_a_reason_for_a_clinic_only_specialty_points_to_a_clinic_visit():
    result = gate.assess("my knee joint pain and swelling after walking", ALL_NO)
    assert result.status == gate.NOT_SUITABLE and result.specialty == "Orthopedic Specialist"
    assert "appointment" in result.message and not result.allowed


def test_the_checklist_has_every_question_once():
    items = gate.checklist()
    assert len(items) == len({q["id"] for q in items}) == len({q["question"] for q in items}) >= 10


# ---- ranking ---------------------------------------------------------------------------------------------------


def doc(
    doctor_id,
    lat=33.6938,
    lon=73.0129,
    specialty="General Physician",
    radius=10.0,
    availability=AVAILABLE_NOW,
    busy=False,
):
    return Candidate(doctor_id, specialty, lat, lon, radius, availability, busy)


def test_the_weights_come_from_the_table_and_sum_to_one():
    assert matching.weights() == {"proximity": 0.4, "specialty": 0.25, "availability": 0.2, "suitability": 0.15}
    assert sum(matching.weights().values()) == pytest.approx(1.0)


def test_a_nearer_doctor_ranks_higher_all_else_equal():
    near = doc(1, 33.6950, 73.0140)
    far = doc(2, 33.7300, 73.0700)
    ranked = matching.rank([far, near], *F10, "General Physician")
    assert [r.doctor_id for r in ranked] == [1, 2]
    assert ranked[0].distance_km < ranked[1].distance_km and ranked[0].score > ranked[1].score


def test_the_exact_specialty_beats_a_general_physician_at_the_same_place():
    ranked = matching.rank([doc(1), doc(2, specialty="Dermatologist")], *F10, "Dermatologist")
    assert [r.doctor_id for r in ranked] == [2, 1]
    assert ranked[0].parts["specialty"] == 1.0 and ranked[1].parts["specialty"] == 0.5


def test_a_doctor_of_another_specialty_is_not_offered():
    assert matching.rank([doc(1, specialty="Dermatologist")], *F10, "Pediatrician") == []


def test_a_clinic_only_specialty_is_never_offered_even_if_it_matches_the_reason():
    assert matching.rank([doc(1, specialty="Cardiologist")], *F10, "Cardiologist") == []


def test_available_now_beats_available_soon():
    ranked = matching.rank([doc(1, availability=AVAILABLE_SOON), doc(2)], *F10, "General Physician")
    assert [r.doctor_id for r in ranked] == [2, 1]


def test_no_hours_today_or_a_visit_in_progress_means_not_offered():
    assert matching.rank([doc(1, availability="none"), doc(2, busy=True)], *F10, "General Physician") == []


def test_outside_the_service_radius_or_with_no_base_is_not_offered():
    far = doc(1, 33.8, 73.2, radius=5)
    no_base = Candidate(2, "General Physician", None, None, 10, AVAILABLE_NOW)
    no_radius = Candidate(3, "General Physician", *F10, None, AVAILABLE_NOW)
    zero_radius = doc(4, radius=0)
    assert matching.rank([far, no_base, no_radius, zero_radius], *F10, "General Physician") == []


def test_the_radius_edge_is_inclusive():
    edge = geo.haversine_km(*F10, *BLUE_AREA)
    assert [r.doctor_id for r in matching.rank([doc(1, *BLUE_AREA, radius=edge)], *F10, "General Physician")] == [1]
    assert matching.rank([doc(1, *BLUE_AREA, radius=edge - 0.001)], *F10, "General Physician") == []


def test_the_score_is_the_weighted_sum_of_its_parts():
    (best,) = matching.rank([doc(1)], *F10, "General Physician")
    assert best.parts == {"proximity": 1.0, "specialty": 1.0, "availability": 1.0, "suitability": 1.0}
    assert best.score == pytest.approx(1.0)
    (soon,) = matching.rank([doc(1, availability=AVAILABLE_SOON)], *F10, "General Physician")
    assert soon.score == pytest.approx(0.9)


def test_proximity_reaches_zero_at_the_horizon_but_stays_eligible_inside_the_radius():
    far = doc(1, lat=33.6938 + 0.3, radius=50)  # about 33 km
    (ranked,) = matching.rank([far], *F10, "General Physician")
    assert ranked.parts["proximity"] == 0.0 and ranked.distance_km > matching.HORIZON_KM


def test_ties_break_by_distance_then_id_and_the_order_is_stable():
    same = [doc(7), doc(3), doc(5)]
    assert [r.doctor_id for r in matching.rank(same, *F10, "General Physician")] == [3, 5, 7]
    assert [r.doctor_id for r in matching.rank(list(reversed(same)), *F10, "General Physician")] == [3, 5, 7]


def test_limit_and_empty_input():
    many = [doc(i) for i in range(1, 9)]
    assert len(matching.rank(many, *F10, "General Physician", limit=5)) == 5
    assert len(matching.rank(many, *F10, "General Physician")) == 8
    assert matching.rank([], *F10, "General Physician") == []


# ---- offers and timeouts ---------------------------------------------------------------------------------------

T0 = datetime(2030, 1, 6, 8, 0, tzinfo=UTC)


def test_the_auto_window_is_two_minutes_and_ends_at_the_moment_it_expires():
    end = offers.expires_at(T0, offers.AUTO)
    assert end == T0 + timedelta(minutes=2)
    assert not offers.is_expired(end, end - timedelta(seconds=1))
    assert offers.is_expired(end, end)
    assert offers.is_expired(end, end + timedelta(hours=1))


def test_a_chosen_doctor_has_a_longer_window():
    assert offers.expires_at(T0, offers.CHOOSE) == T0 + timedelta(minutes=10)


def ranked_of(n):
    return matching.rank([doc(i) for i in range(1, n + 1)], *F10, "General Physician")


def test_the_next_doctor_is_the_best_one_not_yet_offered():
    ranked = ranked_of(4)
    assert offers.next_candidate(ranked, set()).doctor_id == 1
    assert offers.next_candidate(ranked, {1}).doctor_id == 2
    assert offers.next_candidate(ranked, {1, 2, 3}).doctor_id == 4
    assert offers.next_candidate(ranked, {1, 2, 3, 4}) is None


def test_no_more_than_five_doctors_are_offered_a_request():
    ranked = ranked_of(8)
    assert offers.next_candidate(ranked, {1, 2, 3, 4}).doctor_id == 5
    assert offers.next_candidate(ranked, {1, 2, 3, 4, 5}) is None


def test_nobody_eligible_means_no_doctor_found():
    assert offers.next_candidate([], set()) is None


# ---- availability from the weekly hours -------------------------------------------------------------------------

from datetime import time  # noqa: E402

from services.home_visits.availability import availability_state  # noqa: E402

MONDAY_HOURS = [(0, time(9, 0), time(17, 0))]


def karachi(hour, minute=0, day=7):
    """A moment on Monday 7 Jan 2030 at this Pakistan clock time (UTC+5)."""
    return datetime(2030, 1, day, hour - 5, minute, tzinfo=UTC)


def test_inside_the_hours_is_available_now_and_the_end_is_exclusive():
    assert availability_state(MONDAY_HOURS, karachi(9, 0)) == "now"
    assert availability_state(MONDAY_HOURS, karachi(16, 59)) == "now"
    assert availability_state(MONDAY_HOURS, karachi(17, 0)) == "none"


def test_a_window_starting_within_two_hours_is_soon():
    assert availability_state(MONDAY_HOURS, karachi(7, 0)) == "soon"
    assert availability_state(MONDAY_HOURS, karachi(6, 59)) == "none"
    assert availability_state(MONDAY_HOURS, karachi(8, 30)) == "soon"


def test_another_weekday_or_no_hours_is_unavailable():
    assert availability_state(MONDAY_HOURS, karachi(12, 0, day=8)) == "none"
    assert availability_state([], karachi(12, 0)) == "none"


def test_the_clinic_clock_decides_the_day_not_utc():
    # Monday 00:30 in Pakistan is still Sunday in UTC
    assert availability_state([(0, time(0, 0), time(2, 0))], datetime(2030, 1, 6, 19, 30, tzinfo=UTC)) == "now"


# ---- demo doctors -----------------------------------------------------------------------------------------------

from services.home_visits import demo_data  # noqa: E402


def test_demo_doctors_are_labelled_valid_and_resolve_to_home_visit_specialties():
    assert len(demo_data.DOCTORS) == 4 and len({d.key for d in demo_data.DOCTORS}) == 4
    for doctor in demo_data.DOCTORS:
        assert (
            doctor.full_name.startswith("[DEMO] ")
            and doctor.email.endswith("@example.test")
            and doctor.pmdc.startswith("DEMO-")
        )
        assert geo.validate_coordinates(doctor.latitude, doctor.longitude)
        assert 1 <= doctor.radius_km <= 50
        assert suitability.is_suitable(suitability.specialty_of(doctor.specialty))
    assert {d.area for d in demo_data.DOCTORS} == {"F-10", "G-11", "Blue Area", "Bahria Town"}


def test_only_accounts_matching_both_the_email_and_the_name_are_demo_accounts():
    doctor = demo_data.DOCTORS[0]
    assert demo_data.is_demo_account(doctor.email, doctor.full_name)
    assert not demo_data.is_demo_account(doctor.email, "Dr. Real Person")
    assert not demo_data.is_demo_account("someone@example.com", doctor.full_name)
    assert not demo_data.is_demo_account("demo-homevisit-x@gmail.com", doctor.full_name)


def test_a_patient_at_f10_is_matched_to_the_nearer_general_physicians_first():
    candidates = [
        Candidate(i, d.specialty, d.latitude, d.longitude, d.radius_km, AVAILABLE_NOW)
        for i, d in enumerate(demo_data.DOCTORS, start=1)
    ]
    ranked = matching.rank(candidates, 33.6940, 73.0130, "General Physician")
    assert [r.doctor_id for r in ranked][:2] == [
        1,
        2,
    ]  # F-10 then G-11; the dermatologist and pediatrician are not offered
    assert {r.doctor_id for r in ranked} == {1, 2}
