#!/usr/bin/env python3
"""
Email Signature Stripper - Phase 1: Single Email Signature Detection

Reads .eml files from a directory, detects and strips signatures,
and outputs a report showing the body, detected signature, and
confidence score for each email.

Usage:
    python email_signature_stripper.py <eml_directory> [--output report.txt]
"""

import os
import sys
import re
import email
import argparse
from email import policy
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class SignatureResult:
    """Result of signature detection on a single email."""
    body: str                   # Email body with signature stripped
    signature: str              # Detected signature text
    confidence: float           # 0.0 to 1.0
    method: str                 # Which detection method matched
    split_index: int            # Character index where the split occurred


# --- Detection Methods ---
# Each returns a SignatureResult or None.
# They are tried in priority order; first match wins.

def detect_explicit_separator(lines: list[str]) -> Optional[SignatureResult]:
    """
    Look for explicit signature separators: --, ___, ===, etc.
    These are strong indicators, especially '-- ' (note the trailing space)
    which is the RFC 3676 standard email signature delimiter.
    """
    separator_patterns = [
        re.compile(r'^--\s*$'),           # Standard: -- or --<space>
        re.compile(r'^_{3,}\s*$'),        # ___...
        re.compile(r'^={3,}\s*$'),        # ===...
        re.compile(r'^-{3,}\s*$'),        # ---...
    ]

    # Scan from bottom up — we want the LAST separator, not one mid-body
    # Skip line 0 (first line is never a separator)
    for i in range(len(lines) - 1, 0, -1):
        for pattern in separator_patterns:
            if pattern.match(lines[i].strip() if lines[i].strip() else lines[i]):
                # Check that there's actually content after the separator
                remaining = '\n'.join(lines[i + 1:]).strip()
                if remaining and len(remaining) < 5000:
                    body = '\n'.join(lines[:i]).rstrip()
                    sig = '\n'.join(lines[i:]).strip()
                    return SignatureResult(
                        body=body,
                        signature=sig,
                        confidence=0.95,
                        method="explicit_separator",
                        split_index=i
                    )
    return None


def detect_closing_phrase(lines: list[str]) -> Optional[SignatureResult]:
    """
    Look for common closing phrases (Thanks, Best regards, etc.)
    followed by a structural shift to short, non-sentence lines.
    """
    closing_phrases = [
        r'^thanks[\s,!.]*$',
        r'^thank\s+you[\s,!.]*$',
        r'^best[\s,]*regards?[\s,!.]*$',
        r'^kind[\s,]*regards?[\s,!.]*$',
        r'^warm[\s,]*regards?[\s,!.]*$',
        r'^regards[\s,!.]*$',
        r'^sincerely[\s,!.]*$',
        r'^cheers[\s,!.]*$',
        r'^best[\s,!.]*$',
        r'^all\s+the\s+best[\s,!.]*$',
        r'^take\s+care[\s,!.]*$',
        r'^respectfully[\s,!.]*$',
        r'^cordially[\s,!.]*$',
        r'^v/r[\s,!.]*$',
    ]
    closing_pattern = re.compile('|'.join(closing_phrases), re.IGNORECASE)

    # Scan from bottom up — need a wide window because corporate emails
    # can have very long disclaimers/legal text below the closing phrase
    search_limit = max(0, len(lines) - 80)

    for i in range(len(lines) - 1, search_limit, -1):
        stripped = lines[i].strip()
        if closing_pattern.match(stripped):
            # Found a closing phrase — but the name on the next line is part
            # of the sign-off, not the signature. Look for a short name line
            # immediately after the closing phrase and include it in the body.
            sig_start = i  # default: signature starts at closing phrase
            name_included = False

            # Scan ahead past blank lines to find the name line
            for j in range(i + 1, min(i + 3, len(lines))):
                stripped_j = lines[j].strip()
                if not stripped_j:
                    continue  # skip blank lines
                # If it's a short line (likely a name) with no contact patterns
                if (len(stripped_j) < 40
                        and not re.search(r'[\w.+-]+@[\w.-]+\.\w+', stripped_j)
                        and not re.search(r'[\(]?\d{3}[\)\s.-]?\s*\d{3}[\s.-]?\d{4}', stripped_j)
                        and not re.search(r'https?://\S+', stripped_j)
                        and not stripped_j.startswith(('_', '-', '='))):
                    sig_start = j + 1  # body includes the name line
                    name_included = True
                break  # only check the first non-empty line

            remaining = '\n'.join(lines[sig_start:]).strip()
            # A closing phrase is a strong signal. Allow generous content below
            # because corporate emails can have long disclaimers after the sig.
            if remaining is not None and len(remaining) < 10000:
                body = '\n'.join(lines[:sig_start]).rstrip()
                sig = '\n'.join(lines[sig_start:]).strip()
                if sig:
                    return SignatureResult(
                        body=body,
                        signature=sig,
                        confidence=0.90,
                        method="closing_phrase",
                        split_index=sig_start
                    )
    return None


