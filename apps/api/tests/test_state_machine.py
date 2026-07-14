import pytest

from app.models.enums import RequestStatus
from app.services.state_machine import InvalidTransitionError, transition


def test_allows_explicit_happy_path_transitions() -> None:
    status = RequestStatus.DRAFT
    for desired in [
        RequestStatus.SUBMITTED,
        RequestStatus.AWAITING_MANAGER_APPROVAL,
        RequestStatus.AWAITING_CTO_APPROVAL,
        RequestStatus.APPROVED,
        RequestStatus.PROVISIONING,
        RequestStatus.ACTIVE,
        RequestStatus.EXPIRING_SOON,
        RequestStatus.EXPIRED,
        RequestStatus.ARCHIVING,
        RequestStatus.CLOSED,
    ]:
        status = transition(status, desired)
    assert status == RequestStatus.CLOSED


def test_rejects_arbitrary_state_changes() -> None:
    with pytest.raises(InvalidTransitionError):
        transition(RequestStatus.DRAFT, RequestStatus.ACTIVE)
