#!/usr/bin/env python3

import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from urllib.parse import quote_plus
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

import click
import requests
import dateparser

# Constants
DEFAULT_PER_PAGE = 100  # Maximum allowed per_page value for GitHub API
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_SORT = "indexed"
DEFAULT_ORDER = "desc"
CODE_SEARCH_RATE_LIMIT = 10  # Fixed limit for code search API
MAX_SEARCH_RESULTS = 1000  # GitHub API maximum search results limit

# Configure logging (default level will be set based on command line argument)
logging.basicConfig(
    format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def check_and_wait_for_rate_limit(response: requests.Response) -> None:
    """Check rate limit headers and wait if necessary.

    Args:
        response: The HTTP response object containing rate limit headers
    """
    remaining = response.headers.get("x-ratelimit-remaining")
    reset_time = response.headers.get("x-ratelimit-reset")
    used = response.headers.get("x-ratelimit-used")

    if remaining and used:
        logging.info(
            f"Rate limit status: {used}/{CODE_SEARCH_RATE_LIMIT} used, {remaining} remaining"
        )

    # If no requests remaining, wait until reset
    if remaining == "0" and reset_time:
        try:
            reset_timestamp = int(reset_time)
            current_time = int(time.time())
            wait_time = reset_timestamp - current_time + 1  # +1 for safety margin

            if wait_time > 0:
                logging.info(
                    f"Rate limit exhausted. Waiting {wait_time} seconds until reset..."
                )
                time.sleep(wait_time)
            else:
                logging.info("Rate limit reset time already passed")
        except (ValueError, TypeError):
            logging.error(f"Invalid rate limit reset time: {reset_time}")
            sys.exit(1)


def generate_atom_feed(
    items: List[Dict[str, Any]],
    query: str,
    output_file: Optional[Path],
    updated_date: Optional[str] = None,
) -> None:
    """Generate ATOM feed from search results.

    Args:
        items: List of GitHub API search result items
        query: The search query string
        output_file: Optional file path to write the ATOM feed to. If None, output to stdout
        updated_date: Optional updated date string (will be parsed by dateparser)

    Raises:
        SystemExit: If XML generation or file writing fails
    """
    # Create root element
    root_elem = Element("feed")
    root_elem.set("xmlns", "http://www.w3.org/2005/Atom")

    # Add feed metadata
    title_elem = SubElement(root_elem, "title")
    title_elem.text = f"GitHub Code Search Results for: {query}"

    link_elem = SubElement(root_elem, "link")
    link_elem.set("href", f"https://github.com/search?q={quote_plus(query)}&type=code")
    link_elem.set("rel", "alternate")

    # Parse updated date or use current time
    if updated_date:
        parsed_date = dateparser.parse(updated_date)
        if parsed_date:
            # Ensure timezone-aware datetime
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            feed_updated_time = parsed_date.isoformat()
        else:
            logging.warning(
                f"Could not parse updated date: {updated_date}, using current time"
            )
            feed_updated_time = datetime.now(timezone.utc).isoformat()
    else:
        feed_updated_time = datetime.now(timezone.utc).isoformat()

    updated_elem = SubElement(root_elem, "updated")
    updated_elem.text = feed_updated_time

    id_elem = SubElement(root_elem, "id")
    id_elem.text = f"urn:github-search:{quote_plus(query)}"

    # Add entries for each search result
    for item in items:
        entry_elem = SubElement(root_elem, "entry")

        # Entry title
        entry_title_elem = SubElement(entry_elem, "title")
        entry_title_elem.text = f"{item['repository']['full_name']}: {item['name']}"

        # Entry link
        entry_link_elem = SubElement(entry_elem, "link")
        entry_link_elem.set("href", item["html_url"])

        # Entry ID (using repository + path + sha for uniqueness)
        entry_id_elem = SubElement(entry_elem, "id")
        entry_id_elem.text = (
            f"urn:github:{item['repository']['full_name']}:{item['path']}:{item['sha']}"
        )

        # Entry updated - use same time as feed root
        entry_updated_elem = SubElement(entry_elem, "updated")
        entry_updated_elem.text = feed_updated_time

        # Entry content/summary
        entry_summary_elem = SubElement(entry_elem, "summary")
        entry_summary_elem.text = f"File: {item['path']}\nRepository: {item['repository']['full_name']}\nSHA: {item['sha']}"

        # Additional metadata as categories
        category_repo_elem = SubElement(entry_elem, "category")
        category_repo_elem.set("term", "repository")
        category_repo_elem.set("label", item["repository"]["full_name"])

        category_path_elem = SubElement(entry_elem, "category")
        category_path_elem.set("term", "path")
        category_path_elem.set("label", item["path"])

    # Convert to pretty-printed XML
    try:
        rough_string = tostring(root_elem, "unicode")
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent="  ")

        # Remove extra blank lines
        pretty_xml = "\n".join(
            [line for line in pretty_xml.split("\n") if line.strip()]
        )
    except Exception as e:
        logging.error(f"Error generating XML: {e}")
        sys.exit(1)

    # Output ATOM feed
    if output_file:
        # Write to file
        try:
            output_file.write_text(pretty_xml, encoding="utf-8")
            logging.info(f"ATOM feed written to: {output_file}")
        except IOError as e:
            logging.error(f"Error writing to file {output_file}: {e}")
            sys.exit(1)
    else:
        # Write to stdout
        click.echo(pretty_xml)


