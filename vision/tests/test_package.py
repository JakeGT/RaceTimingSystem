# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import racevision


def test_package_imports() -> None:
    assert racevision.__version__
