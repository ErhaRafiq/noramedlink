"""Structured health record entries and the audit log: validation, how the medication check reads the
entries, and the audit rules. No database, no network."""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from schemas import HealthEntryIn, HealthEntryUpdate
from services import audit, health_record
from services.mscie import context as mscie_context
from services.mscie.engine import PatientContext


def entry(kind, name, *, by="patient", status="active", id_=1):
    return SimpleNamespace(
        id=id_, kind=kind, name=name, status=status, added_by_role=by, added_by_id=9, patient_id=3, severity=None
    )


# --- input rules ---------------------------------------------------------------------------------------


def test_a_name_is_trimmed_and_needs_two_characters():
    assert HealthEntryIn(kind="allergy", name="  penicillin  ").name == "penicillin"
    with pytest.raises(ValidationError):
        HealthEntryIn(kind="allergy", name=" a ")


def test_a_date_cannot_be_in_the_future():
    tomorrow = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError):
        HealthEntryIn(kind="diagnosis", name="asthma", since=tomorrow)
    with pytest.raises(ValidationError):
        HealthEntryUpdate(since=tomorrow)


def test_only_known_kinds_and_severities_are_accepted():
    with pytest.raises(ValidationError):
        HealthEntryIn(kind="medicine", name="aspirin")
    with pytest.raises(ValidationError):
        HealthEntryIn(kind="allergy", name="penicillin", severity="extreme")


def test_an_update_only_carries_the_fields_that_were_sent():
    assert HealthEntryUpdate(note="rash").model_dump(exclude_unset=True) == {"note": "rash"}


# --- what the medication check can use -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "name", "expected"),
    [
        ("allergy", "penicillin", True),
        ("allergy", "Penicillin ", True),
        ("allergy", "aspirin", True),
        ("allergy", "moon dust", False),
        ("diagnosis", "diabetes", True),
        ("chronic_condition", "high blood pressure", True),
        ("diagnosis", "feeling sad on mondays", False),
    ],
)
def test_the_check_says_which_words_it_recognises(kind, name, expected):
    assert health_record.recognised(kind, name) is expected


def build(monkeypatch, entries):
    monkeypatch.setattr(health_record, "active_entries", lambda db, patient_id: entries)
    context = PatientContext()
    mscie_context._add_structured_entries(None, SimpleNamespace(id=3), context)
    return context


def test_a_recognised_allergy_reaches_the_safety_check_with_its_classes(monkeypatch):
    context = build(monkeypatch, [entry("allergy", "penicillin")])
    [allergy] = context.allergies
    assert allergy["classes"] and allergy["source"] == "health record (added by you)"


def test_an_allergy_the_check_cannot_read_is_not_guessed_at(monkeypatch):
    assert build(monkeypatch, [entry("allergy", "moon dust")]).allergies == []


def test_a_condition_is_used_under_its_standard_name_and_says_who_added_it(monkeypatch):
    context = build(monkeypatch, [entry("diagnosis", "diabetes", by="doctor")])
    assert context.conditions == [{"name": "diabetes mellitus", "source": "health record (added by a doctor)"}]


def test_the_same_condition_listed_twice_counts_once(monkeypatch):
    context = build(
        monkeypatch, [entry("diagnosis", "diabetes"), entry("chronic_condition", "diabetes mellitus", id_=2)]
    )
    assert [c["name"] for c in context.conditions] == ["diabetes mellitus"]


def test_an_unrecognised_condition_is_kept_on_the_record_but_not_used(monkeypatch):
    assert build(monkeypatch, [entry("diagnosis", "feeling sad on mondays")]).conditions == []


# --- the audit log -------------------------------------------------------------------------------------


class Query:
    def __init__(self, found):
        self.found = found

    def filter(self, *_):
        return self

    def first(self):
        return self.found


class Db:
    def __init__(self, existing=None):
        self.existing, self.added, self.commits = existing, [], 0

    def query(self, *_):
        return Query(self.existing)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


DOCTOR = SimpleNamespace(id=5, role="DOCTOR")


def test_an_unknown_action_is_refused():
    with pytest.raises(ValueError):
        audit.record(Db(), DOCTOR, "record.peek")


def test_a_row_names_who_did_what_to_whom_and_commits():
    db = Db()
    row = audit.record(db, DOCTOR, "record.view", patient_id=3, detail="clinical summary")
    assert (row.actor_id, row.actor_role, row.action, row.patient_id) == (5, "doctor", "record.view", 3)
    assert db.added == [row] and db.commits == 1


def test_a_repeated_view_inside_the_window_is_logged_once():
    assert audit.record(Db(existing=object()), DOCTOR, "record.view", patient_id=3, once_per=audit.VIEW_WINDOW) is None
    assert audit.record(Db(existing=None), DOCTOR, "record.view", patient_id=3, once_per=audit.VIEW_WINDOW) is not None


def test_the_detail_is_cut_to_fit_the_column():
    assert len(audit.record(Db(), DOCTOR, "record.view", detail="x" * 1000).detail) == 300


def test_every_action_has_words_a_person_can_read():
    assert all(text and text == text.strip() for text in audit.ACTIONS.values())


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("viewed the patient's record", "viewed your record"),
        ("was given access to the record", "was given access to your record"),
        ("added to the health record", "added to your health record"),
        ("confirmed a prescription", "confirmed a prescription"),
    ],
)
def test_a_patient_reads_the_log_in_the_second_person(label, expected):
    assert audit.patient_wording(label) == expected