@click.command()
@click.option("--query", "-q", required=True, help="Search query")
@click.option(
    "--token",
    "-t",
    type=str,
    envvar="GHSEARCH_GITHUB_TOKEN",
    required=True,
    help="GitHub API token (can also be set via GITHUB_TOKEN environment variable)",
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default=DEFAULT_LOG_LEVEL,
    help="Set logging level (default: INFO)",
)
@click.option(
    "--until-url",
    "-u",
    type=str,
    required=False,
    help="Stop fetching when this URL is encountered (URL itself is excluded from results)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    required=False,
    help="Output file path for ATOM feed (default: stdout)",
)
@click.option(
    "--updated-date",
    type=str,
    required=False,
    help="Updated date for ATOM feed (any date format, default: current time)",
)
def search_github_code(
    token: str,
    query: str,
    log_level: str,
    until_url: Optional[str],
    output: Optional[Path],
    updated_date: Optional[str],
) -> None:
    """Search GitHub code using the GitHub API with pagination support.

    Args:
        token: GitHub API authentication token
        query: Search query string
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        until_url: Optional URL to stop fetching at (exclusive)
        output: Optional file path to write ATOM feed to. If None, output to stdout
        updated_date: Optional updated date for ATOM feed (ISO format)

    Raises:
        SystemExit: If API request fails or other unexpected errors occur
    """

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))

    base_url: str = "https://api.github.com/search/code"
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Fixed values for sort and order
    sort: str = DEFAULT_SORT
    order: str = DEFAULT_ORDER

    page: int = 1
    per_page: int = DEFAULT_PER_PAGE
    total_count: int = 0
    all_items: List[Dict[str, Any]] = []

    logging.info(f"Searching for: {query}")
    logging.info(f"Sort: {sort}, Order: {order}")

    while True:
        # requests.getのparams=paramsを使うと、queryが%エンコードされ、APIの結果が意図しない結果となるため
        url: str = f"{base_url}?q={query}&sort={sort}&order={order}&page={page}&per_page={per_page}"

        try:
            response: requests.Response = requests.get(url, headers=headers)

            # Check for rate limit before raising for status
            if response.status_code == 403:
                remaining = response.headers.get("x-ratelimit-remaining")
                if remaining == "0":
                    # Check if we've already reached the limit before waiting
                    if page * per_page >= MAX_SEARCH_RESULTS:
                        logging.warning(
                            f"Reached GitHub API search limit of {MAX_SEARCH_RESULTS} results"
                        )
                        break
                    check_and_wait_for_rate_limit(response)
                    continue  # Retry the request after waiting

            response.raise_for_status()

            data: Dict[str, Any] = response.json()

            if page == 1:
                total_count = data.get("total_count", 0)
                logging.info(f"Total results: {total_count}")

            items: List[Dict[str, Any]] = data.get("items", [])

            if not items:
                break

            # Check if we should stop at a specific URL and filter items
            filtered_items: List[Dict[str, Any]] = []
            should_stop: bool = False

            for item in items:
                item_url = item.get("url", "")
                if until_url and item_url == until_url:
                    should_stop = True
                    break
                filtered_items.append(item)

            # Add filtered items to all_items for ATOM feed generation
            all_items.extend(filtered_items)

            for item in filtered_items:
                logging.debug(f"Repository: {item['repository']['full_name']}")
                logging.debug(f"File: {item['name']}")
                logging.debug(f"Path: {item['path']}")
                logging.debug(f"SHA: {item['sha']}")
                logging.debug(f"URL: {item['url']}")
                logging.debug(f"HTML URL: {item['html_url']}")
                logging.debug(f"Repository HTML URL: {item['repository']['html_url']}")
                logging.debug(f"Repository ID: {item['repository']['id']}")
                logging.debug(f"Repository Name: {item['repository']['name']}")
                logging.debug(
                    f"Repository Full Name: {item['repository']['full_name']}"
                )
                logging.debug("-" * 30)

            # Stop if we found the target URL
            if should_stop:
                logging.info(f"Stopped at target URL: {until_url}")
                break

            # Check if there are more pages
            will_continue = not (
                len(items) < per_page
                or page * per_page >= total_count
                or page * per_page >= MAX_SEARCH_RESULTS
            )

            if not will_continue:
                if page * per_page >= MAX_SEARCH_RESULTS:
                    logging.warning(
                        f"Reached GitHub API search limit of {MAX_SEARCH_RESULTS} results"
                    )
                break

            # Only check rate limit if we will continue to next page
            check_and_wait_for_rate_limit(response)

            page += 1

        except requests.exceptions.RequestException as e:
            if hasattr(e, "response") and e.response is not None:
                if e.response.status_code == 422:
                    logging.warning(
                        f"Reached search result limit at page {page}. GitHub API limits search to {MAX_SEARCH_RESULTS} results."
                    )
                    break  # Exit the loop gracefully instead of failing
                else:
                    logging.error(f"Error making request: {e}")
                    sys.exit(1)
            else:
                logging.error(f"Error making request: {e}")
                sys.exit(1)
        except KeyError as e:
            logging.error(f"Unexpected response format: {e}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"Unexpected error occurred: {e}")
            sys.exit(1)

    logging.info(f"Finished searching. Total pages processed: {page}")

    # Generate ATOM feed
    generate_atom_feed(all_items, query, output, updated_date)


if __name__ == "__main__":
    search_github_code()
