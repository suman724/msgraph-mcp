import base64
import json
import os
import time
from dataclasses import dataclass

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .config import settings


def _b64e(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64d(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


@dataclass
class StoredToken:
    refresh_token: str
    scopes: list[str]
    expires_at: int


class TokenStore:
    def __init__(self) -> None:
        self._ddb = boto3.resource("dynamodb", region_name=settings.aws_region)
        self._kms = boto3.client("kms", region_name=settings.aws_region)
        self._tokens_table = self._ddb.Table(settings.ddb_table_tokens)
        self._sessions_table = self._ddb.Table(settings.ddb_table_sessions)
        self._delta_table = self._ddb.Table(settings.ddb_table_delta)
        self._idempotency_table = self._ddb.Table(settings.ddb_table_idempotency)

    def _encrypt(self, plaintext: str) -> dict:
        data_key = self._kms.generate_data_key(
            KeyId=settings.kms_key_id, KeySpec="AES_256"
        )
        nonce = os.urandom(12)
        aesgcm = AESGCM(data_key["Plaintext"])
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return {
            "ciphertext": _b64e(ciphertext),
            "nonce": _b64e(nonce),
            "encrypted_key": _b64e(data_key["CiphertextBlob"]),
        }

    def _decrypt(self, payload: dict) -> str:
        data_key = self._kms.decrypt(CiphertextBlob=_b64d(payload["encrypted_key"]))
        aesgcm = AESGCM(data_key["Plaintext"])
        plaintext = aesgcm.decrypt(
            _b64d(payload["nonce"]), _b64d(payload["ciphertext"]), None
        )
        return plaintext.decode("utf-8")

    def store_refresh_token(
        self,
        tenant_id: str,
        user_id: str,
        client_id: str,
        refresh_token: str,
        scopes: list[str],
        expires_at: int,
    ) -> None:
        encrypted = self._encrypt(refresh_token)
        self._tokens_table.put_item(
            Item={
                "pk": f"{tenant_id}#{user_id}",
                "sk": client_id,
                "scopes": scopes,
                "expires_at": expires_at,
                **encrypted,
            }
        )

    def get_refresh_token(
        self, tenant_id: str, user_id: str, client_id: str
    ) -> StoredToken | None:
        response = self._tokens_table.get_item(
            Key={"pk": f"{tenant_id}#{user_id}", "sk": client_id}
        )
        item = response.get("Item")
        if not item:
            return None
        refresh_token = self._decrypt(item)
        return StoredToken(
            refresh_token=refresh_token,
            scopes=item.get("scopes", []),
            expires_at=int(item.get("expires_at", 0)),
        )

    def store_session(
        self,
        session_id: str,
        tenant_id: str,
        user_id: str,
        client_id: str,
        scopes: list[str],
        expires_at: int,
    ) -> None:
        self._sessions_table.put_item(
            Item={
                "mcp_session_id": session_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "client_id": client_id,
                "scopes": scopes,
                "expires_at": expires_at,
            }
        )

    def get_session(self, session_id: str) -> dict | None:
        response = self._sessions_table.get_item(Key={"mcp_session_id": session_id})
        return response.get("Item")

    def store_delta_token(
        self, tenant_id: str, user_id: str, domain: str, delta_token: str
    ) -> None:
        self._delta_table.put_item(
            Item={
                "pk": f"{tenant_id}#{user_id}",
                "sk": domain,
                "delta_token": delta_token,
                "updated_at": int(time.time()),
            }
        )

    def get_delta_token(self, tenant_id: str, user_id: str, domain: str) -> str | None:
        response = self._delta_table.get_item(
            Key={"pk": f"{tenant_id}#{user_id}", "sk": domain}
        )
        item = response.get("Item")
        if not item:
            return None
        return item.get("delta_token")

    def check_idempotency(
        self, tenant_id: str, user_id: str, idempotency_key: str
    ) -> dict | None:
        response = self._idempotency_table.get_item(
            Key={"pk": f"{tenant_id}#{user_id}", "sk": idempotency_key}
        )
        return response.get("Item")

    def put_idempotency(
        self,
        tenant_id: str,
        user_id: str,
        idempotency_key: str,
        tool_name: str,
        result: dict,
        result_hash: str,
    ) -> None:
        ttl = int(time.time()) + settings.idempotency_ttl_seconds
        self._idempotency_table.put_item(
            Item={
                "pk": f"{tenant_id}#{user_id}",
                "sk": idempotency_key,
                "tool_name": tool_name,
                "result_hash": result_hash,
                "result": json.dumps(result),
                "ttl": ttl,
                "created_at": int(time.time()),
            }
        )
