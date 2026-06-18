import asyncio
import json
import logging
import os
from typing import Optional, Protocol, Set
import uuid

from app.config.settings import settings

class RequestProcessor(Protocol):
    """
    Structural protocol defining the interface for processing incoming test data payloads.
    Decouples the TCP networking layer from business validation and persistence.
    """
    async def process_request(self, ip: str, port: int, payload: str) -> str:
        """
        Process a raw string message payload and return a string response.

        Args:
            ip: Remote client IP address.
            port: Remote client port.
            payload: Raw string message from the client.

        Returns:
            A string response message (JSON formatted).
        """
        ...


class DummyRequestProcessor:
    """
    Fallback request processor for standalone testing without a database.
    Validates JSON structural syntax and returns standard mock ACKs/NACKs.
    """
    async def process_request(self, ip: str, port: int, payload: str) -> str:
        try:
            data = json.loads(payload)
            if not isinstance(data, dict):
                return json.dumps({
                    "status": "failed",
                    "errors": ["Payload must be a JSON object"]
                })
            return json.dumps({
                "status": "success",
                "message": "Stored Successfully",
                "id": str(uuid.uuid4())
            })
        except json.JSONDecodeError:
            return json.dumps({
                "status": "failed",
                "errors": ["Invalid JSON format"]
            })


