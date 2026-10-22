import httpx

from app.services import youtube_transcript


def test_extract_youtube_transcript_returns_ordered_steps(app, monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"transcript": "Boil water. Add grains."}

    calls = {}

    def fake_post(url, **kwargs):
        calls.update(url=url, kwargs=kwargs)
        return Response()

    monkeypatch.setattr(youtube_transcript.httpx, "post", fake_post)
    with app.app_context():
        app.config["RAPIDAPI_KEY"] = "test-key"
        result = youtube_transcript.extract("https://www.youtube.com/watch?v=abc")

    assert result["steps"] == ["Boil water.", "Add grains."]
    assert calls["kwargs"]["headers"]["x-rapidapi-key"] == "test-key"
    assert calls["kwargs"]["json"] == {"url": "https://www.youtube.com/watch?v=abc"}


def test_extract_accepts_provider_transcription_field(app, monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"transcription": "Open the door. Enter the room."}

    monkeypatch.setattr(youtube_transcript.httpx, "post", lambda *args, **kwargs: Response())
    with app.app_context():
        app.config["RAPIDAPI_KEY"] = "test-key"
        result = youtube_transcript.extract("https://www.youtube.com/watch?v=abc")

    assert result["steps"] == ["Open the door.", "Enter the room."]


def test_extract_rejects_non_youtube_url(app):
    from app.services.errors import ServiceError
    import pytest

    with app.app_context(), pytest.raises(ServiceError, match="valid HTTPS YouTube URL"):
        youtube_transcript.extract("https://example.com/video")


def test_extract_maps_provider_failures(app, monkeypatch):
    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "https://provider.test")
        response = httpx.Response(503, request=request)
        raise httpx.HTTPStatusError("unavailable", request=request, response=response)

    monkeypatch.setattr(youtube_transcript.httpx, "post", fake_post)
    with app.app_context():
        app.config["RAPIDAPI_KEY"] = "test-key"
        from app.services.errors import ServiceError
        import pytest
        with pytest.raises(ServiceError) as exc:
            youtube_transcript.extract("https://youtu.be/abc")

    assert exc.value.code == "YOUTUBE_TRANSCRIPT_REJECTED"
    assert exc.value.retryable
