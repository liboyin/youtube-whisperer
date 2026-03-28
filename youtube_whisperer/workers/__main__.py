import argparse
from enum import Enum
import os

from youtube_whisperer.workers.azure_worker import AzureWorker
from youtube_whisperer.workers.common import resolve_worker_slot
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


def process_queue(role: WorkerRole | str = WorkerRole.WHISPER, slot: str | None = None, poll_interval_seconds: int = 5) -> None:
    """Dispatch queue processing to the selected worker implementation.

    This entrypoint normalizes the requested worker role and forwards execution
    to the corresponding YouTube, Whisper, or Azure queue processor. Slot
    routing is only applied to workers that consume slot-specific active
    queues.

    Args:
        role: Worker role to run. May be provided as a `WorkerRole` value or a
            matching string.
        slot: Optional active-slot identifier for Whisper or Azure workers.
            When omitted, the slot is resolved from environment-aware defaults.
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
    match role:
        case WorkerRole.YOUTUBE:
            YouTubeWorker().process_queue(poll_interval_seconds=poll_interval_seconds)
        case WorkerRole.WHISPER:
            resolved_slot = resolve_worker_slot(slot, role.value)
            WhisperWorker(resolved_slot).process_queue(poll_interval_seconds=poll_interval_seconds)
        case WorkerRole.AZURE:
            resolved_slot = resolve_worker_slot(slot, role.value)
            AzureWorker(resolved_slot).process_queue(poll_interval_seconds=poll_interval_seconds)


def main() -> None:
    """Parse CLI arguments and start the requested queue worker.

    The command-line interface accepts the worker role plus optional slot and
    polling configuration, then delegates to `process_queue` with the parsed
    values.

    Returns:
        None. The selected worker loop runs until the process is stopped.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('role', nargs='?', choices=WorkerRole.values(), default=os.getenv('WORKER_ROLE', WorkerRole.WHISPER.value))
    parser.add_argument('--slot', default=None, help="Active-slot identifier for whisper/Azure workers. Defaults to WORKER_SLOT, then HOSTNAME.")
    parser.add_argument('--poll-interval-seconds', type=int, default=5)
    args = parser.parse_args()
    process_queue(role=args.role, slot=args.slot, poll_interval_seconds=args.poll_interval_seconds)


if __name__ == "__main__":
    main()
