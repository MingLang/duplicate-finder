import send2trash


def delete_files_to_trash(paths: list) -> tuple:
    """
    Move files to the Recycle Bin.
    Returns (succeeded: list[str], failed: list[tuple[str, str]])
    """
    succeeded = []
    failed = []
    for path in paths:
        try:
            send2trash.send2trash(path)
            succeeded.append(path)
        except Exception as e:
            failed.append((path, str(e)))
    return succeeded, failed
