import hashlib

CHUNK_SIZE = 65536  # 64 KB


def hash_partial(path: str, algorithm: str = "sha256") -> str:
    """Hash only the first CHUNK_SIZE bytes of a file."""
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as f:
            chunk = f.read(CHUNK_SIZE)
            if chunk:
                h.update(chunk)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()


def hash_full(path: str, algorithm: str = "sha256") -> str:
    """Hash the entire file content."""
    h = hashlib.new(algorithm)
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                h.update(chunk)
    except (OSError, PermissionError):
        return ""
    return h.hexdigest()
