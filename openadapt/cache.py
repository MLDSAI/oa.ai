"""openadapt.cache module.

This module provides a caching decorator for functions and a command line interface for
managing the cache.

Python Example Usage:
    from openadapt.cache import cache

    @cache()
    def my_function():
        # Function body
        pass

Command Line Example Usage:
    # To clear the cache but keep data from the last 14 days and perform a dry run:
    python -m openadapt.cache clear --keep_days 14 --dry_run True
"""

from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable
import os
import time

from joblib import Memory
import fire

from openadapt.config import config
from openadapt.custom_logger import logger


def default(val: Any, default: Any) -> Any:
    """Set a default value if the given value is None.

    Args:
        val: The value to check.
        default: The default value to set.

    Returns:
        The value or the default value.
    """
    return val if val is not None else default


def cache(
    dir_path: str | None = None,
    enabled: bool | None = None,
    verbosity: int | None = None,
    force_refresh: bool = False,
    **cache_kwargs: str | int | bool,
) -> Callable[[Callable], Callable]:
    """Cache decorator for functions.

    Args:
        dir_path (str | None): The path to the cache directory.
        enabled (bool | None): Whether caching is enabled.
        verbosity (int | None): The verbosity level of the cache.
        force_refresh (bool): If True, the cache will be refreshed.
        **cache_kwargs: Additional keyword arguments to pass to the cache.

    Returns:
        The decorator function.
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache_dir_path = default(dir_path, config.CACHE_DIR_PATH)
            cache_enabled = default(enabled, config.CACHE_ENABLED)
            cache_verbosity = default(verbosity, config.CACHE_VERBOSITY)
            logger.debug(f"{cache_enabled=}")
            if cache_enabled:
                memory = Memory(cache_dir_path, verbose=cache_verbosity)
                nonlocal fn
                fn = memory.cache(fn, **cache_kwargs)
                if force_refresh:
                    logger.debug(f"{force_refresh=}")
                    cache_hit = False
                else:
                    cache_hit = fn.check_call_in_cache(*args, **kwargs)
                logger.debug(f"{fn=} {cache_hit=}")
            start_time = time.time()
            logger.debug(f"{fn=} {start_time=}")
            rval = fn(*args, **kwargs)
            duration = time.time() - start_time
            logger.debug(f"{fn=} {duration=}")

            # workaround for `AttributeError: _min_frame` raised when show()ing an Image
            try:
                from PIL import Image
            except ImportError:
                pass
            else:
                if isinstance(rval, Image.Image):
                    if not hasattr(rval, "_min_frame"):
                        logger.debug(
                            "Image object missing '_min_frame'; refreshing image."
                        )
                        fresh_image = Image.new(rval.mode, rval.size)
                        fresh_image.paste(rval)
                        rval = fresh_image

            return rval

        return wrapper

    return decorator


def clear(keep_days: int = 0, dry_run: bool = False) -> None:
    """Clears the cache, optionally keeping data for a specified number of days.

    With an option for a dry run.

    Args:
        keep_days (int): The number of days of cached data to keep.
        dry_run (bool): If True, perform a dry run without deleting files.
    """
    logger.info(
        f"Attempting to clear cache with {'dry run' if dry_run else 'actual deletion'},"
        " keeping last {keep_days} days."
    )
    cache_dir_path = Path(config.CACHE_DIR_PATH) / "joblib"
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    total_cleared = 0

    for path in cache_dir_path.rglob("*"):
        if path.is_file() and os.path.getmtime(path) < cutoff_date.timestamp():
            file_size = path.stat().st_size
            if not dry_run:
                os.remove(path)
                logger.debug(f"Removed file: {path}")
            else:
                logger.debug(f"Would remove file: {path}")
            total_cleared += file_size
        # Check if directory is empty after removing files
        elif path.is_dir() and not any(path.iterdir()):
            if not dry_run:
                os.rmdir(path)
                logger.debug(f"Removed empty directory: {path}")
            else:
                logger.debug(f"Would remove empty directory: {path}")

    if dry_run:
        logger.info(
            "Dry run complete. Would have cleared "
            "{total_cleared / (1024 * 1024):.2f} MB."
        )
    else:
        logger.info(
            f"Cache clearing completed. Cleared {total_cleared / (1024 * 1024):.2f} MB."
        )


if __name__ == "__main__":
    fire.Fire({"clear": clear})
