import argparse
import logging
import socket
from enum import Enum
from typing import TYPE_CHECKING

from youtube_whisperer.config import Settings
from youtube_whisperer.runtime import Runtime

if TYPE_CHECKING:
    from youtube_whisperer.workers.azure_worker import AzureWorker
    from youtube_whisperer.workers.whisper_worker import WhisperWorker
    from youtube_whisperer.workers.youtube_worker import YouTubeWorker


class WorkerRole(str, Enum):
    YOUTUBE = 'youtube'
    WHISPER = 'whisper'
    AZURE = 'azure'

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """Return the CLI-compatible worker role names.

        Returns:
            A tuple containing each supported worker role value in declaration
            order.
        """
        return tuple(role.value for role in cls)


def resolve_worker_slot(slot: str | None, role_name: str, *, settings: Settings | None = None) -> str:
    """
    Resolve the slot name a worker should use for active-queue ownership.

    Args:
        slot: Explicit slot override, if provided.
        role_name: Worker role name used when constructing the fallback slot name.
        settings: Supplied snapshot, or invocation-time environment defaults.

    Returns:
        The resolved slot name from the explicit value, environment, or role-based default.
    """
    if slot:
        return slot
    settings = settings if settings is not None else Settings()
    slot_id = settings.worker_slot_id
    if slot_id is not None:
        return f'{role_name}-{slot_id}'
    return socket.gethostname()


def _load_worker_class(role: WorkerRole) -> "type[YouTubeWorker | WhisperWorker | AzureWorker]":
    """Import only the worker class selected by a validated role.

    Args:
        role: Validated role whose engine may be imported.

    Returns:
        The matching concrete worker class.

    Raises:
        ValueError: If a role outside this dispatch mapping is supplied.
    """
    match role:
        case WorkerRole.YOUTUBE:
            from youtube_whisperer.workers.youtube_worker import YouTubeWorker

            return YouTubeWorker
        case WorkerRole.WHISPER:
            from youtube_whisperer.workers.whisper_worker import WhisperWorker

            return WhisperWorker
        case WorkerRole.AZURE:
            from youtube_whisperer.workers.azure_worker import AzureWorker

            return AzureWorker
    raise ValueError(f'Unsupported worker role: {role}')


def __getattr__(name: str) -> "type[YouTubeWorker | WhisperWorker | AzureWorker]":
    """Forward legacy ``__main__`` worker-class imports lazily to their modules.

    Args:
        name: Previously exposed worker class name.

    Returns:
        The requested concrete worker class.

    Raises:
        AttributeError: If the name is not a supported compatibility export.
    """
    role_by_name = {
        'YouTubeWorker': WorkerRole.YOUTUBE,
        'WhisperWorker': WorkerRole.WHISPER,
        'AzureWorker': WorkerRole.AZURE,
    }
    try:
        return _load_worker_class(role_by_name[name])
    except KeyError as exc:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}') from exc


def process_queue(role: WorkerRole | str = WorkerRole.WHISPER, slot: str | None = None, poll_interval_seconds: int = 5, *, settings: Settings | None = None) -> None:
    """Dispatch queue processing to the selected worker implementation.

    This entrypoint normalizes the requested worker role and forwards execution
    to the corresponding YouTube, Whisper, or Azure queue processor. Slot
    routing supplies each worker's consumer identity.

    Args:
        role: Worker role to run. May be provided as a `WorkerRole` value or a
            matching string.
        slot: Optional consumer identifier for the selected worker.
            When omitted, the slot is resolved from environment-aware defaults.
        settings: Supplied snapshot shared by identity and worker execution.
        poll_interval_seconds: Number of seconds to wait between Redis polling
            attempts while the selected queue is empty.

    Returns:
        None. The selected worker loop runs until the process is stopped.

    Raises:
        ValueError: If `role` is not one of the supported worker roles.
    """
    try:
        role = WorkerRole(role)
    except ValueError as exc:
        raise ValueError(f'Unsupported worker role: {role}') from exc
    with Runtime(settings) as runtime:
        resolved_slot = resolve_worker_slot(slot, role.value, settings=runtime.settings)
        worker_class = _load_worker_class(role)
        worker_class(resolved_slot, runtime=runtime).process_queue(poll_interval_seconds=poll_interval_seconds)


def main() -> None:
    """Parse CLI arguments and start the requested queue worker.

    The command-line interface accepts the worker role plus optional slot and
    polling configuration, then delegates to `process_queue` with the parsed
    values.

    Returns:
        None. The selected worker loop runs until the process is stopped.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()
    parser = argparse.ArgumentParser()
    parser.add_argument('role', nargs='?', choices=WorkerRole.values(), default=settings.worker_role)
    parser.add_argument('--slot', default=None, help="Active-slot identifier for whisper/Azure workers. Defaults to WORKER_SLOT_ID, then machine hostname.")
    parser.add_argument('--poll-interval-seconds', type=int, default=5)
    args = parser.parse_args()
    process_queue(role=args.role, slot=args.slot, poll_interval_seconds=args.poll_interval_seconds, settings=settings)


if __name__ == "__main__":
    main()
