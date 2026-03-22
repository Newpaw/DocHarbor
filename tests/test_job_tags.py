from app.models import Job


def test_job_tags_are_normalized_and_unique() -> None:
    job = Job()
    job.set_tags("Voice, api, voice,  rag ")

    assert job.tags == ["voice", "api", "rag"]
    assert job.tags_text == ",voice,api,rag,"