def detect_sent_from(lines: list[str]) -> Optional[SignatureResult]:
    """
    Detect 'Sent from my iPhone/Outlook/etc.' patterns.
    """
    sent_from_pattern = re.compile(
        r'^sent\s+from\s+(my\s+)?(iphone|ipad|galaxy|samsung|pixel|android|'
        r'outlook|mail|yahoo|aol|protonmail|thunderbird)',
        re.IGNORECASE
    )

    for i in range(len(lines) - 1, max(0, len(lines) - 10), -1):
        if sent_from_pattern.match(lines[i].strip()):
            body = '\n'.join(lines[:i]).rstrip()
            sig = '\n'.join(lines[i:]).strip()
            return SignatureResult(
                body=body,
                signature=sig,
                confidence=0.95,
                method="sent_from",
                split_index=i
            )
    return None


def detect_structural_shift(lines: list[str]) -> Optional[SignatureResult]:
    """
    Scan from the bottom up looking for the transition from
    short contact-info lines to normal prose. This catches signatures
    that don't have explicit separators or closing phrases.
    """
    # Patterns that suggest contact information
    contact_patterns = [
        re.compile(r'[\w.+-]+@[\w.-]+\.\w+'),          # Email address
        re.compile(r'[\(]?\d{3}[\)\s.-]?\s*\d{3}[\s.-]?\d{4}'),  # Phone number
        re.compile(r'https?://\S+'),                     # URL
        re.compile(r'www\.\S+'),                         # www URL
        re.compile(r'\b(ext|fax|tel|cell|mobile|office|direct)[\s.:]+', re.IGNORECASE),  # Phone labels
        re.compile(r'\b(LLC|Inc|Corp|Ltd|Co\.|Group|Associates|Consulting)\b', re.IGNORECASE),  # Company suffixes
    ]

    # Title patterns
    title_patterns = re.compile(
        r'\b(manager|director|president|vp|vice\s+president|ceo|cfo|cto|coo|'
        r'supervisor|coordinator|specialist|analyst|engineer|consultant|'
        r'associate|assistant|administrator|broker|agent|realtor|'
        r'superintendent|technician|foreman|estimator|inspector)\b',
        re.IGNORECASE
    )

    if len(lines) < 3:
        return None

    # Work from the bottom up, scoring each line
    sig_start = None
    consecutive_sig_lines = 0
    min_consecutive = 2  # Need at least 2 consecutive signature-like lines

    for i in range(len(lines) - 1, max(0, len(lines) - 25), -1):
        line = lines[i].strip()

        if not line:
            # Blank lines within a signature block are OK
            if consecutive_sig_lines > 0:
                continue
            else:
                continue

        is_sig_line = False

        # Short line (typical of signature blocks)
        if len(line) < 80:
            # Check for contact patterns
            for pattern in contact_patterns:
                if pattern.search(line):
                    is_sig_line = True
                    break

            # Check for title patterns
            if not is_sig_line and title_patterns.search(line):
                is_sig_line = True

            # Very short line that's not a sentence (no ending punctuation
            # typical of prose — periods in abbreviations are OK)
            if not is_sig_line and len(line) < 50 and not line.endswith(('.', '?', '!')):
                # Could be a name line or short title — only count if we
                # already have signature lines below it
                if consecutive_sig_lines >= min_consecutive:
                    is_sig_line = True

        if is_sig_line:
            consecutive_sig_lines += 1
            sig_start = i
        else:
            # If we've accumulated enough signature lines, we found it
            if consecutive_sig_lines >= min_consecutive:
                break
            else:
                consecutive_sig_lines = 0
                sig_start = None

    if sig_start is not None and consecutive_sig_lines >= min_consecutive:
        body = '\n'.join(lines[:sig_start]).rstrip()
        sig = '\n'.join(lines[sig_start:]).strip()

        # Score confidence based on how many contact patterns we found
        contact_count = 0
        for line in lines[sig_start:]:
            for pattern in contact_patterns:
                if pattern.search(line):
                    contact_count += 1
                    break

        confidence = min(0.85, 0.55 + (contact_count * 0.10))

        return SignatureResult(
            body=body,
            signature=sig,
            confidence=confidence,
            method="structural_shift",
            split_index=sig_start
        )

    return None


