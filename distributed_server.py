"""
Distributed Math Battle Server

Implements a distributed server with multiple nodes, RPC, mutual exclusion,
resource management, and other distributed system concepts.
"""

import socket
import threading
import json
import time
import random
import uuid
import sys
import argparse
from typing import Dict, List, Tuple, Any

from distributed_components import (
    LogicalClock, ResourceManager, MutualExclusionManager,
    MessageRouter, RPCManager, TaskScheduler
)

# Constants
DEFAULT_HOST = "0.0.0.0"  # Listen on all interfaces
DEFAULT_PORT = 5555
NUM_NODES = 3  # Number of server nodes


class GameManager:
    """Manages game rooms and state"""

    def __init__(self):
        """Initialize the game manager"""
        self.rooms = {}  # room_id -> {players, state}
        self.player_rooms = {}  # player_id -> room_id
        self.lock = threading.Lock()

    def create_room(self, creator_id: str) -> str:
        """Create a new game room and return its ID"""
        with self.lock:
            # Generate a room ID (6 alphanumeric characters)
            room_id = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

            # Create room object
            self.rooms[room_id] = {
                "players": [creator_id],
                "state": None,
                "creator": creator_id,
                "creation_time": time.time()
            }

            # Associate player with room
            self.player_rooms[creator_id] = room_id

            return room_id

    def join_room(self, room_id: str, player_id: str) -> Tuple[bool, str]:
        """Join a player to a room. Returns (success, message)"""
        with self.lock:
            # Validate room exists
            if room_id not in self.rooms:
                return False, "Room does not exist"

            # Check if room is full (max 2 players)
            if len(self.rooms[room_id]["players"]) >= 2:
                return False, "Room is full"

            # Check if player is already in the room
            if player_id in self.rooms[room_id]["players"]:
                return False, "You are already in this room"

            # Add player to room
            self.rooms[room_id]["players"].append(player_id)

            # Associate player with room
            self.player_rooms[player_id] = room_id

            return True, "Joined room successfully"

    def is_room_ready(self, room_id: str) -> bool:
        """Check if a room has enough players to start"""
        with self.lock:
            if room_id not in self.rooms:
                return False

            return len(self.rooms[room_id]["players"]) == 2

    def get_players(self, room_id: str) -> List[str]:
        """Get all players in a room"""
        with self.lock:
            if room_id not in self.rooms:
                return []

            return self.rooms[room_id]["players"].copy()

    def set_game_state(self, room_id: str, state: Dict):
        """Set the game state for a room"""
        with self.lock:
            if room_id not in self.rooms:
                return

            self.rooms[room_id]["state"] = state

    def get_game_state(self, room_id: str) -> Dict:
        """Get the game state for a room"""
        with self.lock:
            if room_id not in self.rooms or not self.rooms[room_id]["state"]:
                return {}

            return self.rooms[room_id]["state"]

    def get_player_room(self, player_id: str) -> str:
        """Get the room a player is in"""
        with self.lock:
            return self.player_rooms.get(player_id)

    def remove_player(self, player_id: str):
        """Remove a player from their room"""
        with self.lock:
            if player_id not in self.player_rooms:
                return

            room_id = self.player_rooms[player_id]
            if room_id in self.rooms and player_id in self.rooms[room_id]["players"]:
                self.rooms[room_id]["players"].remove(player_id)

                # If room is empty, remove it
                if not self.rooms[room_id]["players"]:
                    del self.rooms[room_id]

            # Remove player from player_rooms
            del self.player_rooms[player_id]