class ConnectionHandler:
    """
    Manages the full network session lifecycle for a single TCP client connection.
    Reads newline-terminated frames, enforces size and timeout limits,
    delegates processing to the injected RequestProcessor, and returns responses.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        processor: RequestProcessor,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.processor = processor

        peername = writer.get_extra_info("peername")
        self.ip: str = peername[0] if peername else "unknown"
        self.port: int = peername[1] if peername else 0

        self.logger = logging.getLogger("app.server.connections")
        self.error_logger = logging.getLogger("app")
        self._is_closed = False

    async def handle(self) -> None:
        """
        Entry point for the connection coroutine.
        Runs the receive-process-respond loop until EOF, timeout, or error.
        """
        self.logger.info(
            "[PID:%d] Client connected: %s:%d", os.getpid(), self.ip, self.port
        )
        try:
            while True:
                try:
                    data_bytes = await asyncio.wait_for(
                        self.reader.readline(),
                        timeout=settings.SERVER_TIMEOUT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "Timeout after %ss of inactivity for %s:%d",
                        settings.SERVER_TIMEOUT_SECONDS, self.ip, self.port,
                    )
                    break

                if not data_bytes:
                    self.logger.info(
                        "Client %s:%d disconnected (EOF received)", self.ip, self.port
                    )
                    break

                try:
                    payload = data_bytes.decode("utf-8").rstrip("\r\n")
                except UnicodeDecodeError as e:
                    self.logger.warning(
                        "Encoding error from %s:%d: %s", self.ip, self.port, e
                    )
                    await self._send_nack("Invalid encoding. Payload must be UTF-8.")
                    continue

                if not payload.strip():
                    self.logger.warning(
                        "Empty payload from %s:%d", self.ip, self.port
                    )
                    await self._send_nack("Empty packet")
                    continue

                self.logger.info(
                    "Received %d bytes from %s:%d",
                    len(data_bytes), self.ip, self.port,
                )

                try:
                    response = await self.processor.process_request(
                        self.ip, self.port, payload
                    )
                except Exception as e:
                    self.error_logger.exception(
                        "Processor raised unhandled exception for %s:%d: %s",
                        self.ip, self.port, e,
                    )
                    response = json.dumps({
                        "status": "error",
                        "message": "Internal Server Error",
                    })

                self.logger.info("Sending ACK to %s:%d", self.ip, self.port)
                await self._send_raw(response)

        except (asyncio.LimitOverrunError, ValueError) as e:
            self.logger.error(
                "Packet size limit (%d bytes) exceeded by %s:%d: %s",
                settings.SERVER_MAX_PACKET_SIZE_BYTES, self.ip, self.port, e,
            )
            await self._send_nack("Maximum packet size exceeded")
        except ConnectionResetError:
            self.logger.info("Connection reset by peer %s:%d", self.ip, self.port)
        except Exception as e:
            self.error_logger.exception(
                "Unexpected error in handler for %s:%d: %s", self.ip, self.port, e
            )
        finally:
            await self.close()

    async def _send_raw(self, payload: str) -> None:
        """Encodes and sends a string payload with newline framing."""
        try:
            self.writer.write((payload + "\n").encode("utf-8"))
            await self.writer.drain()
        except Exception as e:
            self.logger.error(
                "Write error to %s:%d: %s", self.ip, self.port, e
            )

    async def _send_nack(self, error_message: str) -> None:
        """Formats and sends a structured NACK error response."""
        await self._send_raw(json.dumps({
            "status": "failed",
            "errors": [error_message],
        }))

    async def close(self) -> None:
        """
        Closes the StreamWriter and releases the OS socket file descriptor.
        Idempotent — safe to call multiple times.
        """
        if self._is_closed:
            return
        self._is_closed = True

        try:
            self.writer.close()
        except Exception as e:
            self.logger.debug(
                "writer.close() error for %s:%d: %s", self.ip, self.port, e
            )

        try:
            await self.writer.wait_closed()
            self.logger.info(
                "Socket released for %s:%d", self.ip, self.port
            )
        except Exception as e:
            self.logger.debug(
                "wait_closed() error for %s:%d: %s", self.ip, self.port, e
            )


class Server:
    """
    Asynchronous TCP Server managing binding, concurrency, and lifecycle.

    Design decisions:
    - reuse_address=True: allows immediate port rebinding after restart,
      eliminating OSError [10048] caused by Windows TIME_WAIT socket state.
    - reuse_port=False: intentional — prevents multiple processes accidentally
      sharing the same port in production.
    - Active connection tracking: tasks are stored in a Set and removed via
      done callbacks, providing accurate concurrency metrics at all times.
    - Shutdown is idempotent: _is_shutting_down guard prevents re-entrant calls.
    """

    def __init__(
        self, host: str, port: int, processor: RequestProcessor
    ) -> None:
        self.host = host
        self.port = port
        self.processor = processor
        self.logger = logging.getLogger("app")

        self._server: Optional[asyncio.AbstractServer] = None
        self._active_connections: Set[asyncio.Task[None]] = set()
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down = False

    async def start(self) -> None:
        """
        Binds the server socket and begins accepting connections.

        Key fix: reuse_address=True sets SO_REUSEADDR on the listening socket.
        On Windows this allows re-binding port immediately after shutdown,
        preventing OSError [Errno 10048] when restarting the server quickly.
        """
        self.logger.info(
            "[PID:%d] Binding TCP server on %s:%d...", os.getpid(), self.host, self.port
        )

        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
            limit=settings.SERVER_MAX_PACKET_SIZE_BYTES,
            reuse_address=True,   # ← SO_REUSEADDR: eliminates TIME_WAIT port conflicts
            reuse_port=False,     # ← prevent accidental multi-process port sharing
        )

        # Log the actual bound address (useful when port=0 for dynamic allocation)
        bound = self._server.sockets[0].getsockname()
        self.logger.info(
            "[PID:%d] TCP Server socket bound and listening on %s:%d "
            "(max_packet=%d bytes, max_connections=%d, timeout=%ss)",
            os.getpid(),
            bound[0], bound[1],
            settings.SERVER_MAX_PACKET_SIZE_BYTES,
            settings.SERVER_MAX_CONNECTIONS,
            settings.SERVER_TIMEOUT_SECONDS,
        )

    async def serve_forever(self) -> None:
        """
        Holds the event loop open until the shutdown event is set.
        The `async with self._server` context ensures serve_forever() is called
        on the underlying asyncio server.
        """
        if not self._server:
            raise RuntimeError("Server not started. Call start() first.")

        async with self._server:
            await self._shutdown_event.wait()

    def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Called by asyncio for every new TCP connection.
        Enforces MAX_CONNECTIONS limit before dispatching handler tasks.
        """
        active_count = len(self._active_connections)

        if active_count >= settings.SERVER_MAX_CONNECTIONS:
            peer = writer.get_extra_info("peername")
            self.logger.warning(
                "Rejecting connection from %s — limit reached (%d/%d active)",
                peer, active_count, settings.SERVER_MAX_CONNECTIONS,
            )
            asyncio.create_task(self._reject_client(writer))
            return

        handler = ConnectionHandler(reader, writer, self.processor)
        task = asyncio.create_task(handler.handle())
        self._active_connections.add(task)
        task.add_done_callback(self._on_client_task_done)

        self.logger.debug(
            "Active connections: %d/%d",
            len(self._active_connections), settings.SERVER_MAX_CONNECTIONS,
        )

    async def _reject_client(self, writer: asyncio.StreamWriter) -> None:
        """Sends a connection-limit NACK and immediately closes the socket."""
        try:
            nack = json.dumps({
                "status": "failed",
                "errors": ["Server connection limit exceeded. Try again later."],
            })
            writer.write((nack + "\n").encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def _on_client_task_done(self, task: asyncio.Task[None]) -> None:
        """
        Done callback — removes the task from tracking and logs uncaught exceptions.
        Using discard() is safe even if the task was already removed.
        """
        self._active_connections.discard(task)
        self.logger.debug(
            "Connection task complete. Active connections remaining: %d",
            len(self._active_connections),
        )
        if not task.cancelled():
            exc = task.exception()
            if exc:
                self.logger.error(
                    "Client task exited with unhandled exception: %s",
                    exc, exc_info=exc,
                )

    async def stop(self) -> None:
        """
        Graceful shutdown sequence:
        1. Signal serve_forever() to exit
        2. Close the server socket (stop accepting new connections)
        3. Wait up to 5 seconds for active client tasks to complete
        4. Force-cancel any remaining tasks
        5. Log final state

        Idempotent — safe to call multiple times.
        """
        if self._is_shutting_down:
            self.logger.debug("Shutdown already in progress — ignoring duplicate call.")
            return
        self._is_shutting_down = True

        active_count = len(self._active_connections)
        self.logger.info(
            "[PID:%d] Graceful shutdown initiated. Active connections: %d",
            os.getpid(), active_count,
        )

        # Unblock serve_forever()
        self._shutdown_event.set()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self.logger.info("TCP listener socket closed — no longer accepting connections.")

        if self._active_connections:
            self.logger.info(
                "Waiting up to 5s for %d active client task(s) to complete...",
                len(self._active_connections),
            )
            done, pending = await asyncio.wait(
                self._active_connections,
                timeout=5.0,
            )

            if pending:
                self.logger.warning(
                    "Timeout expired. Force-cancelling %d client task(s).", len(pending)
                )
                for task in pending:
                    task.cancel()
                # Plain gather — no shield. During shutdown the event loop
                # is still running; shield here creates orphaned tasks that
                # prevent clean loop closure and can cause ResourceWarning.
                await asyncio.gather(*pending, return_exceptions=True)

        all_tasks = asyncio.all_tasks()
        self.logger.info(
            "[PID:%d] Shutdown complete. Remaining asyncio tasks in loop: %d",
            os.getpid(), len(all_tasks),
        )
