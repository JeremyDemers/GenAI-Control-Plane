from app.models.enums import RequestStatus


class InvalidTransitionError(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.DRAFT: {RequestStatus.SUBMITTED, RequestStatus.CANCELLED},
    RequestStatus.SUBMITTED: {
        RequestStatus.AWAITING_MANAGER_APPROVAL,
        RequestStatus.AWAITING_SECURITY_REVIEW,
        RequestStatus.AWAITING_CTO_APPROVAL,
        RequestStatus.REJECTED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.AWAITING_MANAGER_APPROVAL: {
        RequestStatus.SUBMITTED,
        RequestStatus.AWAITING_SECURITY_REVIEW,
        RequestStatus.AWAITING_CTO_APPROVAL,
        RequestStatus.APPROVED,
        RequestStatus.REJECTED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.AWAITING_SECURITY_REVIEW: {
        RequestStatus.SUBMITTED,
        RequestStatus.AWAITING_CTO_APPROVAL,
        RequestStatus.APPROVED,
        RequestStatus.REJECTED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.AWAITING_CTO_APPROVAL: {
        RequestStatus.SUBMITTED,
        RequestStatus.APPROVED,
        RequestStatus.REJECTED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.APPROVED: {RequestStatus.PROVISIONING, RequestStatus.CANCELLED},
    RequestStatus.PROVISIONING: {RequestStatus.ACTIVE, RequestStatus.PROVISIONING_FAILED},
    RequestStatus.PROVISIONING_FAILED: {RequestStatus.PROVISIONING, RequestStatus.CANCELLED},
    RequestStatus.ACTIVE: {
        RequestStatus.EXPIRING_SOON,
        RequestStatus.SUSPENDED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.EXPIRING_SOON: {
        RequestStatus.ACTIVE,
        RequestStatus.SUSPENDED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.SUSPENDED: {
        RequestStatus.ACTIVE,
        RequestStatus.EXPIRED,
        RequestStatus.ARCHIVING,
        RequestStatus.DEPROVISIONING_FAILED,
    },
    RequestStatus.EXPIRED: {RequestStatus.ARCHIVING, RequestStatus.DEPROVISIONING_FAILED},
    RequestStatus.DEPROVISIONING_FAILED: {RequestStatus.ARCHIVING, RequestStatus.SUSPENDED},
    RequestStatus.ARCHIVING: {RequestStatus.CLOSED},
    RequestStatus.CLOSED: set(),
    RequestStatus.REJECTED: set(),
    RequestStatus.CANCELLED: set(),
}


def transition(current: RequestStatus, desired: RequestStatus) -> RequestStatus:
    if desired not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(f"Cannot transition request from {current} to {desired}")
    return desired
