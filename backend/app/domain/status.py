from enum import Enum


class TaskStatus(str, Enum):
    DRAFT = "draft"
    CLARIFYING = "clarifying"
    CARD_READY = "card_ready"
    CONFIRMED = "confirmed"


class TaskPublicationStatus(str, Enum):
    UNPUBLISHED = "unpublished"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
