import asyncio
import json
import unittest

from app.config.settings import settings
from app.server.tcp import Server, DummyRequestProcessor

class TestTCPServer(unittest.IsolatedAsyncioTestCase):
    """
    Integration test suite verifying the asynchronous TCP Server's concurrency,
    packet size limits, inactivity timeouts, and request processing.
    """
    async def asyncSetUp(self) -> None:
        # Cache original settings to restore them post-test
        self.original_port = settings.SERVER_PORT
        self.original_timeout = settings.SERVER_TIMEOUT_SECONDS
        self.original_max_packet = settings.SERVER_MAX_PACKET_SIZE_BYTES
        self.original_max_connections = settings.SERVER_MAX_CONNECTIONS
        
        # Override configuration for fast, predictable unit tests
        settings.SERVER_TIMEOUT_SECONDS = 0.5  # 500ms timeout
        settings.SERVER_MAX_PACKET_SIZE_BYTES = 100  # Strict packet size for overflow test
        settings.SERVER_MAX_CONNECTIONS = 20  # Set limit high enough for concurrency tests
        
        # Initialize and bind server to dynamic port (port=0) to prevent port conflicts
        self.processor = DummyRequestProcessor()
        self.server = Server(host="127.0.0.1", port=0, processor=self.processor)
        await self.server.start()
        
        # Extract the port dynamically allocated by the OS
        self.port = self.server._server.sockets[0].getsockname()[1]
        
        # Spin up the server's serve loop in the background
        self.server_task = asyncio.create_task(self.server.serve_forever())

    async def asyncTearDown(self) -> None:
        # Stop the server and clean up background tasks
        await self.server.stop()
        self.server_task.cancel()
        try:
            await self.server_task
        except asyncio.CancelledError:
            pass
            
        # Restore original configuration settings
        settings.SERVER_PORT = self.original_port
        settings.SERVER_TIMEOUT_SECONDS = self.original_timeout
        settings.SERVER_MAX_PACKET_SIZE_BYTES = self.original_max_packet
        settings.SERVER_MAX_CONNECTIONS = self.original_max_connections

    async def test_valid_json_packet(self) -> None:
        """Verifies that the server processes a valid JSON packet and returns a success ACK."""
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        
        try:
            payload = json.dumps({"device_id": "DEV-999", "result": "PASS"})
            writer.write((payload + "\n").encode("utf-8"))
            await writer.drain()
            
            response_bytes = await reader.readline()
            response = json.loads(response_bytes.decode("utf-8").strip())
            
            self.assertEqual(response["status"], "success")
            self.assertEqual(response["message"], "Stored Successfully")
            self.assertIn("id", response)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_invalid_json_packet(self) -> None:
        """Verifies that malformed JSON payloads return a structured failed NACK response."""
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        
        try:
            # Send plain string lacking JSON layout
            writer.write(b"INVALID_STRING_PAYLOAD\n")
            await writer.drain()
            
            response_bytes = await reader.readline()
            response = json.loads(response_bytes.decode("utf-8").strip())
            
            self.assertEqual(response["status"], "failed")
            self.assertIn("errors", response)
            self.assertEqual(response["errors"][0], "Invalid JSON format")
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_packet_size_exceeded(self) -> None:
        """Verifies that sending a packet larger than the limit results in rejection."""
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        
        try:
            # Generate a payload exceeding the 100-byte test limit
            huge_payload = "A" * 150 + "\n"
            writer.write(huge_payload.encode("utf-8"))
            await writer.drain()
            
            response_bytes = await reader.readline()
            response = json.loads(response_bytes.decode("utf-8").strip())
            
            self.assertEqual(response["status"], "failed")
            self.assertIn("errors", response)
            self.assertEqual(response["errors"][0], "Maximum packet size exceeded")
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_client_timeout(self) -> None:
        """Verifies that inactive sockets are closed automatically after the timeout threshold."""
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        
        try:
            # Sleep longer than the 0.5s timeout threshold without sending data
            await asyncio.sleep(0.8)
            
            # Read from the connection; it should yield EOF (empty bytes)
            response_bytes = await reader.readline()
            self.assertEqual(response_bytes, b"")
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_multiple_concurrent_clients(self) -> None:
        """Verifies that the server handles multiple active connections concurrently."""
        client_count = 10
        connections = []
        
        try:
            # Establish all connections concurrently
            for _ in range(client_count):
                conn = await asyncio.open_connection("127.0.0.1", self.port)
                connections.append(conn)
                
            # Send messages concurrently
            for i, (reader, writer) in enumerate(connections):
                payload = json.dumps({"test_index": i})
                writer.write((payload + "\n").encode("utf-8"))
                await writer.drain()
                
            # Read and verify responses
            for reader, writer in connections:
                response_bytes = await reader.readline()
                response = json.loads(response_bytes.decode("utf-8").strip())
                self.assertEqual(response["status"], "success")
        finally:
            for reader, writer in connections:
                writer.close()
                await writer.wait_closed()

    async def test_max_connections_exceeded(self) -> None:
        """Verifies that connections exceeding the maximum limit are rejected with a structured NACK."""
        original_limit = settings.SERVER_MAX_CONNECTIONS
        settings.SERVER_MAX_CONNECTIONS = 3
        connections = []
        try:
            # Open the maximum allowed connections (3)
            for _ in range(3):
                conn = await asyncio.open_connection("127.0.0.1", self.port)
                connections.append(conn)
                
            # The 4th connection should be rejected
            reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
            try:
                response_bytes = await reader.readline()
                response = json.loads(response_bytes.decode("utf-8").strip())
                self.assertEqual(response["status"], "failed")
                self.assertIn("connection limit exceeded", response["errors"][0])
            finally:
                writer.close()
                await writer.wait_closed()
        finally:
            # Clean up the initial 3 connections
            for reader, writer in connections:
                writer.close()
                await writer.wait_closed()
            settings.SERVER_MAX_CONNECTIONS = original_limit
