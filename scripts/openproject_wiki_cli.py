#!/usr/bin/env python3
"""Browser-based OpenProject wiki operations using Playwright.

This script uses direct browser automation (Playwright) to manage
OpenProject wiki pages through the web UI, bypassing API limitations.

Requires: pip install playwright python-dotenv
          playwright install chromium
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_a, **_kw):
        return False

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
except ModuleNotFoundError:
    sync_playwright = None  # type: ignore[assignment,misc]
    PwTimeout = Exception  # type: ignore[assignment,misc]


class WikiError(Exception):
    """Raised when wiki browser automation fails."""


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise WikiError(f"Environment variable {name} is required but not set.")
    return value


def _launch_and_login(pw, *, visible: bool = False):
    """Launch browser, log in to OpenProject, return (browser, page)."""
    base_url = _require_env("OPENPROJECT_BASE_URL").rstrip("/")
    username = _require_env("OPENPROJECT_WIKI_USERNAME")
    password = _require_env("OPENPROJECT_WIKI_PASSWORD")

    try:
        browser = pw.chromium.launch(headless=not visible)
    except Exception as exc:
        if "Executable doesn't exist" in str(exc) or "browserType.launch" in str(exc):
            raise WikiError(
                "Chromium not installed. Run: playwright install chromium"
            ) from exc
        raise
    page = browser.new_page()
    page.set_default_timeout(60000)
    page.set_default_navigation_timeout(60000)

    # Navigate to login
    page.goto(f"{base_url}/login", wait_until="networkidle", timeout=60000)

    # OpenProject 17 may show a "Sign in" button that opens the login form
    username_field = page.query_selector("#username-pulldown")
    if not username_field or not username_field.is_visible():
        signin_btn = page.locator("text=Sign in").first
        if signin_btn.is_visible():
            signin_btn.click()
            page.wait_for_selector("#username-pulldown", state="visible", timeout=10000)

    page.fill("#username-pulldown", username)
    page.fill("#password-pulldown", password)
    # The login form lives inside a dialog overlay — use the nav dialog's submit button
    page.locator("dialog:visible").get_by_role("button", name="Sign in").click()
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # Redirect after login may not work — force navigate to home
    if "/login" in page.url:
        page.goto(base_url, wait_until="networkidle")
        time.sleep(2)

    # Final check — if still on login, credentials are wrong
    if "/login" in page.url:
        browser.close()
        raise WikiError("Login failed. Check OPENPROJECT_WIKI_USERNAME and OPENPROJECT_WIKI_PASSWORD.")

    return browser, page


def _wiki_url(project: str) -> str:
    base_url = _require_env("OPENPROJECT_BASE_URL").rstrip("/")
    return f"{base_url}/projects/{project}/wiki"


def _markdown_to_html(md: str) -> str:
    """Convert basic markdown to HTML for CKEditor injection."""
    import re
    lines = md.split("\n")
    html_parts: list[str] = []
    in_list = False
    in_table = False
    table_header_done = False

    for line in lines:
        stripped = line.strip()

        # Empty line — close list if open
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            if in_table:
                html_parts.append("</tbody></table>")
                in_table = False
                table_header_done = False
            continue

        # Table row
        if "|" in stripped and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Skip separator rows like |---|---|
            if all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            if not in_table:
                html_parts.append('<table><thead>')
                in_table = True
                table_header_done = False
            if not table_header_done:
                html_parts.append("<tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr>")
                html_parts.append("</thead><tbody>")
                table_header_done = True
            else:
                html_parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue

        # Close table if line is not a table row
        if in_table:
            html_parts.append("</tbody></table>")
            in_table = False
            table_header_done = False

        # Headings
        m = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if m:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            level = len(m.group(1))
            html_parts.append(f"<h{level}>{m.group(2)}</h{level}>")
            continue

        # Unordered list items
        m = re.match(r'^[-*]\s+(.*)', stripped)
        if m:
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item = m.group(1)
            # Bold
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            html_parts.append(f"<li>{item}</li>")
            continue

        # Ordered list items
        m = re.match(r'^\d+\.\s+(.*)', stripped)
        if m:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            item = m.group(1)
            item = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', item)
            html_parts.append(f"<p>{item}</p>")
            continue

        # Horizontal rule
        if re.match(r'^---+$', stripped):
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append("<hr>")
            continue

        # Regular paragraph — handle inline bold
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        para = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', stripped)
        html_parts.append(f"<p>{para}</p>")

    if in_list:
        html_parts.append("</ul>")
    if in_table:
        html_parts.append("</tbody></table>")

    return "\n".join(html_parts)


def cmd_write_wiki(args: argparse.Namespace) -> None:
    """Create or update a wiki page via Playwright."""
    if sync_playwright is None:
        raise WikiError("playwright is not installed. Run: pip install playwright && playwright install chromium")

    project = args.project or os.getenv("OPENPROJECT_DEFAULT_PROJECT", "").strip()
    if not project:
        raise WikiError("--project is required (or set OPENPROJECT_DEFAULT_PROJECT).")

    title = args.title.strip()
    if not title:
        raise WikiError("--title is required.")

    if args.content_file:
        content_path = Path(args.content_file)
        if not content_path.is_file():
            raise WikiError(f"Content file not found: {args.content_file}")
        content = content_path.read_text(encoding="utf-8")
    elif args.content:
        content = args.content
    else:
        raise WikiError("Provide --content or --content-file.")

    base_url = _require_env("OPENPROJECT_BASE_URL").rstrip("/")
    print(f"Writing wiki page '{title}' to project '{project}'...")

    with sync_playwright() as pw:
        browser, page = _launch_and_login(pw, visible=getattr(args, "visible", False))
        try:
            slug = title.replace(" ", "_")
            page.goto(f"{base_url}/projects/{project}/wiki/{slug}", wait_until="networkidle")
            time.sleep(2)

            page_title = page.title() or ""
            page_url = page.url
            is_create = "Create new wiki page" in page_title

            if is_create:
                # We're on the create form — fill title
                title_input = page.query_selector("#page_title")
                if title_input and title_input.is_visible():
                    title_input.fill(title)
            else:
                # Page exists — navigate directly to the edit URL
                edit_url = f"{base_url}/projects/{project}/wiki/{slug}/edit"
                page.goto(edit_url, wait_until="networkidle")
                time.sleep(3)

            # Fill CKEditor content — try multiple selectors
            ck_editor = (
                page.query_selector(".ck-editor__editable")
                or page.query_selector("[contenteditable='true']")
            )
            textarea = (
                page.query_selector("#content_text")
                or page.query_selector("textarea#content_text")
            ) if not ck_editor else None

            if ck_editor and ck_editor.is_visible():
                # Convert markdown to basic HTML for CKEditor
                html = _markdown_to_html(content)
                # Inject via CKEditor API or innerHTML
                injected = page.evaluate("""(html) => {
                    // Try CKEditor 5 API first
                    const editable = document.querySelector('.ck-editor__editable');
                    if (editable && editable.ckeditorInstance) {
                        editable.ckeditorInstance.setData(html);
                        return 'ckeditor-api';
                    }
                    // Fallback: set innerHTML directly
                    if (editable) {
                        editable.innerHTML = html;
                        editable.dispatchEvent(new Event('input', {bubbles: true}));
                        return 'innerhtml';
                    }
                    return 'failed';
                }""", html)
                if injected == "failed":
                    browser.close()
                    raise WikiError("Could not inject content into CKEditor.")
            elif textarea and textarea.is_visible():
                textarea.fill(content)
            else:
                browser.close()
                raise WikiError("Could not find editor on the page.")

            # Click Save
            save_btn = page.locator("button", has_text="Save").first
            if save_btn.is_visible():
                save_btn.click()
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                print(f"Wiki page '{title}' saved successfully.")
                print(f"URL: {base_url}/projects/{project}/wiki/{slug}")
            else:
                browser.close()
                raise WikiError("Could not find Save button on the page.")

        except PwTimeout as exc:
            raise WikiError(f"Browser timeout: {exc}") from exc
        finally:
            browser.close()


def cmd_read_wiki(args: argparse.Namespace) -> None:
    """Read a wiki page via Playwright."""
    if sync_playwright is None:
        raise WikiError("playwright is not installed.")

    project = args.project or os.getenv("OPENPROJECT_DEFAULT_PROJECT", "").strip()
    if not project:
        raise WikiError("--project is required (or set OPENPROJECT_DEFAULT_PROJECT).")

    title = args.title.strip()
    if not title:
        raise WikiError("--title is required.")

    base_url = _require_env("OPENPROJECT_BASE_URL").rstrip("/")
    slug = title.replace(" ", "_")

    print(f"Reading wiki page '{title}'...")

    with sync_playwright() as pw:
        browser, page = _launch_and_login(pw, visible=getattr(args, "visible", False))
        try:
            page.goto(f"{base_url}/projects/{project}/wiki/{slug}", wait_until="networkidle")
            time.sleep(1)

            # Extract wiki content
            content_el = (
                page.query_selector('.wiki-content')
                or page.query_selector('#content .wiki')
                or page.query_selector('.content--wiki')
                or page.query_selector('#wiki-content')
                or page.query_selector('.op-uc-container')
            )
            if content_el:
                print(content_el.inner_text())
            else:
                print("Could not find wiki content on the page.")
                print(f"Page URL: {page.url}")
        except PwTimeout as exc:
            raise WikiError(f"Browser timeout: {exc}") from exc
        finally:
            browser.close()


def cmd_list_wiki(args: argparse.Namespace) -> None:
    """List wiki pages via Playwright."""
    if sync_playwright is None:
        raise WikiError("playwright is not installed.")

    project = args.project or os.getenv("OPENPROJECT_DEFAULT_PROJECT", "").strip()
    if not project:
        raise WikiError("--project is required (or set OPENPROJECT_DEFAULT_PROJECT).")

    base_url = _require_env("OPENPROJECT_BASE_URL").rstrip("/")

    print(f"Listing wiki pages for project '{project}'...")

    with sync_playwright() as pw:
        browser, page = _launch_and_login(pw, visible=getattr(args, "visible", False))
        try:
            page.goto(f"{base_url}/projects/{project}/wiki", wait_until="networkidle")
            time.sleep(1)

            # Look for the page index / table of contents
            links = page.query_selector_all('.wiki-page--index a, .pages-hierarchy a, .toc a, a[href*="/wiki/"]')
            seen = set()
            for link in links:
                text = (link.inner_text() or "").strip()
                href = link.get_attribute("href") or ""
                if text and "/wiki/" in href and text not in seen:
                    seen.add(text)
                    print(f"  - {text}")

            if not seen:
                print("  No wiki pages found (or page index not accessible).")
        except PwTimeout as exc:
            raise WikiError(f"Browser timeout: {exc}") from exc
        finally:
            browser.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="OpenProject wiki operations via browser automation (Playwright)."
    )
    sub = parser.add_subparsers(dest="command")

    wp = sub.add_parser("write-wiki", help="Create or update a wiki page.")
    wp.add_argument("--project", help="Project identifier.")
    wp.add_argument("--title", required=True, help="Wiki page title.")
    wp.add_argument("--content", help="Inline wiki content.")
    wp.add_argument("--content-file", help="Path to file containing wiki content.")
    wp.add_argument("--visible", action="store_true", help="Show browser window (for debugging).")

    rp = sub.add_parser("read-wiki", help="Read a wiki page.")
    rp.add_argument("--project", help="Project identifier.")
    rp.add_argument("--title", required=True, help="Wiki page title.")
    rp.add_argument("--visible", action="store_true", help="Show browser window (for debugging).")

    lp = sub.add_parser("list-wiki", help="List wiki pages for a project.")
    lp.add_argument("--project", help="Project identifier.")
    lp.add_argument("--visible", action="store_true", help="Show browser window (for debugging).")

    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "write-wiki": cmd_write_wiki,
        "read-wiki": cmd_read_wiki,
        "list-wiki": cmd_list_wiki,
    }

    handler = dispatch.get(args.command)
    if not handler:
        parser.print_help()
        sys.exit(1)

    try:
        handler(args)
    except WikiError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
