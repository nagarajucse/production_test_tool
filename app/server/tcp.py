import asyncio
import json
import logging
from typing import Any, Dict, Optional, Protocol, Set
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
    Fallback request processor used for Step 2 testing.
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
            # Mock successful save with a fresh UUID
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
    Handles the network session lifecycle for a single TCP client.
    Reads lines of text up to a maximum byte limit, enforces timeouts,
    delegates parsing/saving to the RequestProcessor, and returns responses.
    """
    def __init__(
        self, 
        reader: asyncio.StreamReader, 
        writer: asyncio.StreamWriter, 
        processor: RequestProcessor
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.processor = processor
        
        # Extract peer metadata
        peername = writer.get_extra_info("peername")
        self.ip: str = peername[0] if peername else "unknown"
        self.port: int = peername[1] if peername else 0
        
        self.logger = logging.getLogger("app.server.connections")
        self.error_logger = logging.getLogger("app")

    async def handle(self) -> None:
        """
        Runs the socket loop for the connection.
        Reads newline-terminated frames, processes them, and writes results back to the stream.
        """
        self.logger.info("Client connected from %s:%d", self.ip, self.port)
        try:
            while True:
                try:
                    # Enforce timeout on client socket read
                    data_bytes = await asyncio.wait_for(
                        self.reader.readline(),
                        timeout=settings.SERVER_TIMEOUT_SECONDS
                      )
                except asyncio.TimeoutError:
                    self.logger.warning("Connection timeout (no communication for %ds) for %s:%d", 
                                        settings.SERVER_TIMEOUT_SECONDS, self.ip, self.port)
                    break

                if not data_bytes:
                    # EOF indicates client closed the write half of connection
                    self.logger.info("Client %s:%d disconnected (EOF received)", self.ip, self.port)
                    break

                # Parse and process the stream packet
                try:
                    payload = data_bytes.decode("utf-8").rstrip("\r\n")
                except UnicodeDecodeError as e:
                    self.logger.warning("Encoding error from client %s:%d: %s", self.ip, self.port, str(e))
                    await self._send_nack("Invalid encoding. Payload must be UTF-8.")
                    continue

                if not payload.strip():
                    self.logger.warning("Empty payload received from client %s:%d", self.ip, self.port)
                    await self._send_nack("Empty packet")
                    continue

                # Process payload using injected business logic processor
                try:
                    response = await self.processor.process_request(self.ip, self.port, payload)
                except Exception as e:
                    self.error_logger.exception("Internal error executing request processor for %s:%d: %s", 
                                                self.ip, self.port, str(e))
                    response = json.dumps({
                        "status": "error",
                        "message": "Internal Server Error"
                    })

                # Return response framed with a newline
                await self._send_raw(response)

        except (asyncio.LimitOverrunError, ValueError) as e:
            self.logger.error("Maximum packet size limit (%d bytes) exceeded by %s:%d: %s", 
                              settings.SERVER_MAX_PACKET_SIZE_BYTES, self.ip, self.port, str(e))
            await self._send_nack("Maximum packet size exceeded")
        except ConnectionResetError:
            self.logger.info("Connection reset by peer %s:%d", self.ip, self.port)
        except Exception as e:
            self.error_logger.exception("Unexpected error in connection handler for %s:%d: %s", 
                                        self.ip, self.port, str(e))
        finally:
            await self.close()

    async def _send_raw(self, payload: str) -> None:
        """Sends raw string data over the socket, appending newline framing."""
        try:
            self.writer.write((payload + "\n").encode("utf-8"))
            await self.writer.drain()
        except Exception as e:
            self.logger.error("Error writing message to %s:%d: %s", self.ip, self.port, str(e))

    async def _send_nack(self, error_message: str) -> None:
        """Format and send a structured NACK error response."""
        nack = json.dumps({
            "status": "failed",
            "errors": [error_message]
        })
        await self._send_raw(nack)

    async def close(self) -> None:
        """Closes the socket writer resources cleanly."""
        try:
            self.writer.close()
            await self.writer.wait_closed()
            self.logger.info("Socket closed successfully for %s:%d", self.ip, self.port)
        except Exception as e:
            self.logger.debug("Error while closing socket for %s:%d: %s", self.ip, self.port, str(e))


class Server:
    """
    Asynchronous TCP Socket Server coordinating connection handling tasks.
    Manages startup binding, lifecycle callbacks, and graceful shutdown.
    """
    def __init__(self, host: str, port: int, processor: RequestProcessor) -> None:
        self.host = host
        self.port = port
        self.processor = processor
        self.logger = logging.getLogger("app")
        
        self._server: Optional[asyncio.AbstractServer] = None
        self._active_connections: Set[asyncio.Task[None]] = set()
        self._shutdown_event = asyncio.Event()

    async def start(self) -> None:
        """Starts the server listener socket."""
        # Enforce server-wide buffer limits for client readers to prevent RAM bloating
        self._server = await asyncio.start_server(
            self._handle_client,
            host=self.host,
            port=self.port,
            limit=settings.SERVER_MAX_PACKET_SIZE_BYTES
        )
        self.logger.info("Asynchronous TCP Server successfully initialized and listening on %s:%d", 
                         self.host, self.port)

    async def serve_forever(self) -> None:
        """Blocks the active coroutine loop and serves requests until shutdown is triggered."""
        if not self._server:
            raise RuntimeError("Server not started. Invoke start() first.")
        
        async with self._server:
            await self._shutdown_event.wait()

    def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Callback for incoming socket connections. Registers task to tracking set."""
        handler = ConnectionHandler(reader, writer, self.processor)
        task = asyncio.create_task(handler.handle())
        self._active_connections.add(task)
        task.add_done_callback(self._active_connections.discard)

    async def stop(self) -> None:
        """Performs a graceful stop of the socket listener and waits for client tasks to drain."""
        self.logger.info("Graceful shutdown initiated. Stopping TCP listener...")
        self._shutdown_event.set()

        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self.logger.info("TCP Listener stopped (no longer accepting new client sockets).")

        if self._active_connections:
            self.logger.info("Draining %d active client handler tasks...", len(self._active_connections))
            # Grant a timeout period (e.g. 5 seconds) to allow clients to flush remaining tasks
            done, pending = await asyncio.wait(
                self._active_connections,
                timeout=5.0
            )
            
            if pending:
                self.logger.warning("Shutdown timeout expired. Force-canceling %d remaining clients...", len(pending))
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                
        self.logger.info("Graceful shutdown complete. Server terminated.")
