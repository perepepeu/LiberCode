from unittest.mock import patch, MagicMock
from libercode.providers.base import request_with_retry


class TestRequestWithRetry:
    @patch("libercode.providers.base.requests.post")
    def test_success_on_first_try(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        result = request_with_retry("http://test.com", {})
        assert result.status_code == 200

    @patch("libercode.providers.base.time.sleep")
    @patch("libercode.providers.base.requests.post")
    def test_retries_on_429(self, mock_post, mock_sleep):
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_post.side_effect = [mock_429, mock_ok]
        result = request_with_retry("http://test.com", {})
        assert result.status_code == 200
        assert mock_post.call_count == 2

    @patch("libercode.providers.base.time.sleep")
    @patch("libercode.providers.base.requests.post")
    def test_retries_on_500(self, mock_post, mock_sleep):
        mock_500 = MagicMock()
        mock_500.status_code = 500
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_post.side_effect = [mock_500, mock_ok]
        result = request_with_retry("http://test.com", {})
        assert result.status_code == 200

    @patch("libercode.providers.base.time.sleep")
    @patch("libercode.providers.base.requests.post")
    def test_returns_none_after_max_retries(self, mock_post, mock_sleep):
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_post.return_value = mock_429
        result = request_with_retry("http://test.com", {})
        assert result is None
