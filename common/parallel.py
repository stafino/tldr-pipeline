"""Thread-pool fan-out helper.

Several modules share the same shape: submit `fn` over an iterable,
swallow exceptions (with a warning), drop `None` results, collect the
survivors into a list. `parallel_map` absorbs that pattern.

Order is NOT preserved - results come back in completion order (the
caller should sort or re-index by URL if it needs ordering).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def parallel_map(
    fn: Callable[[T], Optional[R]],
    items: Iterable[T],
    *,
    concurrency: int,
    log: Optional[logging.Logger] = None,
    error_msg_fn: Optional[Callable[[T, Exception], str]] = None,
) -> list[R]:
    """Run `fn` over `items` on a thread pool, returning non-None results.

    Exceptions from `fn` are caught and logged (via `log.warning` using
    `error_msg_fn(item, exc)` when both are provided, otherwise a generic
    message); the corresponding item is dropped. `None` results are also
    dropped. Order is not preserved.
    """
    items_list = list(items)
    out: list[R] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(fn, item): item for item in items_list}
        for fut in as_completed(futures):
            item = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                if log is not None:
                    if error_msg_fn is not None:
                        log.warning("%s", error_msg_fn(item, e))
                    else:
                        log.warning("parallel_map worker error: %r", e)
                continue
            if r is None:
                continue
            out.append(r)
    return out
