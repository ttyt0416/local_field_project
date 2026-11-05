from __future__ import annotations

import base64
import json
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app import download_tokens as tokens
from app import model_downloads as models
from app.configs.constants import settings


class DownloadTokensTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = MagicMock()
        db = patch("app.download_tokens.get_connection")
        db.start().return_value.__enter__.return_value = self.connection
        self.addCleanup(db.stop)
        config = patch("app.download_tokens.settings", replace(settings, token_encryption_secret="test-encryption-secret-" * 3))
        config.start()
        self.addCleanup(config.stop)

    def test_ciphertext_is_randomized_authenticated_and_provider_bound(self) -> None:
        first = tokens.encrypt_token("civitai", "private-token")
        second = tokens.encrypt_token("civitai", "private-token")
        self.assertNotEqual(first, second)
        self.assertNotIn("private-token", first)
        self.assertEqual(tokens.decrypt_token("civitai", first), "private-token")
        self.assertNotIn("user_id", json.loads(tokens._cipher().decrypt(first.encode())))
        for provider, encrypted in (("hugging_face", first), ("civitai", first[:-5] + "XXXXX")):
            with self.subTest(provider=provider), self.assertRaises(tokens.CredentialError):
                tokens.decrypt_token(provider, encrypted)

    def test_legacy_ciphertext_can_be_migrated_without_account_information(self) -> None:
        old = tokens._cipher().encrypt(json.dumps({"user_id": str(uuid4()), "provider": "civitai", "token": "legacy-secret"}).encode()).decode()
        migrated = tokens.encrypt_token("civitai", tokens.decrypt_token("civitai", old))
        self.assertEqual(tokens.decrypt_token("civitai", migrated), "legacy-secret")
        self.assertNotIn("user_id", json.loads(tokens._cipher().decrypt(migrated.encode())))

    def test_save_and_status_never_return_a_token(self) -> None:
        self.connection.execute.return_value.fetchall.return_value = [("civitai", datetime.now(timezone.utc))]
        result = tokens.save_token("civitai", tokens.TokenRequest(token=" shared-secret "))
        query, parameters = self.connection.execute.call_args_list[0].args
        self.assertIn("ON CONFLICT (provider)", query)
        self.assertNotIn("user_id", query)
        self.assertEqual(parameters[0], "civitai")
        self.assertEqual(tokens.decrypt_token("civitai", parameters[1]), "shared-secret")
        body = json.dumps([row.model_dump(mode="json") for row in result])
        self.assertNotIn("shared-secret", body)
        self.assertNotIn(parameters[1], body)
        self.assertTrue(result[0].saved)
        self.assertFalse(result[1].saved)

    def test_saved_token_is_shared_by_provider(self) -> None:
        for provider in ("civitai", "hugging_face"):
            with self.subTest(provider=provider):
                self.connection.execute.return_value.fetchone.return_value = (tokens.encrypt_token(provider, "shared"),)
                self.assertEqual(tokens.get_effective_token(provider), "shared")
                self.assertEqual(self.connection.execute.call_args.args[1], (provider,))
                self.connection.execute.return_value.fetchone.return_value = None
                self.assertEqual(tokens.get_effective_token(provider), "")

    def test_invalid_headers_and_missing_encryption_configuration_do_not_write(self) -> None:
        for value in ("", "one\ntwo", "contains space", "한글", "x" * 4097):
            with self.subTest(value=value[:10]), self.assertRaises(HTTPException) as raised:
                tokens.save_token("civitai", tokens.TokenRequest(token=value))
            self.assertEqual(raised.exception.status_code, 422)
        with patch("app.download_tokens.settings", replace(settings, token_encryption_secret="")), self.assertRaises(HTTPException) as raised:
            tokens.save_token("civitai", tokens.TokenRequest(token="test-only"))
        self.assertEqual(raised.exception.status_code, 503)
        self.connection.execute.assert_not_called()

    def test_delete_is_provider_scoped(self) -> None:
        self.connection.execute.return_value.fetchall.return_value = []
        tokens.remove_token("hugging_face")
        query, parameters = self.connection.execute.call_args_list[0].args
        self.assertNotIn("user_id", query)
        self.assertEqual(parameters, ("hugging_face",))

    def test_workers_use_shared_provider_token(self) -> None:
        job = {"provider": "hugging_face", "source_repo": "owner/repo", "source_revision": "a" * 40, "source_filename": "model.safetensors"}
        repository = models.hf.HuggingFaceRepository("owner/repo", "a" * 40, (models.hf.HuggingFaceFile("model.safetensors", 10, None),))
        with patch("app.model_downloads.get_effective_token", return_value="shared-token") as token, patch("app.model_downloads.hf.fetch_repository", return_value=repository), patch("app.model_downloads._transfer_model_download") as transfer, patch("app.model_downloads.hf.open_download") as stream:
            models._process_model_download(job)
            transfer.call_args.args[3](4)
        token.assert_called_once_with("hugging_face")
        self.assertEqual(stream.call_args.args[1:3], ("shared-token", 4))
