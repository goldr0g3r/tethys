"""Profile selector — marine / space radio buttons.

The Tethys slave compiles in one of two profiles (``marine`` /
``space``); the master GUI surfaces the currently-detected profile so
operators see which feature constraints apply and so the calibration
editor can filter writable CHARACTERISTICs (space profile is
service-mode-only — see ADR-0001 and the space-profile-invariants
rule).

In PR-C the selector is a simple radio group emitting
:attr:`ProfileSelector.profile_changed`. The slave's actual profile is
read out of ``GET_VERSION`` / ``tethys_profile.h`` markers in a
follow-up wiring PR.

Cite: parent plan §3.3 (profile system)
Cite: ADR-0001 (XCP as development-time protocol; service-mode FSM)
Cite: ADR-0002 (profile-based build system)
Cite: marine-profile-invariants.mdc + space-profile-invariants.mdc
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from tethys_master.logging_setup import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class Profile(str, Enum):
    """Tethys profile identifier (parent §3.3)."""

    MARINE = "marine"
    SPACE = "space"


_PROFILE_LABELS: dict[Profile, str] = {
    Profile.MARINE: "&Marine (IACS UR E22 Rev.3, IEC 60945)",
    Profile.SPACE: "&Space (ECSS-E-ST-40C Rev.1, NPR 7150.2D)",
}

_PROFILE_DESCRIPTIONS: dict[Profile, str] = {
    Profile.MARINE: (
        "MARINE: dev-time XCP fully on by default; CAL/PAG read+write; "
        "DAQ at 1 kHz; SocketCAN + UDP transports; MISRA C:2023 mandatory + required."
    ),
    Profile.SPACE: (
        "SPACE: XCP quiescent at boot; CAL writable only after AES-128 "
        "service-mode unlock; ECC-wrapped CAL pages; UART/SxI + CCSDS COP-1; "
        "MISRA C:2023 mandatory + required + advisory."
    ),
}


class ProfileSelector(QWidget):
    """Radio-group selector for marine / space profile.

    Emits :attr:`profile_changed` with the new :class:`Profile` value
    whenever the operator changes the selection.
    """

    profile_changed = Signal(str)

    def __init__(self, initial: Profile = Profile.MARINE, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profile_selector")

        group_box = QGroupBox("Active profile")
        group_box.setObjectName("profile_group")

        self._buttons: dict[Profile, QRadioButton] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setObjectName("profile_button_group")
        self._button_group.setExclusive(True)

        group_layout = QVBoxLayout(group_box)
        for kind in Profile:
            btn = QRadioButton(_PROFILE_LABELS[kind])
            btn.setObjectName(f"profile_radio_{kind.value}")
            btn.setAccessibleName(f"Profile {kind.value}")
            self._buttons[kind] = btn
            self._button_group.addButton(btn)
            group_layout.addWidget(btn)
        self._buttons[initial].setChecked(True)
        self._profile = initial

        self._desc = QLabel(_PROFILE_DESCRIPTIONS[initial])
        self._desc.setObjectName("profile_description")
        self._desc.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(group_box)
        layout.addWidget(self._desc)
        layout.addStretch(1)

        for kind, btn in self._buttons.items():
            btn.toggled.connect(lambda checked, k=kind: self._on_toggled(k, checked))

    def selected_profile(self) -> Profile:
        return self._profile

    def set_profile(self, profile: Profile) -> None:
        if profile == self._profile:
            return
        self._buttons[profile].setChecked(True)

    def is_marine(self) -> bool:
        return self._profile == Profile.MARINE

    def is_space(self) -> bool:
        return self._profile == Profile.SPACE

    def _on_toggled(self, profile: Profile, checked: bool) -> None:
        if not checked:
            return
        if profile == self._profile:
            return
        self._profile = profile
        self._desc.setText(_PROFILE_DESCRIPTIONS[profile])
        logger.info("profile.changed", profile=profile.value)
        self.profile_changed.emit(profile.value)
