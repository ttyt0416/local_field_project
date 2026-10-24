from __future__ import annotations

import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app import download_tokens as tokens
from app import model_downloads as models
from app.auth import UserResponse
from app.configs.constants import settings


class DownloadTokensTest(unittest.TestCase):
    def setUp(self) -> None:
        self.user = UserResponse(id=uuid4(), username="tester")
        self.connection = MagicMock()
        db = patch("app.download_tokens.get_connection")
        db.start().return_value.__enter__.return_value = self.connection
        self.addCleanup(db.stop)
        config = patch("app.download_tokens.settings", replace(settings, auth_secret="test-encryption-secret-" * 3))
        config.start()
        self.addCleanup(config.stop)

    def test_ciphertext_is_randomized_authenticated_and_bound_to_owner_and_provider(self) -> None:
        first = tokens.encrypt_token(self.user.id, "civitai", "private-token")
        second = tokens.encrypt_token(self.user.id, "civitai", "private-token")
        self.assertNotEqual(first, second)
        self.assertNotIn("private-token", first)
        self.assertEqual(tokens.decrypt_token(self.user.id, "civitai", first), "private-token")
        for owner, provider, encrypted in ((uuid4(), "civitai", first), (self.user.id, "hugging_face", first), (self.user.id, "civitai", first[:-5] + "XXXXX")):
            with self.subTest(provider=provider), self.assertRaises(tokens.CredentialError):
                tokens.decrypt_token(owner, provider, encrypted)

    def test_save_and_status_never_return_a_token(self) -> None:
        self.connection.execute.return_value.fetchall.return_value = [("civitai", datetime.now(timezone.utc))]
        payload = tokens.TokenRequest(token=" personal-secret ")
        self.assertNotIn("personal-secret", repr(payload))
        result = tokens.save_token("civitai", payload, self.user)
        sql, parameters = self.connection.execute.call_args_list[0].args
        self.assertIn("ON CONFLICT", sql)
        self.assertEqual(parameters[:2], (self.user.id, "civitai"))
        self.assertEqual(tokens.decrypt_token(self.user.id, "civitai", parameters[2]), "personal-secret")
        body = json.dumps([row.model_dump(mode="json") for row in result])
        self.assertNotIn("personal-secret", body)
        self.assertNotIn(parameters[2], body)
        self.assertNotIn("server_configured", body)
        self.assertTrue(result[0].saved)
        self.assertFalse(result[1].saved)

    def test_only_personal_tokens_are_used_and_lookup_is_owner_scoped(self) -> None:
        with patch.dict("os.environ", {"CIVITAI_TOKEN": "unused-shared-civitai", "HF_TOKEN": "unused-shared-hf"}):
            for provider in ("civitai", "hugging_face"):
                with self.subTest(provider=provider):
                    encrypted = tokens.encrypt_token(self.user.id, provider, "personal")
                    self.connection.execute.return_value.fetchone.return_value = (encrypted,)
                    self.assertEqual(tokens.get_effective_token(self.user.id, provider), "personal")
                    self.assertEqual(self.connection.execute.call_args.args[1], (self.user.id, provider))
                    self.connection.execute.return_value.fetchone.return_value = None
                    self.assertEqual(tokens.get_effective_token(uuid4(), provider), "")
                    self.connection.execute.reset_mock()
                    self.assertEqual(tokens.get_effective_token(None, provider), "")
                    self.connection.execute.assert_not_called()

    def test_civitai_download_requires_personal_token_even_with_shared_environment(self) -> None:
        self.connection.execute.return_value.fetchone.return_value = None
        with TemporaryDirectory() as temporary, patch.dict("os.environ", {"CIVITAI_TOKEN": "unused-shared-civitai"}), patch("app.model_downloads.settings", replace(settings, comfyui_models_path=temporary)), patch("app.model_downloads._resolve_civitai_source") as metadata, patch("app.model_downloads.create_model_download") as enqueue:
            with self.assertRaises(HTTPException) as raised:
                models.download_civitai_model(models.ModelDownloadRequest(source="1", model_type="checkpoint"), self.user)
        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("토큰을 저장", raised.exception.detail)
        metadata.assert_not_called()
        enqueue.assert_not_called()

    def test_invalid_headers_and_missing_encryption_configuration_do_not_write(self) -> None:
        for value in ("", "one\ntwo", "contains space", "한글", "x" * 4097):
            with self.subTest(value=value[:10]), self.assertRaises(HTTPException) as raised:
                tokens.save_token("civitai", tokens.TokenRequest(token=value), self.user)
            self.assertEqual(raised.exception.status_code, 422)
        with patch("app.download_tokens.settings", replace(settings, auth_secret="")), self.assertRaises(HTTPException) as raised:
            tokens.save_token("civitai", tokens.TokenRequest(token="test-only"), self.user)
        self.assertEqual(raised.exception.status_code, 503)
        self.connection.execute.assert_not_called()

    def test_delete_is_owner_and_provider_scoped(self) -> None:
        self.connection.execute.return_value.fetchall.return_value = []
        tokens.remove_token("hugging_face", self.user)
        self.assertEqual(self.connection.execute.call_args_list[0].args[1], (self.user.id, "hugging_face"))
        self.connection.execute.return_value.fetchone.return_value = None
        self.assertEqual(tokens.get_effective_token(self.user.id, "hugging_face"), "")

    def test_civitai_metadata_token_context_does_not_leak_between_requests(self) -> None:
        response = MagicMock()
        response.read.return_value = b'{}'
        with patch("app.model_downloads._NO_REDIRECT_OPENER.open") as opener, patch("app.model_downloads.urlopen") as public:
            opener.return_value.__enter__.return_value = response
            public.return_value.__enter__.return_value = response
            with models._civitai_token_scope("first-user"):
                models._fetch_civitai_payload("model-versions/1", "missing")
            models._fetch_civitai_payload("model-versions/1", "missing")
        self.assertEqual(opener.call_args.args[0].get_header("Authorization"), "Bearer first-user")
        self.assertIsNone(public.call_args.args[0].get_header("Authorization"))
        self.assertEqual(models._CIVITAI_REQUEST_TOKEN.get(), "")

    def test_hugging_face_worker_uses_job_owner_token(self) -> None:
        job = {"user_id": self.user.id, "provider": "hugging_face", "source_repo": "owner/repo", "source_revision": "a" * 40, "source_filename": "model.safetensors"}
        repository = models.hf.HuggingFaceRepository("owner/repo", "a" * 40, (models.hf.HuggingFaceFile("model.safetensors", 10, None),))
        with patch("app.model_downloads.get_effective_token", return_value="owner-token") as token, patch("app.model_downloads.hf.fetch_repository", return_value=repository) as metadata, patch("app.model_downloads._transfer_model_download") as transfer, patch("app.model_downloads.hf.open_download") as stream:
            models._process_model_download(job)
            transfer.call_args.args[3](4)
        token.assert_called_once_with(self.user.id, "hugging_face")
        self.assertEqual(metadata.call_args.args[2], "owner-token")
        self.assertEqual(stream.call_args.args[1:3], ("owner-token", 4))

    def test_civitai_worker_uses_job_owner_token(self) -> None:
        job = {"user_id": self.user.id, "version_id": 1, "model_type": "checkpoint", "file_index": 0}
        version = MagicMock()
        version.files = [models.CivitaiFile("model.safetensors", "Model", "https://civitai.com/file", 10, None, True)]
        with patch("app.model_downloads.get_effective_token", return_value="owner-token") as token, patch("app.model_downloads._fetch_version", return_value=version), patch("app.model_downloads._select_file_index", return_value=0), patch("app.model_downloads._transfer_model_download") as transfer, patch("app.model_downloads._open_download") as stream:
            models._process_model_download(job)
            transfer.call_args.args[3](4)
        token.assert_called_once_with(self.user.id, "civitai")
        self.assertEqual(stream.call_args.args[1:3], ("owner-token", 4))


if __name__ == "__main__":
    unittest.main()
