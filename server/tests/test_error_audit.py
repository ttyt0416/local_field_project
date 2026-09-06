import asyncio
import json
import unittest
from unittest.mock import patch

from starlette.requests import Request
from starlette.responses import Response

from app import database, main


class ErrorAuditTest(unittest.TestCase):
    def test_handled_error_records_provider_response(self) -> None:
        provider_response = {"choices": [{"finish_reason": "length"}], "usage": {"completion_tokens": 1024}}
        request = Request({"type": "http", "method": "POST", "path": "/generation/video/enhance-prompt", "headers": []})
        request.state.provider_response = provider_response

        async def call_next(_: Request) -> Response:
            return Response(status_code=503)

        with patch.object(main, "record_api_error") as record_error, patch.object(main, "record_api_call"):
            asyncio.run(main.audit_api_requests(request, call_next))

        self.assertEqual(record_error.call_args.kwargs["provider_response"], provider_response)

    def test_error_record_serializes_provider_response_as_jsonb(self) -> None:
        provider_response = {"choices": [{"finish_reason": "length"}], "usage": {"completion_tokens": 1024}}
        with patch.object(database, "_record") as record:
            database.record_api_error(
                method="POST",
                path="/generation/video/enhance-prompt",
                status_code=503,
                error_type="HTTPError",
                error_message="HTTP 503",
                client_ip=None,
                user_agent=None,
                provider_response=provider_response,
            )

        statement, parameters = record.call_args.args
        self.assertIn("provider_response", statement)
        self.assertEqual(parameters[5], json.dumps(provider_response, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