class QuestionGenerator:
    """Generates math questions with varying difficulty"""

    def __init__(self):
        """Initialize the question generator"""
        self.question_id = 0

    def generate_question(self, difficulty):
        """Generate a single math question"""
        self.question_id += 1

        if difficulty == 'easy':
            # Addition and subtraction
            if random.random() < 0.5:
                # Addition
                a = random.randint(1, 20)
                b = random.randint(1, 20)
                text = f"What is {a} + {b}?"
                answer = str(a + b)
            else:
                # Subtraction
                a = random.randint(10, 30)
                b = random.randint(1, a)
                text = f"What is {a} - {b}?"
                answer = str(a - b)
        elif difficulty == 'medium':
            # Multiplication and division
            if random.random() < 0.5:
                # Multiplication
                a = random.randint(2, 12)
                b = random.randint(2, 12)
                text = f"What is {a} × {b}?"
                answer = str(a * b)
            else:
                # Division (ensure it divides evenly)
                b = random.randint(2, 12)
                c = random.randint(1, 10)
                a = b * c
                text = f"What is {a} ÷ {b}?"
                answer = str(c)
        else:
            # Hard (mixed operations)
            op1 = random.choice(['+', '-', '×'])
            op2 = random.choice(['+', '-', '×'])

            a = random.randint(2, 15)
            b = random.randint(2, 15)
            c = random.randint(2, 10)

            if op1 == '+':
                result1 = a + b
            elif op1 == '-':
                result1 = a - b
            else:
                result1 = a * b

            if op2 == '+':
                result = result1 + c
            elif op2 == '-':
                result = result1 - c
            else:
                result = result1 * c

            text = f"What is {a} {op1} {b} {op2} {c}?"
            answer = str(result)

        return {
            "id": self.question_id,
            "text": text,
            "answer": answer,
            "difficulty": difficulty
        }

    def generate_questions(self, count, difficulty='medium'):
        """Generate a list of questions"""
        return [self.generate_question(difficulty) for _ in range(count)]


class StatsManager:
    """Manages player statistics"""

    def __init__(self):
        """Initialize the stats manager"""
        self.player_stats = {}  # player_id -> {wins, losses, games}
        self.lock = threading.Lock()

    def record_game_result(self, winner_id: str, loser_id: str):
        """Record the result of a game"""
        with self.lock:
            # Initialize player stats if needed
            if winner_id not in self.player_stats:
                self.player_stats[winner_id] = {"wins": 0, "losses": 0, "games": 0}
            if loser_id not in self.player_stats:
                self.player_stats[loser_id] = {"wins": 0, "losses": 0, "games": 0}

            # Update stats
            self.player_stats[winner_id]["wins"] += 1
            self.player_stats[winner_id]["games"] += 1
            self.player_stats[loser_id]["losses"] += 1
            self.player_stats[loser_id]["games"] += 1

    def get_player_stats(self, player_id: str) -> Dict:
        """Get stats for a player"""
        with self.lock:
            if player_id not in self.player_stats:
                return {"wins": 0, "losses": 0, "games": 0, "win_rate": 0}

            stats = self.player_stats[player_id]
            games = stats["games"]
            win_rate = (stats["wins"] / games) * 100 if games > 0 else 0

            return {
                "wins": stats["wins"],
                "losses": stats["losses"],
                "games": games,
                "win_rate": win_rate
            }

    def get_leaderboard(self, limit=10) -> List:
        """Get the leaderboard (top players by wins)"""
        with self.lock:
            # Sort players by wins
            sorted_players = sorted(
                self.player_stats.items(),
                key=lambda x: x[1]["wins"],
                reverse=True
            )

            # Return top players
            return [
                {"player_id": player_id, "wins": stats["wins"]}
                for player_id, stats in sorted_players[:limit]
            ]


