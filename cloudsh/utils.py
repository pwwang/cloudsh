__version__ = "0.3.1"

PACKAGE = "cloudsh"
MULTIPLIERS = {
    "b": 512,
    "kb": 1000,
    "k": 1024,
    "kib": 1024,
    "mb": 1000 * 1000,
    "m": 1024 * 1024,
    "mib": 1024 * 1024,
    "gb": 1000 * 1000 * 1000,
    "g": 1024 * 1024 * 1024,
    "gib": 1024 * 1024 * 1024,
    "tb": 1000 * 1000 * 1000 * 1000,
    "t": 1024 * 1024 * 1024 * 1024,
    "tib": 1024 * 1024 * 1024 * 1024,
    "pb": 1000 * 1000 * 1000 * 1000 * 1000,
    "p": 1024 * 1024 * 1024 * 1024 * 1024,
    "pib": 1024 * 1024 * 1024 * 1024 * 1024,
    # ... and so on for E, Z, Y, R, Q
}


def parse_number(value: str) -> int:
    """Parse a number with optional suffix.

    Args:
        value: String value with optional suffix

    Returns:
        int: The parsed number

    Examples:
        >>> parse_number("1234")
        1234
        >>> parse_number("1K")
        1024
        >>> parse_number("-1K")
        -1024
        >>> parse_number("1kB")
        1000
    """
    if not value:  # pragma: no cover
        raise ValueError("Empty value")

    value = str(value).strip()
    negative = value.startswith("-")
    if negative:
        value = value[1:]

    # Find where the number ends and suffix begins
    for i, char in enumerate(value):
        if not (char.isdigit() or char == "."):
            number = value[:i]
            suffix = value[i:].lower()
            break
    else:
        number = value
        suffix = ""

    if not number:  # pragma: no cover
        raise ValueError(f"Invalid number format: {value}")

    # Convert number part
    base = float(number)

    # Apply multiplier if suffix exists
    if suffix:
        if suffix not in MULTIPLIERS:
            raise ValueError(f"Unknown multiplier suffix: {suffix}")
        base *= MULTIPLIERS[suffix]

    result = int(base)
    return -result if negative else result