def _looks_like_signature_block(lines: list[str]) -> bool:
    """Helper: check if a set of lines looks like a signature block."""
    non_empty = [l.strip() for l in lines if l.strip()]
    if not non_empty:
        return False

    # Most lines should be relatively short
    short_lines = sum(1 for l in non_empty if len(l) < 80)
    return short_lines / len(non_empty) >= 0.7


# --- Main Detection Pipeline ---

def detect_signature(email_text: str) -> SignatureResult:
    """
    Run detection methods in two tiers:
    - Tier 1 (strong signals): explicit_separator, sent_from, closing_phrase
      These run and the earliest split wins among them.
    - Tier 2 (fallback): structural_shift
      Only used if no Tier 1 detector matches.
    """
    lines = email_text.split('\n')

    # Tier 1: Strong signal detectors — earliest split wins
    tier1_detectors = [
        detect_explicit_separator,
        detect_sent_from,
        detect_closing_phrase,
    ]

    tier1_matches = []
    for detector in tier1_detectors:
        result = detector(lines)
        if result:
            tier1_matches.append(result)

    if tier1_matches:
        best = min(tier1_matches, key=lambda r: (r.split_index, -r.confidence))
        if len(tier1_matches) > 1 and best.confidence < 0.95:
            best.confidence = min(0.98, best.confidence + 0.05)
            best.method = f"{best.method} (+{len(tier1_matches)-1} other)"
        return best

    # Tier 2: Fallback to structural analysis
    result = detect_structural_shift(lines)
    if result:
        return result

    # No signature detected
    return SignatureResult(
        body=email_text.rstrip(),
        signature="[No signature detected]",
        confidence=0.0,
        method="none",
        split_index=-1
    )


# --- EML Parsing ---

def parse_eml(filepath: str) -> dict:
    """Parse an .eml file and return relevant fields."""
    with open(filepath, 'rb') as f:
        msg = email.message_from_binary_file(f, policy=policy.default)

    result = {
        'subject': msg.get('Subject', '(No Subject)'),
        'from': msg.get('From', '(Unknown)'),
        'to': msg.get('To', '(Unknown)'),
        'date': msg.get('Date', '(Unknown)'),
        'body': '',
    }

    # Extract plain text body
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == 'text/plain':
                charset = part.get_content_charset() or 'utf-8'
                try:
                    result['body'] = part.get_payload(decode=True).decode(charset, errors='replace')
                except Exception:
                    result['body'] = part.get_payload(decode=True).decode('utf-8', errors='replace')
                break
        # If no plain text found, try HTML (basic strip)
        if not result['body']:
            for part in msg.walk():
                if part.get_content_type() == 'text/html':
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        html = part.get_payload(decode=True).decode(charset, errors='replace')
                    except Exception:
                        html = part.get_payload(decode=True).decode('utf-8', errors='replace')
                    # Basic HTML tag stripping
                    result['body'] = re.sub(r'<[^>]+>', '', html)
                    result['body'] = re.sub(r'\n\s*\n', '\n\n', result['body']).strip()
                    break
    else:
        charset = msg.get_content_charset() or 'utf-8'
        try:
            result['body'] = msg.get_payload(decode=True).decode(charset, errors='replace')
        except Exception:
            result['body'] = msg.get_payload(decode=True).decode('utf-8', errors='replace')

    return result


# --- Report Generation ---

