#!/usr/bin/env python3
"""
Generate AI-powered release notes for Yt-RivoGUI using Google Gemini API.
Analyzes git commit log and diffs with context, generating a warm, cute, human-friendly summary in English.
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

# Models to attempt in order (supports user override via GEMINI_MODEL)
DEFAULT_MODELS = [
    os.getenv("GEMINI_MODEL", "").strip(),
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
MODELS = [m for m in DEFAULT_MODELS if m]

SYSTEM_PROMPT = """\
You are the official release notes writer for Yt-RivoGUI, a sleek, minimalist desktop YouTube and media downloader for Windows built with PySide6 and powered by yt-dlp technology.

Your task is to write the release notes for the new version in English.

Guidelines:
1. Tone: Warm, charming, cute, friendly, and human ("fofa, humana e descontraída"), yet clear and organized. Use cute and relevant emojis (like ✨, 🌸, 🚀, 💻, 🎧, 📦, 🌿, etc.) naturally throughout the text.
2. Length: Medium to long (around 300 to 500 words). Make it a pleasant read!
3. Focus: Clearly summarize the changes, bug fixes, UI improvements, and new features based on the git diffs and commit log provided.
4. Style: Explain the practical impact and benefits for the user. DO NOT dump raw code, commit hashes, or dry programming jargon. Make it understandable for regular humans and music/video enthusiasts.
5. Structure:
   - A sweet, welcoming opening greeting for this new version.
   - What's New & What Changed (broken down with cute subheadings or bullet points).
   - A friendly download note (recommending the standalone .zip for Windows 10/11 x64).
   - A heartwarming sign-off thanking everyone for using Yt-RivoGUI and supporting the project.
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


def get_git_changes(base_ref: str | None) -> tuple[str, str]:
    """Retrieve commit log and diff with 3 lines of context (-U3)."""
    range_spec = f"{base_ref}..HEAD" if base_ref else "HEAD~10..HEAD"

    # Commit log
    res = run_git("log", range_spec, "--oneline", "--no-merges")
    commit_log = res.stdout.strip() if res.returncode == 0 else ""

    if not commit_log:
        res = run_git("log", "-n", "10", "--oneline", "--no-merges")
        commit_log = res.stdout.strip() if res.returncode == 0 else "Recent updates to Yt-RivoGUI."

    # Git diff with context lines (-U3), filtering out binaries and builds
    diff_args = [
        "diff", "-U3", range_spec,
        "--",
        ":!*.whl", ":!*.ico", ":!*.png", ":!*.jpg", ":!*.jpeg", ":!*.svg",
        ":!*.zip", ":!*.tar.gz", ":!dist/*", ":!build/*", ":!package-lock.json"
    ]
    res = run_git(*diff_args)
    diff_text = res.stdout.strip() if res.returncode == 0 else ""

    if not diff_text:
        res = run_git("diff", "-U3", "HEAD^..HEAD", "--", ":!*.whl", ":!*.ico", ":!*.png", ":!dist/*", ":!build/*")
        diff_text = res.stdout.strip() if res.returncode == 0 else ""

    # Limit diff text length to prevent exceeding token limits (~35k chars)
    if len(diff_text) > 35000:
        diff_text = diff_text[:35000] + "\n\n... [diff truncated for brevity] ..."

    return commit_log, diff_text


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
            "maxOutputTokens": 2500,
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
                with urllib.request.urlopen(req, timeout=40) as resp:
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
                    print(f"[ai_release_notes] Model {model} returned 404, falling back to next model...", file=sys.stderr)
                    break  # Break retry loop to try the next model candidate

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
    commit_log, diff_text = get_git_changes(base_ref)

    ai_body = None
    if api_key:
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Release Version: {version}\n\n"
            f"Commit Log:\n{commit_log}\n\n"
            f"Code Diffs (with context):\n{diff_text}\n"
        )
        try:
            ai_body = call_gemini(api_key, prompt, max_retries=5, retry_delay=10)
        except Exception as err:
            print(f"[ai_release_notes] Warning: AI generation failed: {err}. Falling back to default format.", file=sys.stderr)

    if not ai_body:
        # Fallback friendly text when API key is not present or failed
        ai_body = (
            f"### ✨ Welcome to Yt-RivoGUI v{version}!\n\n"
            f"A fresh update for Yt-RivoGUI is here! This release brings improvements, fixes, "
            f"and polished features to make your video and audio downloading experience even smoother.\n\n"
            f"#### 🌸 Highlights in this release:\n"
            f"{chr(10).join(f'- {line}' for line in commit_log.splitlines()[:8])}\n\n"
            f"📦 **Download Note:** For the best experience on Windows 10/11 64-bit, download the "
            f"`Yt-RivoGUI-v{version}-windows.zip` archive, extract it, and launch `Yt-RivoGUI.exe`.\n\n"
            f"Thank you for your love and support! 💕"
        )

    # Wrap the full notes with nice badges and collapsible technical changelog
    notes_parts = [
        f"[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/brnalemusic/Yt-RivoGUI#quickstart) "
        f"[![Donate](https://img.shields.io/badge/Sponsor-InfinitePay-00E575?style=for-the-badge&logo=handshake&logoColor=black)](https://invoice.infinitepay.io/plans/brnale_music/bjLluwct3L)\n",
        ai_body,
        "\n---\n",
        "<details><summary><b>🛠️ Technical Commit Log</b></summary>\n\n",
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
