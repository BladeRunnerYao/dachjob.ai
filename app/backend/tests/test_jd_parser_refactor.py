def test_jd_parser_compat_exports():
    from app.modules.matching.jd_parser import (
        _enrich_parsed_skills,
        _extract_listed_skills,
        parse_job_posting,
    )

    assert callable(parse_job_posting)
    assert callable(_extract_listed_skills)
    assert callable(_enrich_parsed_skills)
