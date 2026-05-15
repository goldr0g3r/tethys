"""ProfileSelector tests — radio toggling + signal emission."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

pytest.importorskip("PySide6", reason="PySide6 not installed; run `uv sync --all-extras`.")
pytest.importorskip("pytestqt", reason="pytest-qt not installed; run `uv sync --all-extras`.")

from tethys_master.gui.profile_selector import Profile, ProfileSelector  # noqa: E402

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

pytestmark = pytest.mark.gui


@pytest.fixture
def selector(qtbot: QtBot) -> ProfileSelector:
    s = ProfileSelector()
    qtbot.addWidget(s)
    s.show()
    qtbot.waitExposed(s)
    return s


def test_default_profile_is_marine(selector: ProfileSelector) -> None:
    assert selector.selected_profile() == Profile.MARINE
    assert selector.is_marine()
    assert not selector.is_space()


def test_initial_value_can_be_space(qtbot: QtBot) -> None:
    s = ProfileSelector(initial=Profile.SPACE)
    qtbot.addWidget(s)
    s.show()
    qtbot.waitExposed(s)
    assert s.selected_profile() == Profile.SPACE
    assert s.is_space()


def test_clicking_space_emits_profile_changed(
    qtbot: QtBot,
    selector: ProfileSelector,
) -> None:
    with qtbot.waitSignal(selector.profile_changed, timeout=1000) as blocker:
        selector._buttons[Profile.SPACE].setChecked(True)
    assert blocker.args == [Profile.SPACE.value]
    assert selector.is_space()


def test_clicking_same_profile_does_not_re_emit(
    qtbot: QtBot,
    selector: ProfileSelector,
) -> None:
    # Already marine — toggling marine on again should not re-emit.
    with qtbot.assertNotEmitted(selector.profile_changed):
        selector._buttons[Profile.MARINE].setChecked(True)


def test_set_profile_changes_selection(qtbot: QtBot, selector: ProfileSelector) -> None:
    with qtbot.waitSignal(selector.profile_changed, timeout=1000):
        selector.set_profile(Profile.SPACE)
    assert selector.selected_profile() == Profile.SPACE


def test_description_label_swaps_with_profile(selector: ProfileSelector) -> None:
    selector._buttons[Profile.SPACE].setChecked(True)
    desc = selector._desc.text()
    assert "ECC" in desc or "AES-128" in desc or "service-mode" in desc


def test_radio_buttons_carry_object_names(selector: ProfileSelector) -> None:
    assert selector._buttons[Profile.MARINE].objectName() == "profile_radio_marine"
    assert selector._buttons[Profile.SPACE].objectName() == "profile_radio_space"
