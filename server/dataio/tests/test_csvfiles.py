# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dataio.csvfiles import (
    CsvError,
    format_duration,
    parse_bool,
    parse_duration,
    read_table,
    write_csv,
)

ALIASES = {"bib": ("bib", "bibnumber"), "name": ("name", "firstname")}


class TestReadTable:
    def test_matches_loose_header_spellings(self) -> None:
        table = read_table(b"Bib Number,First_Name,Shoe size\n7,Ada,5\n", ALIASES)
        assert table.columns == {"bib": "Bib Number", "name": "First_Name"}
        assert table.ignored == ["Shoe size"]
        assert table.rows == [(2, {"bib": "7", "name": "Ada"})]

    def test_excel_byte_order_mark_and_semicolons(self) -> None:
        table = read_table("﻿bib;name\r\n7;Zoë\r\n".encode(), ALIASES)
        assert table.rows == [(2, {"bib": "7", "name": "Zoë"})]

    def test_windows_1252(self) -> None:
        table = read_table("bib,name\n7,Zoë\n".encode("cp1252"), ALIASES)
        assert table.rows[0][1]["name"] == "Zoë"

    def test_blank_rows_skipped_and_line_numbers_kept(self) -> None:
        table = read_table(b"bib,name\n\n7,Ada\n,\n8,Ben\n", ALIASES)
        assert [line for line, _ in table.rows] == [3, 5]

    def test_short_rows_padded(self) -> None:
        assert read_table(b"bib,name\n7\n", ALIASES).rows[0][1] == {"bib": "7", "name": ""}

    def test_known_unused_columns_not_reported(self) -> None:
        table = read_table(b"bib,TeamName\n7,A\n", ALIASES, known_unused=("teamname",))
        assert table.ignored == []

    def test_two_columns_meaning_the_same(self) -> None:
        with pytest.raises(CsvError, match="mean the same"):
            read_table(b"name,firstname\nA,B\n", ALIASES)

    def test_empty(self) -> None:
        with pytest.raises(CsvError, match="empty"):
            read_table(b"  \n", ALIASES)


class TestCsvInjection:
    def test_formulas_escaped_on_export_and_restored_on_import(self) -> None:
        text = write_csv(["bib", "name"], [["7", '=HYPERLINK("x")'], ["8", "-Ada"]])
        assert "'=HYPERLINK" in text
        rows = read_table(text.encode(), ALIASES).rows
        assert [r["name"] for _, r in rows] == ['=HYPERLINK("x")', "-Ada"]

    def test_numbers_untouched(self) -> None:
        assert write_csv(["n"], [[-1]]) == "n\r\n-1\r\n"


class TestDurations:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("00:25:36", timedelta(minutes=25, seconds=36)),
            ("1:02:03.4", timedelta(hours=1, minutes=2, seconds=3.4)),
            ("42:15,25", timedelta(minutes=42, seconds=15.25)),
            ("45.6", timedelta(seconds=45.6)),
            ("26:00:00", timedelta(hours=26)),
        ],
    )
    def test_parse(self, text: str, expected: timedelta) -> None:
        assert parse_duration(text) == expected

    @pytest.mark.parametrize("text", ["", "abc", "1:60:00", "1:00:61", "-5:00"])
    def test_rejects(self, text: str) -> None:
        with pytest.raises(ValueError):
            parse_duration(text)

    def test_format_truncates(self) -> None:
        t = timedelta(hours=1, minutes=2, seconds=3.979)
        assert format_duration(t) == "1:02:03"
        assert format_duration(t, decimals=1) == "1:02:03.9"
        assert format_duration(t, decimals=2) == "1:02:03.97"
        assert (
            format_duration(timedelta(minutes=25, seconds=36), two_digit_hours=True) == "00:25:36"
        )
        assert format_duration(None) == ""

    @given(st.integers(min_value=0, max_value=48 * 3600 * 1000))
    def test_round_trip_to_milliseconds(self, ms: int) -> None:
        t = timedelta(milliseconds=ms)
        assert parse_duration(format_duration(t, decimals=3)) == t


def test_parse_bool() -> None:
    assert [parse_bool(v) for v in ("yes", "Y", "1", "", "no", "False")] == [
        True,
        True,
        True,
        False,
        False,
        False,
    ]
    with pytest.raises(ValueError):
        parse_bool("maybe")
