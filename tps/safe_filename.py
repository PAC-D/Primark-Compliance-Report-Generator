ILLEGAL_FILENAME_CHARS = '<>:"/\\|?*'


def safe_filename(name: str) -> str:
    """Sanitize a name for use in a filename.

    Preserves letters, digits, spaces, hyphens, underscores, dots,
    ampersands, parentheses, commas, apostrophes and other punctuation
    that are valid in filenames on all major operating systems.

    Replaces only characters that are illegal in Windows filenames
    (< > : " / \\ | ? *) with underscores.
    """
    return "".join(c if c not in ILLEGAL_FILENAME_CHARS else "_" for c in str(name))
