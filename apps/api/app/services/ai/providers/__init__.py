"""AI providers: FakeProvider (deterministic test script), OllamaProvider, GeminiProvider (PRD §6.2)."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.ai.prompts import (
    explain_meal_plan,
    explain_nutrition,
    explain_prices,
    explain_workout,
)


class AITimeout(Exception):
    pass


class AIUnavailable(Exception):
    pass


class AIInvalidOutput(Exception):
    pass


class ProviderResult(BaseModel):
    parsed: dict[str, Any]
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int = 0


class AIProvider(Protocol):
    name: str
    model: str

    async def chat(self, messages: list[dict[str, str]], schema: dict[str, Any], timeout_s: float) -> ProviderResult: ...


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaProvider:
    def __init__(self, base_url: str, model: str, max_output_tokens: int = 600) -> None:
        self.name = "ollama"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_output_tokens = max_output_tokens

    async def chat(self, messages: list[dict[str, str]], schema: dict[str, Any], timeout_s: float) -> ProviderResult:
        t0 = time.monotonic()
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "think": False,
            "options": {"temperature": 0.2, "num_ctx": 4096, "num_predict": self.max_output_tokens},
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=body)
        except httpx.TimeoutException as exc:
            raise AITimeout("Ollama timeout") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailable(f"Ollama connection error: {exc}") from exc

        if resp.status_code != 200:
            raise AIUnavailable(f"Ollama HTTP {resp.status_code}")

        data = resp.json()
        raw = ((data.get("message") or {}).get("content") or "").strip()
        raw = _THINK_RE.sub("", raw).strip()
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            raise AIInvalidOutput("Invalid JSON from Ollama") from exc
        if not isinstance(parsed, dict):
            raise AIInvalidOutput("Non-object JSON from Ollama")
        return ProviderResult(
            parsed=parsed,
            tokens_in=data.get("prompt_eval_count"),
            tokens_out=data.get("eval_count"),
            latency_ms=int((time.monotonic() - t0) * 1000),
        )


class GeminiProvider:
    def __init__(self, api_key: str, model: str, max_output_tokens: int = 600) -> None:
        self.name = "gemini"
        self.api_key = api_key
        self.model = model
        self.max_output_tokens = max_output_tokens

    async def chat(self, messages: list[dict[str, str]], schema: dict[str, Any], timeout_s: float) -> ProviderResult:
        if not self.api_key:
            raise AIUnavailable("GEMINI_API_KEY not configured")
        t0 = time.monotonic()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        sys_parts = [m["content"] for m in messages if m["role"] == "system"]
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
            if m["role"] != "system"
        ]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        if sys_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(sys_parts)}]}
        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                resp = await client.post(url, params={"key": self.api_key}, json=payload)
        except httpx.TimeoutException as exc:
            raise AITimeout("Gemini timeout") from exc
        except httpx.HTTPError as exc:
            raise AIUnavailable(f"Gemini error: {exc}") from exc

        if resp.status_code != 200:
            raise AIUnavailable(f"Gemini HTTP {resp.status_code}")

        data = resp.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
        except Exception as exc:
            raise AIInvalidOutput("Invalid JSON from Gemini") from exc
        if not isinstance(parsed, dict):
            raise AIInvalidOutput("Non-object JSON from Gemini")
        usage = data.get("usageMetadata") or {}
        return ProviderResult(
            parsed=parsed,
            tokens_in=usage.get("promptTokenCount"),
            tokens_out=usage.get("candidatesTokenCount"),
            latency_ms=int((time.monotonic() - t0) * 1000),
        )


class FakeProvider:
    """Deterministic scripted provider for tests & demos (PRD §6.2)."""

    def __init__(self) -> None:
        self.name = "fake"
        self.model = "fake-1.0"
        self.call_count = 0
        self.custom_handler: Callable[[list[dict[str, str]], dict[str, Any]], dict[str, Any]] | None = None
        self.next_exception: Exception | None = None
        self.next_raw_output: Any = None

    def reset(self) -> None:
        self.call_count = 0
        self.custom_handler = None
        self.next_exception = None
        self.next_raw_output = None

    async def chat(self, messages: list[dict[str, str]], schema: dict[str, Any], timeout_s: float) -> ProviderResult:
        self.call_count += 1
        if self.next_exception is not None:
            exc = self.next_exception
            self.next_exception = None
            raise exc
        if self.next_raw_output is not None:
            raw = self.next_raw_output
            self.next_raw_output = None
            if not isinstance(raw, dict):
                raise AIInvalidOutput("Malformed output")
            return ProviderResult(parsed=raw, tokens_in=10, tokens_out=20, latency_ms=5)
        if self.custom_handler is not None:
            return ProviderResult(parsed=self.custom_handler(messages, schema), tokens_in=10, tokens_out=20, latency_ms=5)

        user_msg = (messages[-1]["content"] if messages else "").strip()
        low = user_msg.lower()
        ctx: dict[str, Any] = {}
        for m in messages:
            if m["role"] == "system" and "KONTEKS_JSON:" in m["content"]:
                raw_ctx = m["content"].split("KONTEKS_JSON:", 1)[1].strip()
                try:
                    ctx = json.loads(raw_ctx)
                except Exception:
                    ctx = {}

        # Out-of-scope / prompt injection / modifying energy/protein targets via chat
        if any(
            p in low
            for p in (
                "pengguna lain",
                "hapus semua",
                "system prompt",
                "abaikan aturan",
                "ubah target kalori",
                "ubah target protein",
                "naikkan kalori",
                "turunkan kalori",
            )
        ):
            return ProviderResult(
                parsed={
                    "intent": "out_of_scope",
                    "explanation": "Permintaan tersebut di luar cakupan asisten. Untuk mengubah target energi atau protein, gunakan halaman Nutrisi.",
                    "proposed_changes": [],
                    "references": [],
                    "warnings": [],
                    "missing_params": [],
                },
                tokens_in=20,
                tokens_out=25,
                latency_ms=4,
            )

        # Price question (TC-07)
        if "harga" in low:
            return ProviderResult(
                parsed={
                    "intent": "price_question",
                    "explanation": explain_prices(ctx, user_msg),
                    "proposed_changes": [],
                    "references": ["prices"],
                    "warnings": [],
                    "missing_params": [],
                },
                tokens_in=30,
                tokens_out=30,
                latency_ms=4,
            )

        # Budget change proposal
        if "budget" in low or "anggaran" in low:
            nums = [int(x.replace(".", "")) for x in re.findall(r"\d{2,3}(?:\.\d{3})+|\d{4,6}", low)]
            if not nums:
                return ProviderResult(
                    parsed={
                        "intent": "clarification_needed",
                        "explanation": "Berapa nominal budget harian baru (dalam rupiah) yang Anda inginkan?",
                        "proposed_changes": [],
                        "references": ["targets"],
                        "warnings": [],
                        "missing_params": ["daily_budget_idr"],
                    },
                    tokens_in=20,
                    tokens_out=20,
                    latency_ms=4,
                )
            b = nums[-1]
            return ProviderResult(
                parsed={
                    "intent": "propose_budget_change",
                    "explanation": f"Saya membuat usulan perubahan budget harian menjadi Rp{b:,}. Silakan tinjau pratinjau dan konfirmasi.".replace(
                        ",", "."
                    ),
                    "proposed_changes": [{"type": "change_budget", "params": {"daily_budget_idr": b}}],
                    "references": ["targets", "meal_plan"],
                    "warnings": [],
                    "missing_params": [],
                },
                tokens_in=25,
                tokens_out=25,
                latency_ms=4,
            )

        # Exclude food proposal
        if any(k in low for k in ("kecualikan", "hapus makanan", "tidak suka", "alergi", "exclude", "tanpa ")):
            m = re.search(r"(?:kecualikan|tanpa|suka|alergi|exclude)\s+([a-zA-Z\s]{2,30})", user_msg, re.IGNORECASE)
            fname = m.group(1).strip() if m else ""
            if not fname:
                return ProviderResult(
                    parsed={
                        "intent": "clarification_needed",
                        "explanation": "Sebutkan nama bahan pangan yang ingin dikecualikan.",
                        "proposed_changes": [],
                        "references": [],
                        "warnings": [],
                        "missing_params": ["food_name"],
                    },
                    tokens_in=20,
                    tokens_out=20,
                    latency_ms=4,
                )
            return ProviderResult(
                parsed={
                    "intent": "propose_exclude_food",
                    "explanation": f"Saya membuat usulan untuk mengecualikan '{fname}' dan menyusun ulang draf menu. Silakan konfirmasi bila setuju.",
                    "proposed_changes": [{"type": "exclude_food", "params": {"food_name": fname}}],
                    "references": ["meal_plan"],
                    "warnings": [],
                    "missing_params": [],
                },
                tokens_in=25,
                tokens_out=25,
                latency_ms=4,
            )

        # Reschedule workout proposal
        if any(k in low for k in ("geser", "pindah", "reschedule", "jadwal ulang")):
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", user_msg)
            if len(dates) < 2:
                return ProviderResult(
                    parsed={
                        "intent": "clarification_needed",
                        "explanation": "Sebutkan tanggal sesi asal dan tanggal tujuan (format YYYY-MM-DD).",
                        "proposed_changes": [],
                        "references": ["workout_plan"],
                        "warnings": [],
                        "missing_params": ["from_date", "to_date"],
                    },
                    tokens_in=20,
                    tokens_out=20,
                    latency_ms=4,
                )
            return ProviderResult(
                parsed={
                    "intent": "propose_reschedule_workout",
                    "explanation": f"Saya membuat usulan pemindahan sesi latihan dari {dates[0]} ke {dates[1]}. Silakan konfirmasi.",
                    "proposed_changes": [
                        {"type": "reschedule_workout", "params": {"from_date": dates[0], "to_date": dates[1]}}
                    ],
                    "references": ["workout_plan"],
                    "warnings": [],
                    "missing_params": [],
                },
                tokens_in=25,
                tokens_out=25,
                latency_ms=4,
            )

        if any(k in low for k in ("latihan", "gym", "workout", "sesi")):
            return ProviderResult(
                parsed={
                    "intent": "explain_workout",
                    "explanation": explain_workout(ctx),
                    "proposed_changes": [],
                    "references": ["workout_plan"],
                    "warnings": [],
                    "missing_params": [],
                },
                tokens_in=25,
                tokens_out=25,
                latency_ms=4,
            )

        if any(k in low for k in ("tdee", "ree", "kalori", "nutrisi", "protein")):
            return ProviderResult(
                parsed={
                    "intent": "explain_nutrition",
                    "explanation": explain_nutrition(ctx),
                    "proposed_changes": [],
                    "references": ["targets"],
                    "warnings": [],
                    "missing_params": [],
                },
                tokens_in=25,
                tokens_out=25,
                latency_ms=4,
            )

        return ProviderResult(
            parsed={
                "intent": "explain_plan",
                "explanation": explain_meal_plan(ctx),
                "proposed_changes": [],
                "references": ["meal_plan", "targets"],
                "warnings": [],
                "missing_params": [],
            },
            tokens_in=30,
            tokens_out=30,
            latency_ms=4,
        )


_fake_singleton = FakeProvider()
_override_provider: AIProvider | None = None


def get_fake_provider() -> FakeProvider:
    return _fake_singleton


def set_override_provider(p: AIProvider | None) -> None:
    global _override_provider
    _override_provider = p


def resolve_provider() -> AIProvider | None:
    if _override_provider is not None:
        return _override_provider
    s = get_settings()
    kind = (s.ai_provider or "none").lower()
    if kind == "none":
        return None
    if kind == "fake":
        return _fake_singleton
    if kind == "gemini":
        return GeminiProvider(s.gemini_api_key, s.gemini_model, s.ai_max_output_tokens)
    return OllamaProvider(s.ollama_base_url, s.ollama_model, s.ai_max_output_tokens)

