import uuid

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import JobPosting
from app.modules.jobs.location_country import (
    infer_countries_from_location,
    parse_serialized_countries,
    serialize_countries,
)
from app.modules.jobs.repository import _job_filters


def _compiled(filters):
    return select(JobPosting).where(*filters).compile(dialect=postgresql.dialect())


def test_infer_countries_from_location_handles_city_and_metropolitan_area():
    assert infer_countries_from_location("Hamburg") == ["Germany"]
    assert infer_countries_from_location("Greater Munich Metropolitan Area") == ["Germany"]
    assert infer_countries_from_location("Metropolregion München") == ["Germany"]
    assert infer_countries_from_location("Zürich, Schweiz") == ["Switzerland"]


def test_infer_countries_from_location_keeps_multi_country_jobs():
    assert infer_countries_from_location("Germany/Spain/Italy/Portugal (Remote)") == [
        "Germany",
        "Spain",
        "Italy",
        "Portugal",
    ]
    assert infer_countries_from_location(
        "Berlin, Germany / London, United Kingdom / Iasi, Romania"
    ) == ["Germany", "United Kingdom", "Romania"]


def test_country_serialization_is_stable_for_like_filtering():
    serialized = serialize_countries(["Germany", "Switzerland", "Germany"])

    assert serialized == "|Germany||Switzerland|"
    assert parse_serialized_countries(serialized) == ["Germany", "Switzerland"]


def test_job_filters_include_country_and_added_date_when_requested():
    compiled = _compiled(_job_filters(uuid.uuid4(), country="Germany", added_date="2026-06-05"))
    sql = str(compiled)

    assert "job_postings.countries LIKE" in sql
    assert "date(job_postings.created_at)" in sql
    assert compiled.params["countries_1"] == "|Germany|"
    assert compiled.params["date_1"] == "2026-06-05"
