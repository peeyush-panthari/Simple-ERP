"""Unit coverage for the BigQuery transaction retry primitive
(app/services/bq_transaction.py). Mocked at the google-cloud-bigquery client
boundary - no live GCP access needed, since it validates our own retry/
backoff control flow, not BigQuery's actual scripting/transaction behavior
(see that module's docstring for what still needs live verification).
"""

from unittest.mock import MagicMock, patch

import pytest
from google.api_core.exceptions import Aborted, BadRequest, NotFound

from app.services.bq_transaction import _is_conflict, run_in_transaction


def _build():
    return "SELECT 1", []


class TestIsConflict:
    def test_aborted_is_always_a_conflict(self):
        assert _is_conflict(Aborted("transaction aborted")) is True

    def test_bad_request_with_conflict_hint_is_a_conflict(self):
        assert _is_conflict(BadRequest("Transaction is aborted due to concurrent update")) is True

    def test_bad_request_without_conflict_hint_is_not_a_conflict(self):
        assert _is_conflict(BadRequest("Syntax error near SELECT")) is False

    def test_unrelated_error_is_not_a_conflict(self):
        assert _is_conflict(NotFound("table not found")) is False


class TestRunInTransaction:
    def test_succeeds_on_first_attempt_without_retrying(self):
        fake_result = object()
        fake_job = MagicMock(result=MagicMock(return_value=fake_result))
        fake_client = MagicMock(query=MagicMock(return_value=fake_job))

        with patch("app.services.bq_transaction._get_client", return_value=fake_client), patch("time.sleep") as sleep_mock:
            result = run_in_transaction(_build, max_retries=5)

        assert result is fake_result
        assert fake_client.query.call_count == 1
        sleep_mock.assert_not_called()

    def test_retries_on_conflict_then_succeeds(self):
        fake_result = object()
        fake_job = MagicMock(result=MagicMock(return_value=fake_result))
        fake_client = MagicMock(query=MagicMock(side_effect=[Aborted("conflict"), Aborted("conflict"), fake_job]))

        with patch("app.services.bq_transaction._get_client", return_value=fake_client), patch("time.sleep") as sleep_mock:
            result = run_in_transaction(_build, max_retries=5)

        assert result is fake_result
        assert fake_client.query.call_count == 3
        assert sleep_mock.call_count == 2
        # Backoff should be increasing (base * 2**attempt, jittered 0.5-1.5x) - just
        # check it stays within the documented bounds rather than an exact value.
        for call_args in sleep_mock.call_args_list:
            delay = call_args.args[0]
            assert 0 < delay <= 4.0

    def test_exhausts_retries_and_raises_last_error(self):
        conflict = Aborted("still conflicting")
        fake_client = MagicMock(query=MagicMock(side_effect=[conflict] * 5))

        with patch("app.services.bq_transaction._get_client", return_value=fake_client), patch("time.sleep"):
            with pytest.raises(Aborted):
                run_in_transaction(_build, max_retries=5)

        assert fake_client.query.call_count == 5

    def test_non_conflict_error_raises_immediately_without_retry(self):
        fake_client = MagicMock(query=MagicMock(side_effect=NotFound("dataset not found")))

        with patch("app.services.bq_transaction._get_client", return_value=fake_client), patch("time.sleep") as sleep_mock:
            with pytest.raises(NotFound):
                run_in_transaction(_build, max_retries=5)

        assert fake_client.query.call_count == 1
        sleep_mock.assert_not_called()

    def test_build_script_is_called_fresh_on_every_attempt(self):
        """Each retry must re-read the latest state, not resend a stale script."""
        build_calls = []

        def build():
            build_calls.append(1)
            return f"SELECT {len(build_calls)}", []

        fake_result = object()
        fake_job = MagicMock(result=MagicMock(return_value=fake_result))
        fake_client = MagicMock(query=MagicMock(side_effect=[Aborted("conflict"), fake_job]))

        with patch("app.services.bq_transaction._get_client", return_value=fake_client), patch("time.sleep"):
            run_in_transaction(build, max_retries=5)

        assert len(build_calls) == 2
        first_sql = fake_client.query.call_args_list[0].args[0]
        second_sql = fake_client.query.call_args_list[1].args[0]
        assert first_sql != second_sql