def generate_report(results: list[dict], output_path: str):
    """Write a human-readable report of all results."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("EMAIL SIGNATURE DETECTION REPORT\n")
        f.write("=" * 80 + "\n\n")

        # Summary
        total = len(results)
        detected = sum(1 for r in results if r['result'].method != 'none')
        high_conf = sum(1 for r in results if r['result'].confidence >= 0.85)
        med_conf = sum(1 for r in results if 0.5 <= r['result'].confidence < 0.85)
        low_conf = sum(1 for r in results if 0 < r['result'].confidence < 0.5)
        no_sig = sum(1 for r in results if r['result'].method == 'none')

        f.write(f"Total emails processed: {total}\n")
        f.write(f"Signatures detected:    {detected}\n")
        f.write(f"  High confidence (≥85%): {high_conf}\n")
        f.write(f"  Medium confidence:      {med_conf}\n")
        f.write(f"  Low confidence:         {low_conf}\n")
        f.write(f"No signature found:     {no_sig}\n\n")

        # Method breakdown
        methods = {}
        for r in results:
            m = r['result'].method
            methods[m] = methods.get(m, 0) + 1
        f.write("Detection methods used:\n")
        for method, count in sorted(methods.items()):
            f.write(f"  {method}: {count}\n")
        f.write("\n")

        f.write("=" * 80 + "\n\n")

        # Individual results
        for i, r in enumerate(results, 1):
            res = r['result']
            f.write(f"{'─' * 80}\n")
            f.write(f"EMAIL {i}: {r['filename']}\n")
            f.write(f"{'─' * 80}\n")
            f.write(f"From:       {r['email']['from']}\n")
            f.write(f"Subject:    {r['email']['subject']}\n")
            f.write(f"Date:       {r['email']['date']}\n")
            f.write(f"Confidence: {res.confidence:.0%}\n")
            f.write(f"Method:     {res.method}\n\n")

            f.write("--- BODY (signature stripped) ---\n")
            f.write(res.body if res.body else "(empty)")
            f.write("\n\n")

            f.write("--- DETECTED SIGNATURE ---\n")
            f.write(res.signature)
            f.write("\n\n")

    print(f"Report written to: {output_path}")


# --- Main ---

def main(eml_dir: str = None, output: str = 'signature_report.txt'):
    if eml_dir is None:
        # Fall back to command-line args if not called directly
        parser = argparse.ArgumentParser(
            description="Detect and strip email signatures from .eml files."
        )
        parser.add_argument(
            'eml_dir',
            help="Directory containing .eml files"
        )
        parser.add_argument(
            '--output', '-o',
            default='signature_report.txt',
            help="Output report file (default: signature_report.txt)"
        )
        args = parser.parse_args()
        eml_dir = args.eml_dir
        output = args.output

    eml_dir = Path(eml_dir)
    if not eml_dir.is_dir():
        print(f"Error: {eml_dir} is not a directory.")
        sys.exit(1)

    eml_files = sorted(eml_dir.glob('*.eml'))
    if not eml_files:
        print(f"No .eml files found in {eml_dir}")
        sys.exit(1)

    print(f"Found {len(eml_files)} .eml files in {eml_dir}")
    print("Processing...\n")

    results = []
    for filepath in eml_files:
        print(f"  {filepath.name}...", end=" ")
        try:
            email_data = parse_eml(str(filepath))
            sig_result = detect_signature(email_data['body'])
            results.append({
                'filename': filepath.name,
                'email': email_data,
                'result': sig_result,
            })
            print(f"[{sig_result.confidence:.0%} - {sig_result.method}]")
        except Exception as e:
            print(f"[ERROR: {e}]")
            results.append({
                'filename': filepath.name,
                'email': {'from': '?', 'subject': '?', 'date': '?', 'body': ''},
                'result': SignatureResult(
                    body=f"ERROR: {e}",
                    signature="",
                    confidence=0.0,
                    method="error",
                    split_index=-1
                ),
            })

    print()
    generate_report(results, output)

    # Print quick summary to console
    detected = sum(1 for r in results if r['result'].method != 'none')
    print(f"\nDone! {detected}/{len(results)} signatures detected.")
    print(f"Review the report at: {output}")




if __name__ == '__main__':
    main(eml_dir=r"/home/doug/Documents/Test Emails", output="report.txt")