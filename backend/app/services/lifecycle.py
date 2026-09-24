from app.domain.status import ProposalStatus, TaskStatus


class InvalidTransition(ValueError):
    pass


_TASK_TRANSITIONS = {
    TaskStatus.DRAFT: {TaskStatus.CLARIFYING},
    TaskStatus.CLARIFYING: {TaskStatus.CARD_READY},
    TaskStatus.CARD_READY: {TaskStatus.CONFIRMED},
}


def transition_task(current: TaskStatus | str, target: TaskStatus) -> TaskStatus:
    try:
        current = TaskStatus(current)
    except ValueError as exc:
        raise InvalidTransition("Unknown task status") from exc

    # Re-answering a card and re-confirming an already confirmed task preserve
    # existing idempotent endpoint behavior.
    if current == target and current in {TaskStatus.CARD_READY, TaskStatus.CONFIRMED}:
        return current
    if target not in _TASK_TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"Cannot transition task from {current.value} to {target.value}")
    return target


def transition_proposal(
    current: ProposalStatus | str, target: ProposalStatus
) -> ProposalStatus:
    try:
        current = ProposalStatus(current)
    except ValueError as exc:
        raise InvalidTransition("Unknown proposal status") from exc

    if current == ProposalStatus.PENDING and target == ProposalStatus.PENDING:
        return current
    if current == ProposalStatus.PENDING and target in {
        ProposalStatus.ACCEPTED,
        ProposalStatus.REJECTED,
    }:
        return target
    raise InvalidTransition(f"Cannot transition proposal from {current.value} to {target.value}")