class DistributedServer:
    """Distributed implementation of the Math Battle server"""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, num_nodes=NUM_NODES):
        """Initialize the server"""
        self.host = host
        self.port = port
        self.num_nodes = num_nodes
        self.server_socket = None
        self.running = False
        self.clients = {}  # client_id -> socket
        self.client_nodes = {}  # client_id -> node_id
        self.client_threads = {}  # client_id -> thread

        # Distributed system components
        self.logical_clock = LogicalClock()
        self.resource_manager = ResourceManager()
        self.mutex_manager = MutualExclusionManager(num_nodes)
        self.message_router = MessageRouter(num_nodes)
        self.rpc_manager = RPCManager()
        self.task_scheduler = TaskScheduler(num_nodes)

        # Create game components
        self.game_manager = GameManager()
        self.question_generator = QuestionGenerator()
        self.stats_manager = StatsManager()

        # Register RPC methods
        self._register_rpc_methods()

        # Thread lock
        self.lock = threading.Lock()

    def start(self):
        """Start the server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)  # Allow up to 10 queued connections
            self.running = True

            print(f"Server started on {self.host}:{self.port} with {self.num_nodes} nodes")

            # Start node threads
            self._start_node_threads()

            # Accept clients
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    client_id = str(uuid.uuid4())

                    # Assign to a node (round-robin)
                    node_id = len(self.clients) % self.num_nodes

                    print(f"New connection from {addr}, assigned client ID {client_id} to node {node_id}")

                    # Create client thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_id, node_id)
                    )
                    client_thread.daemon = True
                    client_thread.start()

                    # Store client info
                    with self.lock:
                        self.clients[client_id] = client_socket
                        self.client_nodes[client_id] = node_id
                        self.client_threads[client_id] = client_thread

                    # Send welcome message
                    welcome_msg = {
                        "type": "welcome",
                        "client_id": client_id,
                        "timestamp": self.logical_clock.increment()
                    }
                    self.send_to_client(client_id, welcome_msg)

                except Exception as e:
                    if self.running:
                        print(f"Error accepting connection: {e}")

        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the server"""
        self.running = False

        # Close all client connections
        with self.lock:
            for client_id in list(self.clients.keys()):
                try:
                    self.clients[client_id].close()
                except:
                    pass

            self.clients = {}
            self.client_nodes = {}
            self.client_threads = {}

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        print("Server stopped")

    def handle_client(self, client_socket, client_id, node_id):
        """Handle client connection"""
        try:
            buffer = b''
            while self.running:
                try:
                    # Receive data
                    data = client_socket.recv(4096)
                    if not data:
                        break  # Client disconnected

                    # Add to buffer
                    buffer += data

                    # Process complete messages
                    while b'\n' in buffer:
                        # Split on newline
                        message_data, buffer = buffer.split(b'\n', 1)

                        if not message_data.strip():
                            continue

                        # Parse and process the message
                        try:
                            message = json.loads(message_data.decode('utf-8'))
                            self.process_message(message, client_id)
                        except json.JSONDecodeError as e:
                            print(f"Invalid JSON from client {client_id}: {e}")
                            print(f"Raw data: {message_data}")

                except ConnectionError:
                    break
                except Exception as e:
                    print(f"Error handling client {client_id}: {e}")
                    break

        finally:
            # Client disconnected, clean up
            self.disconnect_client(client_id)
            print(f"Client {client_id} disconnected")

    def process_message(self, message, client_id):
        """Process a message from a client"""
        message_type = message.get("type")

        # Update logical clock
        self.logical_clock.increment()

        # Handle message based on type
        if message_type == "create_room":
            self.handle_create_room(client_id)

        elif message_type == "join_room":
            room_id = message.get("room_id")
            self.handle_join_room(client_id, room_id)

        elif message_type == "answer":
            room_id = message.get("room_id")
            answer = message.get("answer")
            self.handle_answer(client_id, room_id, answer)

        elif message_type == "rpc_call":
            method = message.get("method")
            params = message.get("params", [])
            call_id = message.get("call_id")
            self.handle_rpc_call(client_id, method, params, call_id)

        elif message_type == "resource_request":
            resource_id = message.get("resource_id")
            self.handle_resource_request(client_id, resource_id)

        elif message_type == "resource_release":
            resource_id = message.get("resource_id")
            self.handle_resource_release(client_id, resource_id)

    def handle_create_room(self, client_id: str):
        """Handle a client request to create a game room"""
        # FIXED: Directly create room without mutual exclusion
        # Create room
        room_id = self.game_manager.create_room(client_id)

        # Send confirmation to client
        response = {
            "type": "create_room",
            "success": True,
            "room_id": room_id
        }

        self.send_to_client(client_id, response)
        print(f"Created room {room_id} for client {client_id}")

    def handle_join_room(self, client_id: str, room_id: str):
        """Handle a client request to join a game room"""
        # Join the room
        success, message = self.game_manager.join_room(room_id, client_id)

        # Send response to client
        response = {
            "type": "join_room",
            "success": success,
            "message": message,
            "room_id": room_id
        }

        self.send_to_client(client_id, response)

        if success:
            print(f"Client {client_id} joined room {room_id}")

            # Check if room is ready to start (2 players)
            if self.game_manager.is_room_ready(room_id):
                print(f"Room {room_id} is ready, starting game")
                self.start_game(room_id)
        else:
            print(f"Client {client_id} failed to join room {room_id}: {message}")

    def start_game(self, room_id: str):
        """Start a game in a room"""
        # Get all players in room
        players = self.game_manager.get_players(room_id)

        # Generate questions
        questions = self.question_generator.generate_questions(5, 'medium')

        # Create game state
        game_state = {
            "room_id": room_id,
            "players": players,
            "questions": questions,
            "current_question": 0,
            "scores": {player: 0 for player in players},
            "start_time": time.time(),
            "game_over": False
        }

        # Store game state
        self.game_manager.set_game_state(room_id, game_state)

        # Notify players that game is starting
        for player_id in players:
            start_msg = {
                "type": "game_start",
                "room_id": room_id,
                "player_count": len(players),
                "question_count": len(questions)
            }

            self.send_to_client(player_id, start_msg)

        # Send first question to all players
        self.send_question_to_all_players(room_id)

    def send_question_to_all_players(self, room_id: str):
        """Send the current question to all players in a room"""
        game_state = self.game_manager.get_game_state(room_id)
        if not game_state:
            return

        current_question_index = game_state["current_question"]
        if current_question_index >= len(game_state["questions"]):
            # No more questions, end the game
            self.end_game(room_id)
            return

        current_question = game_state["questions"][current_question_index]

        # Send question to each player
        for player_id in game_state["players"]:
            question_msg = {
                "type": "question",
                "room_id": room_id,
                "question_text": current_question["text"],
                "question_id": current_question["id"],
                "question_number": current_question_index + 1,
                "total_questions": len(game_state["questions"])
            }

            self.send_to_client(player_id, question_msg)

    def handle_answer(self, client_id: str, room_id: str, answer: str):
        """Handle a client's answer to a question"""
        game_state = self.game_manager.get_game_state(room_id)
        if not game_state or game_state.get("game_over", True):
            # No active game or game already over
            error_msg = {
                "type": "error",
                "message": "No active game or game already over"
            }

            self.send_to_client(client_id, error_msg)
            return

        current_question_index = game_state["current_question"]
        current_question = game_state["questions"][current_question_index]

        # Check if answer is correct
        is_correct = current_question["answer"] == answer

        # Update score if correct
        if is_correct:
            game_state["scores"][client_id] += 1

        # Send result to client
        result_msg = {
            "type": "answer",
            "room_id": room_id,
            "correct": is_correct,
            "correct_answer": current_question["answer"]
        }

        self.send_to_client(client_id, result_msg)

        # Move to next question
        game_state["current_question"] += 1

        # Update game state
        self.game_manager.set_game_state(room_id, game_state)

        # Check if all questions have been answered
        if game_state["current_question"] >= len(game_state["questions"]):
            # End the game
            self.end_game(room_id)
        else:
            # Send next question
            self.send_question_to_all_players(room_id)

    def end_game(self, room_id: str):
        """End a game and send results to players"""
        game_state = self.game_manager.get_game_state(room_id)
        if not game_state:
            return

        # Mark game as over
        game_state["game_over"] = True
        self.game_manager.set_game_state(room_id, game_state)

        # Calculate winner
        scores = game_state["scores"]
        winner = max(scores, key=scores.get) if scores else None

        # Prepare list of player results
        results = []
        for player_id, score in scores.items():
            results.append({
                "player_id": player_id,
                "score": score,
                "is_winner": player_id == winner
            })

        # Send game over message to all players
        for player_id in game_state["players"]:
            game_over_msg = {
                "type": "game_over",
                "room_id": room_id,
                "results": results,
                "your_score": scores.get(player_id, 0),
                "winner": winner
            }

            self.send_to_client(player_id, game_over_msg)

    def handle_rpc_call(self, client_id: str, method: str, params: List, call_id: Any):
        """Handle an RPC call from a client"""
        # Execute the RPC call
        result = self.rpc_manager.call(method, *params)

        # Send result to client
        response = {
            "type": "rpc_result",
            "call_id": call_id,
            "result": result
        }

        self.send_to_client(client_id, response)

    def handle_resource_request(self, client_id: str, resource_id: str):
        """Handle a resource request from a client"""
        # Try to acquire the resource
        success = self.resource_manager.request_resource(client_id, resource_id)

        # Send response to client
        response = {
            "type": "resource_response",
            "resource_id": resource_id,
            "granted": success
        }

        self.send_to_client(client_id, response)

    def handle_resource_release(self, client_id: str, resource_id: str):
        """Handle a resource release from a client"""
        # Release the resource
        self.resource_manager.release_resource(client_id, resource_id)

        # Send confirmation to client
        response = {
            "type": "resource_released",
            "resource_id": resource_id
        }

        self.send_to_client(client_id, response)

    def send_to_client(self, client_id: str, message: Dict):
        """Send a message to a specific client"""
        if client_id not in self.clients:
            return False

        # Add timestamp from logical clock
        message["timestamp"] = self.logical_clock.get_time()

        try:
            # Add newline for message separation
            self.clients[client_id].send(json.dumps(message).encode('utf-8') + b'\n')
            return True
        except Exception as e:
            print(f"Error sending to client {client_id}: {e}")
            self.disconnect_client(client_id)
            return False

    def disconnect_client(self, client_id: str):
        """Disconnect a client and clean up"""
        with self.lock:
            # Close socket
            if client_id in self.clients:
                try:
                    self.clients[client_id].close()
                except:
                    pass

                del self.clients[client_id]

            # Remove from nodes
            if client_id in self.client_nodes:
                del self.client_nodes[client_id]

            # Remove from client_threads
            if client_id in self.client_threads:
                del self.client_threads[client_id]

        # Release all resources
        self.resource_manager.release_all_client_resources(client_id)

        # Remove from game manager
        self.game_manager.remove_player(client_id)

    def _register_rpc_methods(self):
        """Register RPC methods that clients can call"""

        # Calculate expression
        def calculate_expression(expression):
            try:
                # Security: Limit the allowed operations
                allowed_chars = set("0123456789+-*/() ")
                if not all(c in allowed_chars for c in expression):
                    return {"status": "error", "message": "Invalid characters in expression"}

                # Further security: Use eval with restricted globals/locals
                result = eval(expression, {"__builtins__": {}}, {})
                return {"status": "success", "result": result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        # Get player stats
        def get_player_stats(player_id=None):
            stats = self.stats_manager.get_player_stats(player_id)
            return {"status": "success", "stats": stats}

        # Get leaderboard
        def get_leaderboard(limit=10):
            leaderboard = self.stats_manager.get_leaderboard(limit)
            return {"status": "success", "leaderboard": leaderboard}

        # Register methods
        self.rpc_manager.register_method("calculate_expression", calculate_expression)
        self.rpc_manager.register_method("get_player_stats", get_player_stats)
        self.rpc_manager.register_method("get_leaderboard", get_leaderboard)

    def _start_node_threads(self):
        """Start threads for each node to process tasks"""
        for i in range(self.num_nodes):
            thread = threading.Thread(target=self._node_worker, args=(i,))
            thread.daemon = True
            thread.start()

    def _node_worker(self, node_id):
        """Worker thread for a node"""
        print(f"Node {node_id} started")
        while self.running:
            # Get a task for this node
            task = self.task_scheduler.get_task(node_id, timeout=1)
            if task:
                self._process_task(task, node_id)

    def _process_task(self, task, node_id):
        """Process a task assigned to a node"""
        task_type = task.get("type")

        if task_type == "handle_client":
            client_id = task.get("client_id")
            if client_id in self.clients:
                self.handle_client(self.clients[client_id], client_id, node_id)

        elif task_type == "start_game":
            room_id = task.get("room_id")
            self.start_game(room_id)


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Distributed Math Battle Server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind to")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to bind to")
    parser.add_argument("--nodes", type=int, default=NUM_NODES, help="Number of server nodes")
    args = parser.parse_args()

    # Create and start server
    server = DistributedServer(args.host, args.port, args.nodes)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.stop()


if __name__ == "__main__":
    main()