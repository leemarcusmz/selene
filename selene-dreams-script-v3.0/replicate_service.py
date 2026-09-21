# =============================================================================
# Selene Dreams — Image Generation Script v3.0
# replicate_service.py — Nano Banana Pro image generation via Replicate
# VERSION 1.1 — 2026-08-26
#
# CHANGELOG
#   1.1  2026-08-26  Capacity retries. Google's Nano Banana capacity has been
#                    saturating for days (E003 "high demand" — see Google's own
#                    forum), and three real generation runs across 17 hours all
#                    died on it, each needing a HUMAN to reset D=Ready and
#                    re-fire. Capacity errors and timeouts are now retried
#                    IN-PROCESS: up to 4 further attempts with 2/4/8/16-minute
#                    backoff (~30 min total) before giving up. Genuine errors —
#                    bad input, safety blocks, auth — still fail immediately;
#                    only "try again later"-class failures are retried.
#   1.0              Original: explicit polling (Prefer:wait was dropping
#                    connections), allow_fallback_model to Seedream.
# =============================================================================
#
# Uses the official Replicate Python SDK. This module explicitly polls the
# prediction status instead of relying on the SDK's client.run() short-wait
# pattern, because Nano Banana Pro generations frequently exceed the 60-second
# Prefer:wait window and the implicit polling has been dropping connections.
#
# allow_fallback_model is True — if Nano Banana Pro is at capacity, Replicate
# routes the request to bytedance/seedream-5 automatically (charged at that
# model's price). Both are strong for fabric-heavy product photography.
#
# Model schema (from Replicate as of March 2026):
#   prompt: str (required)
#   image_input: list of file objects (optional, up to 14)
#   aspect_ratio: "1:1" | "3:4" | "4:3" | "9:16" | "16:9"
#   resolution: "1K" | "2K" | "4K"
#   output_format: "png" | "jpg"
#   safety_filter_level: "block_low_and_above" | "block_medium_and_above" |
#                        "block_only_high"
#   allow_fallback_model: bool
# =============================================================================

import io
import os
import time

import replicate
import requests

import config

# Poll for up to 5 minutes — generations rarely exceed 90s but we leave
# headroom for capacity / fallback routing.
MAX_POLL_SECONDS = 300
POLL_INTERVAL_SECONDS = 3

# Capacity-retry policy (v1.1). Backoff doubles: 2, 4, 8, 16 minutes.
CAPACITY_RETRIES = 4
CAPACITY_BACKOFF_START = 120

# Only these failure shapes are worth retrying — they mean "later might work".
_RETRYABLE_MARKERS = (
    "high demand",            # E003 — Google capacity
    "ModelRateLimitError",
    "rate limit",
    "timed out after",        # our own poll timeout: model queued but crawling
    "overloaded",
    "temporarily unavailable",
    "503",
)


def _is_retryable(err):
    text = str(err)
    return any(m.lower() in text.lower() for m in _RETRYABLE_MARKERS)


def _client():
    """Return a Replicate client bound to the configured token."""
    token = config.REPLICATE_API_TOKEN
    if not token or "PASTE_YOUR" in token:
        raise RuntimeError(
            "REPLICATE_API_TOKEN is not set in config.py. "
            "Get one at https://replicate.com/account/api-tokens "
            "and paste it into config.py."
        )
    os.environ["REPLICATE_API_TOKEN"] = token
    return replicate.Client(api_token=token)


def _wait_for_prediction(client, prediction, max_seconds=MAX_POLL_SECONDS):
    """Poll a prediction until it succeeds, fails, or times out."""
    deadline = time.time() + max_seconds
    last_status = None
    while time.time() < deadline:
        # Refresh the prediction — the SDK returns a Prediction object with
        # a reload() method that re-fetches its state from the API.
        prediction = client.predictions.get(prediction.id)
        if prediction.status != last_status:
            last_status = prediction.status
        if prediction.status == "succeeded":
            return prediction
        if prediction.status in ("failed", "canceled"):
            err = prediction.error or "no error message"
            raise RuntimeError(f"Replicate prediction {prediction.status}: {err}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise RuntimeError(
        f"Replicate prediction timed out after {max_seconds}s "
        f"(last status: {last_status})"
    )


def generate_image_with_flux(product_image_bytes, reference_image_bytes_list, prompt):
    """Public entry point — retries capacity failures, see the changelog.

    Runs in a background thread (server.py), so sleeping minutes here blocks
    nobody. Total worst case ~30 min per image before a real ERROR lands on
    the row, versus the previous behaviour: fail in seconds and wait for a
    human to notice.
    """
    attempt = 0
    delay = CAPACITY_BACKOFF_START
    while True:
        try:
            return _generate_once(product_image_bytes, reference_image_bytes_list, prompt)
        except Exception as e:
            if attempt >= CAPACITY_RETRIES or not _is_retryable(e):
                raise
            attempt += 1
            print(f"  Capacity failure ({e}) — retry {attempt}/{CAPACITY_RETRIES} "
                  f"in {delay // 60} min", flush=True)
            time.sleep(delay)
            delay *= 2


def _generate_once(product_image_bytes, reference_image_bytes_list, prompt):
    """
    Generate a single image via the configured Replicate model.

    Function name kept for backwards compatibility — despite the name it
    now routes to whichever model config.REPLICATE_MODEL points at.

    Args:
        product_image_bytes: bytes of the product source image (always passed
            as the first input image).
        reference_image_bytes_list: list of bytes for additional reference
            images. Can be empty.
        prompt: text prompt describing the desired output.

    Returns:
        bytes of the generated image.

    Raises:
        RuntimeError on any Replicate error.
    """
    client = _client()

    input_files = [io.BytesIO(product_image_bytes)]
    for ref in reference_image_bytes_list:
        input_files.append(io.BytesIO(ref))

    # Create the prediction async. The SDK uploads file inputs automatically
    # and returns a Prediction handle immediately (no long wait).
    prediction = client.predictions.create(
        model=config.REPLICATE_MODEL,
        input={
            "prompt": prompt,
            "image_input": input_files,
            "aspect_ratio": config.IMAGE_ASPECT_RATIO,
            "resolution": config.IMAGE_RESOLUTION,
            "output_format": config.IMAGE_OUTPUT_FORMAT,
            "safety_filter_level": config.SAFETY_FILTER_LEVEL,
            "allow_fallback_model": True,
        },
    )

    prediction = _wait_for_prediction(client, prediction)
    output = prediction.output

    # Nano Banana Pro (and Seedream fallback) return a single URL string.
    if isinstance(output, list):
        if not output:
            raise RuntimeError("Replicate returned an empty output list")
        result = output[0]
    else:
        result = output

    if isinstance(result, str):
        resp = requests.get(result, timeout=120)
        resp.raise_for_status()
        return resp.content
    if hasattr(result, "read"):
        return result.read()
    raise RuntimeError(f"Unexpected Replicate output type: {type(result)}")
