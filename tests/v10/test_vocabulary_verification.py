"""Vocabulary verification tests (m5 plan step 7, task T7).

The frozen m1/m3 decision-artifact vocabularies live in five Python
constants across four modules. This test file proves they are exactly the
values their normative DDL ``CHECK`` constraints allow (or, for
``evidence_items.kind``, the repository-enforced closed vocabulary the DDL
deliberately leaves open), that each is a non-empty duplicate-free frozen
``tuple[str, ...]``, that the hardcoded fixture constants in the references
CLI test file have not drifted from the repository, and that the
``choices=`` arguments on the product CLI parsers point at those exact
repository tuples (no parser-side drift).

DDL sources (parsed from the shipped migration SQL, never hardcoded):

- ``project_references.kind``, ``media_references.role``,
  ``reference_links.kind`` — ``astrid/packs/references/migrations/0001_initial.sql``
- ``media_relations.kind`` — ``astrid/core/migrations/sql/core/0001_initial.sql``
- ``evidence_items.kind`` — declared ``TEXT NOT NULL`` with **no** CHECK
  (the closed five-kind vocabulary is enforced by
  :class:`astrid.core.repositories.evidence.EvidenceRepository` before any
  write; see docs/astrid-v10-implementation-decisions.md section 8).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pytest

import astrid

from astrid.core.cli.domain_media import MEDIA_RELATION_KINDS
from astrid.core.repositories.evidence import EVIDENCE_KINDS
from astrid.packs.references.repository import (
    MEDIA_REFERENCE_ROLES,
    REFERENCE_KINDS,
    REFERENCE_LINK_KINDS,
)
from astrid.packs.shots.text_bindings import TEXT_BINDING_KINDS

_PACKAGE_ROOT = Path(astrid.__file__).resolve().parent

_REFERENCES_MIGRATION = (
    _PACKAGE_ROOT / "packs" / "references" / "migrations" / "0001_initial.sql"
)
_CORE_MIGRATION = (
    _PACKAGE_ROOT / "core" / "migrations" / "sql" / "core" / "0001_initial.sql"
)
_SHOTS_TEXT_MIGRATION = (
    _PACKAGE_ROOT / "packs" / "shots" / "migrations" / "0002_text_bindings.sql"
)

# The five frozen vocabularies under test, in the order the sense check
# enumerates them.
VOCABULARIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("REFERENCE_KINDS", REFERENCE_KINDS),
    ("MEDIA_REFERENCE_ROLES", MEDIA_REFERENCE_ROLES),
    ("REFERENCE_LINK_KINDS", REFERENCE_LINK_KINDS),
    ("MEDIA_RELATION_KINDS", MEDIA_RELATION_KINDS),
    ("EVIDENCE_KINDS", EVIDENCE_KINDS),
)


# ---------------------------------------------------------------------------
# DDL CHECK extraction (parse the shipped SQL, never hardcode the values)
# ---------------------------------------------------------------------------


def _table_body(sql_text: str, table: str) -> str | None:
    """Return the ``CREATE TABLE <table> (...)`` body, or ``None`` if absent."""
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?P<table>\w+)\s*\((?P<body>.*?)\)\s*;", re.DOTALL
    )
    for match in pattern.finditer(sql_text):
        if match.group("table") == table:
            return match.group("body")
    return None


def _ddl_check_in_list(
    sql_text: str, table: str, column: str
) -> tuple[str, ...] | None:
    """Extract the first ``<column> IN ('a','b',...)`` list for *table*.

    Returns the quoted string literals in DDL order, or ``None`` when the
    column has no ``IN`` constraint (the open-column case).
    """
    body = _table_body(sql_text, table)
    if body is None:
        return None
    in_list = re.compile(
        r"\b(?P<column>\w+)\s+IN\s*\((?P<items>[^)]*)\)"
    )
    for match in in_list.finditer(body):
        if match.group("column") == column:
            return tuple(re.findall(r"'([^']*)'", match.group("items")))
    return None


# ---------------------------------------------------------------------------
# DDL CHECK matching
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("vocabulary", "table", "column"),
    [
        (REFERENCE_KINDS, "project_references", "kind"),
        (MEDIA_REFERENCE_ROLES, "media_references", "role"),
        (REFERENCE_LINK_KINDS, "reference_links", "kind"),
    ],
)
def test_reference_vocabularies_match_ddl_check(
    vocabulary: tuple[str, ...], table: str, column: str
) -> None:
    """Every references-pack vocabulary matches its DDL CHECK, in DDL order."""
    sql_text = _REFERENCES_MIGRATION.read_text(encoding="utf-8")
    ddl = _ddl_check_in_list(sql_text, table, column)
    assert ddl is not None, (
        f"{table}.{column} has no IN (...) CHECK constraint in the DDL"
    )
    assert vocabulary == ddl
    assert vocabulary  # non-empty


def test_media_relation_kinds_match_ddl_check() -> None:
    """``MEDIA_RELATION_KINDS`` matches the ``media_relations.kind`` CHECK."""
    sql_text = _CORE_MIGRATION.read_text(encoding="utf-8")
    ddl = _ddl_check_in_list(sql_text, "media_relations", "kind")
    assert ddl is not None, "media_relations.kind has no IN (...) CHECK constraint"
    assert MEDIA_RELATION_KINDS == ddl
    assert MEDIA_RELATION_KINDS  # non-empty


def test_shot_text_binding_kinds_match_ddl_check() -> None:
    """The Shots text-binding kind vocabulary matches its migration."""
    sql_text = _SHOTS_TEXT_MIGRATION.read_text(encoding="utf-8")
    ddl = _ddl_check_in_list(sql_text, "shot_text_bindings", "kind")
    assert ddl == TEXT_BINDING_KINDS


def test_evidence_kinds_match_closed_vocabulary_and_ddl_has_no_check() -> None:
    """``EVIDENCE_KINDS`` is the closed five-kind vocabulary.

    ``evidence_items.kind`` is deliberately **open** in the DDL (``TEXT NOT
    NULL``, no CHECK) — the closed vocabulary is the repository-enforced
    gate before any write. This test asserts both facts: the DDL does not
    constrain the column, and the Python constant is the canonical frozen
    five-kind tuple.
    """
    sql_text = _CORE_MIGRATION.read_text(encoding="utf-8")
    assert (
        _ddl_check_in_list(sql_text, "evidence_items", "kind") is None
    ), "evidence_items.kind unexpectedly has an IN (...) CHECK constraint"
    assert EVIDENCE_KINDS == (
        "observation",
        "measurement",
        "validation",
        "decision",
        "error",
    )


# ---------------------------------------------------------------------------
# Frozen-tuple shape
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name,vocabulary", VOCABULARIES)
def test_vocabularies_are_frozen_tuples(
    name: str, vocabulary: tuple[str, ...]
) -> None:
    """Each vocabulary is a non-empty frozen tuple of non-empty strings."""
    assert isinstance(vocabulary, tuple), f"{name} is not a tuple"
    assert vocabulary, f"{name} is empty"
    assert len(vocabulary) == len(set(vocabulary)), (
        f"{name} has duplicate values: {vocabulary!r}"
    )
    for value in vocabulary:
        assert isinstance(value, str), f"{name} value {value!r} is not a str"
        assert value, f"{name} has an empty-string value"
        assert value == value.strip(), f"{name} value {value!r} is not trimmed"


# ---------------------------------------------------------------------------
# Fixture drift (hardcoded constants in the references CLI test file)
# ---------------------------------------------------------------------------


def test_reference_kinds_match_test_fixtures() -> None:
    """The hardcoded vocabularies in the references CLI test file match.

    ``tests/v10/test_domain_cli_media_references.py`` hardcodes the frozen
    vocabularies at module level to drive its parser assertions. If those
    copies drift from the repository constants, the test fixture is no
    longer exercising the real vocabulary — so this test pins them equal.
    """
    from tests.v10.test_domain_cli_media_references import (
        MEDIA_REFERENCE_ROLES as fixture_media_reference_roles,
    )
    from tests.v10.test_domain_cli_media_references import (
        MEDIA_RELATION_KINDS as fixture_media_relation_kinds,
    )
    from tests.v10.test_domain_cli_media_references import (
        REFERENCE_KINDS as fixture_reference_kinds,
    )
    from tests.v10.test_domain_cli_media_references import (
        REFERENCE_LINK_KINDS as fixture_reference_link_kinds,
    )

    assert fixture_reference_kinds == REFERENCE_KINDS
    assert fixture_media_reference_roles == MEDIA_REFERENCE_ROLES
    assert fixture_reference_link_kinds == REFERENCE_LINK_KINDS
    assert fixture_media_relation_kinds == MEDIA_RELATION_KINDS


# ---------------------------------------------------------------------------
# CLI choices= drift (parser choices point at the repository tuples)
# ---------------------------------------------------------------------------


class _DummyClient:
    """A stand-in client — the parser builders only need the object present."""


def _subparser(
    parser: argparse.ArgumentParser, command: str
) -> argparse.ArgumentParser:
    """Return the subparser registered for *command*."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[command]
    raise AssertionError(f"parser {parser.prog!r} has no subparsers")


