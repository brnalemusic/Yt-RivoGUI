#!/usr/bin/env python3
"""
Generate AI-powered release notes for Yt-RivoGUI using Google Gemini API.
Analyzes git commit log and diffs with context, generating a warm, human-friendly,
structured summary in English without emojis, using clean markdown, lists, and tables.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Models to attempt in order (gemini-3.5-flash-lite is primary, supports user override via GEMINI_MODEL)
DEFAULT_MODELS = [
    os.getenv("GEMINI_MODEL", "").strip(),
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]
MODELS = [m for m in DEFAULT_MODELS if m]

SYSTEM_PROMPT = """\
You are the release notes author for Yt-RivoGUI, a minimalist desktop YouTube and media downloader for Windows built with PySide6 and powered by yt-dlp technology.

Your task is to write warm, human, engaging, and beautifully structured release notes in English for this new version.

CRITICAL CONSTRAINTS:
1. STRICTLY NO EMOJIS: Do NOT use any emojis, pictograms, or emoji symbols anywhere in the response. Zero emojis. The warmth, friendliness, and charm must come purely from your phrasing, tone, and vocabulary.
2. Tone: Warm, human, welcoming, conversational, and thoughtful ("humana, calorosa e descontraida"), yet clean, polished, and easy to follow.
3. Rich Markdown Structure:
   - Use clear headings (## and ###).
   - Include a neat Markdown summary table comparing or categorizing the main updates (for example: | Component | Changes | Impact on You |).
   - Use clean, well-spaced bulleted lists for detailed feature and bugfix breakdowns.
   - Use bold and italic text purposefully to emphasize key benefits.
4. Input Analysis:
   - You will receive both the list of all commit names and the full code diff (with 3 lines of context) comparing the previous version to the current version.
   - Synthesize what was actually added, improved, fixed, or redesigned.
   - Focus on practical benefits and user experience.
   - DO NOT copy raw code, syntax blocks, diff patches, or raw git hashes into the main release narrative.
5. Structure:
   - Warm, friendly introduction welcoming users to the update.
   - Summary Table: A concise table categorizing the key changes.
   - Detailed Highlights: Organized bullet points explaining what is new, improved, or fixed.
   - Download & Setup Guide: Clear instructions recommending the standalone Windows .zip package (Windows 10 / 11 64-bit).
   - Sincere, appreciative closing thanking users for their support and feedback.
"""


def run_git(*args: str) -> subprocess.CompletedProcess[str]:
    """Helper to run git with explicit utf-8 encoding and safe error handling."""
    return subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def get_base_ref() -> str | None:
    """Find the previous release tag or ancestor commit for diffing."""
    # 1. Look for the previous tag before current commit
    try:
        res = run_git("describe", "--tags", "--abbrev=0", "HEAD^")
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    # 2. Look for any tag in the repo
    try:
        res = run_git("tag", "--sort=-creatordate")
        if res.returncode == 0:
            for t in res.stdout.splitlines():
                t = t.strip()
                if t and t != "latest":
                    return t
    except Exception:
        pass

    # 3. Fallback: recent ancestor or root commit
    try:
        res = run_git("rev-parse", "HEAD~10")
        if res.returncode == 0:
            return "HEAD~10"
    except Exception:
        pass

    return None


def get_git_changes(base_ref: str | None) -> tuple[str, str, str]:
    """
    Retrieve commit names, commit log with hashes, and diff with context (-U3).
    Returns (commit_names, commit_log, diff_text).
    """
    range_spec = f"{base_ref}..HEAD" if base_ref else "HEAD~10..HEAD"

    # Commit names only
    res_names = run_git("log", range_spec, "--pretty=format:%s", "--no-merges")
    commit_names = res_names.stdout.strip() if res_names.returncode == 0 else ""

    # Commit log with short hashes
    res_log = run_git("log", range_spec, "--oneline", "--no-merges")
    commit_log = res_log.stdout.strip() if res_log.returncode == 0 else ""

    if not commit_log:
        res_log = run_git("log", "-n", "10", "--oneline", "--no-merges")
        commit_log = res_log.stdout.strip() if res_log.returncode == 0 else "Recent updates to Yt-RivoGUI."
        res_names = run_git("log", "-n", "10", "--pretty=format:%s", "--no-merges")
        commit_names = res_names.stdout.strip() if res_names.returncode == 0 else commit_log

    # Full git diff with 3 lines of context (-U3), filtering out binary files and build artifacts
    diff_args = [
        "diff", "-U3", range_spec,
        "--",
        ":!*.whl", ":!*.ico", ":!*.png", ":!*.jpg", ":!*.jpeg", ":!*.svg",
        ":!*.zip", ":!*.tar.gz", ":!dist/*", ":!build/*", ":!package-lock.json"
    ]
    res_diff = run_git(*diff_args)
    diff_text = res_diff.stdout.strip() if res_diff.returncode == 0 else ""

    if not diff_text:
        res_diff = run_git("diff", "-U3", "HEAD^..HEAD", "--", ":!*.whl", ":!*.ico", ":!*.png", ":!dist/*", ":!build/*")
        diff_text = res_diff.stdout.strip() if res_diff.returncode == 0 else ""

    # Limit diff text length to prevent exceeding API limits (~40k chars)
    if len(diff_text) > 40000:
        diff_text = diff_text[:40000] + "\n\n... [diff truncated for brevity] ..."

    return commit_names, commit_log, diff_text


def call_gemini(api_key: str, prompt: str, max_retries: int = 5, retry_delay: int = 10) -> str:
    """Call Google Gemini API with up to 5 retries every 10 seconds."""
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 3000,
        }
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    last_error = None
    for model in MODELS:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        print(f"[ai_release_notes] Using model: {model}")

        for attempt in range(1, max_retries + 1):
            print(f"[ai_release_notes] Request attempt {attempt}/{max_retries}...")
            req = urllib.request.Request(
                endpoint,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            if text:
                                print("[ai_release_notes] Success! AI release notes generated.")
                                return text
                    raise ValueError(f"Unexpected response structure: {resp_data}")

            except urllib.error.HTTPError as e:
                err_msg = ""
                try:
                    err_msg = e.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
                print(f"[ai_release_notes] HTTP error {e.code}: {e.reason} ({err_msg})", file=sys.stderr)
                last_error = f"HTTP {e.code}: {err_msg}"

                if e.code == 404:
                    print(f"[ai_release_notes] Model '{model}' not found (404), trying next model...", file=sys.stderr)
                    break  # Break retry loop for this model and fall back to the next model in MODELS

                if attempt < max_retries:
                    print(f"[ai_release_notes] Waiting {retry_delay}s before retry...", file=sys.stderr)
                    time.sleep(retry_delay)

            except Exception as exc:
                print(f"[ai_release_notes] Request error: {exc}", file=sys.stderr)
                last_error = str(exc)
                if attempt < max_retries:
                    print(f"[ai_release_notes] Waiting {retry_delay}s before retry...", file=sys.stderr)
                    time.sleep(retry_delay)

    raise RuntimeError(f"All Gemini API attempts failed. Last error: {last_error}")


def generate_notes(version: str, api_key: str | None = None) -> str:
    """Generate complete release notes markdown."""
    base_ref = get_base_ref()
    commit_names, commit_log, diff_text = get_git_changes(base_ref)

    ai_body = None
    if api_key:
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Release Version: {version}\n\n"
            f"List of Commit Titles in this Release:\n{commit_names}\n\n"
            f"Commit Log (with hashes):\n{commit_log}\n\n"
            f"Full Code Diffs (with 3 lines of context):\n{diff_text}\n"
        )
        try:
            ai_body = call_gemini(api_key, prompt, max_retries=5, retry_delay=10)
        except Exception as err:
            print(f"[ai_release_notes] Warning: AI generation failed: {err}. Falling back to default format.", file=sys.stderr)

    if not ai_body:
        # Fallback friendly text (strictly without emojis) when API key is not present or failed
        table_rows = []
        for line in commit_names.splitlines()[:6]:
            clean_line = line.strip().lstrip("-* ").replace("|", "/")
            if clean_line:
                table_rows.append(f"| Update | {clean_line} | Enhanced stability and performance |")
        table_str = "\n".join(table_rows)

        ai_body = (
            f"### Welcome to Yt-RivoGUI v{version}\n\n"
            f"We are happy to present a new update for Yt-RivoGUI. This release brings improvements, "
            f"refinements, and fixes to ensure your media downloading experience remains smooth and dependable.\n\n"
            f"#### Summary of Changes\n\n"
            f"| Category | Change | Impact |\n"
            f"| :--- | :--- | :--- |\n"
            f"{table_str}\n\n"
            f"#### Highlights in this Version\n\n"
            f"{chr(10).join(f'- {line}' for line in commit_names.splitlines()[:8])}\n\n"
            f"**Download Note:** For the best experience on Windows 10 and 11 64-bit, download the "
            f"`Yt-RivoGUI-v{version}-windows.zip` archive, extract it to a folder of your choice, and launch `Yt-RivoGUI.exe`.\n\n"
            f"Thank you for using Yt-RivoGUI and for your continued support and feedback."
        )

    # Wrap the full notes with nice badges and collapsible technical changelog
    notes_parts = [
        f"[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/brnalemusic/Yt-RivoGUI#quickstart) "
        f"[![Donate](https://img.shields.io/badge/Sponsor-InfinitePay-00E575?style=for-the-badge&logo=handshake&logoColor=black)](https://invoice.infinitepay.io/plans/brnale_music/bjLluwct3L)\n",
        ai_body,
        "\n---\n",
        "<details><summary><b>Technical Commit Log</b></summary>\n\n",
        "```text\n",
        commit_log,
        "\n```\n</details>\n"
    ]

    return "\n".join(notes_parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AI release notes for Yt-RivoGUI")
    parser.add_argument("-v", "--version", default="0.0.1.0", help="Release version string")
    parser.add_argument("-o", "--output", default="RELEASE_NOTES", help="Path to write the release notes file")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[ai_release_notes] Notice: GEMINI_API_KEY environment variable is not set. Generating fallback notes.", file=sys.stderr)

    notes = generate_notes(version=args.version, api_key=api_key)

    out_path = Path(args.output).resolve()
    out_path.write_text(notes, encoding="utf-8")
    print(f"[ai_release_notes] Release notes written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
