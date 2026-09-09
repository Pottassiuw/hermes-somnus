from enum import Enum

class ExecutionStatus(str, Enum):
    PASS = PASS
    FAIL = FAIL
    BLOCKED = BLOCKED
    SKIPPED = SKIPPED

class RiskLevel(str, Enum):
    LOW = LOW
    MEDIUM = MEDIUM
    HIGH = HIGH
    CRITICAL = CRITICAL