def _choices(
    subparser: argparse.ArgumentParser, option: str
) -> tuple[str, ...]:
    """Return the ``choices`` tuple for the first action matching *option*."""
    for action in subparser._actions:
        if option in action.option_strings:
            assert action.choices is not None, f"{option} has no choices"
            return tuple(action.choices)
    raise AssertionError(f"{option!r} not found on {subparser.prog!r}")


def test_cli_choices_match_repository_vocabularies() -> None:
    """The references/media parser ``choices=`` args pin the repository tuples.

    Drift between a parser's ``choices=`` and the repository constant would
    let a CLI accept (or reject) a value the repository treats differently.
    This introspects the actual parsers, so any future copy-paste drift is
    caught here rather than at runtime.
    """
    from astrid.core.cli.domain_media import build_parser as media_build_parser
    from astrid.packs.references.cli import build_parser as refs_build_parser

    refs = refs_build_parser(_DummyClient())
    assert _choices(_subparser(refs, "create"), "--kind") == REFERENCE_KINDS
    assert (
        _choices(_subparser(refs, "associate"), "--role")
        == MEDIA_REFERENCE_ROLES
    )
    assert (
        _choices(_subparser(refs, "link"), "--kind") == REFERENCE_LINK_KINDS
    )

    media = media_build_parser(_DummyClient())
    assert (
        _choices(_subparser(media, "relate"), "--kind")
        == MEDIA_RELATION_KINDS
    )
