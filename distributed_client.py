"""
Distributed Math Battle Client

Implements features to interact with the distributed server including RPC calls,
resource management, and other distributed system concepts.
"""

import socket
import threading
import json
import time
import os
import sys
import tkinter as tk
from tkinter import messagebox, font
from typing import Dict, List, Callable, Tuple

# Server configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5555

# Colors
BG_COLOR = "#1e3d59"  # Dark blue
BUTTON_COLOR = "#f5f0e1"  # Off-white
TEXT_COLOR = "#ffffff"  # White
HIGHLIGHT_COLOR = "#ff6e40"  # Orange
SUCCESS_COLOR = "#57c84d"  # Green
ERROR_COLOR = "#ff5252"  # Red


class LocalClock:
    """A local logical clock for the client"""

    def __init__(self):
        """Initialize the logical clock"""
        self.time = 0
        self.lock = threading.Lock()

    def increment(self):
        """Increment the logical clock"""
        with self.lock:
            self.time += 1
            return self.time

    def update(self, received_time):
        """Update the logical clock based on a received timestamp"""
        with self.lock:
            self.time = max(self.time, received_time) + 1
            return self.time

    def get_time(self):
        """Get the current logical clock value"""
        with self.lock:
            return self.time


class DistributedMathBattleClient:
    """Client for the distributed Math Battle server"""

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT):
        """Initialize the client"""
        self.host = host
        self.port = port
        self.socket = None
        self.connected = False
        self.client_id = None
        self.receive_thread = None

        # Game state
        self.current_room = None
        self.current_question = None
        self.question_number = 0
        self.total_questions = 0
        self.game_results = None

        # Distributed system components
        self.logical_clock = LocalClock()
        self.held_resources = set()
        self.pending_resources = set()
        self.rpc_callbacks = {}
        self.rpc_counter = 0

        # Message handlers
        self.handlers = {}
        self._register_default_handlers()

    def connect(self):
        """Connect to the server with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(5)  # Set timeout for connection
                self.socket.connect((self.host, self.port))

                # Connection successful
                self.socket.settimeout(None)  # Reset timeout
                self.connected = True

                # Start thread to receive messages
                self.receive_thread = threading.Thread(target=self._receive_messages)
                self.receive_thread.daemon = True
                self.receive_thread.start()

                return True
            except Exception as e:
                print(f"Connection attempt {attempt+1} failed: {e}")
                if self.socket:
                    self.socket.close()
                    self.socket = None

                # If last attempt, give up
                if attempt == max_retries - 1:
                    print(f"Failed to connect after {max_retries} attempts")
                    return False

                # Wait before retrying
                time.sleep(1)

    def disconnect(self):
        """Disconnect from the server"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def register_handler(self, message_type, handler_func):
        """Register a handler for a specific message type"""
        self.handlers[message_type] = handler_func

    def send_message(self, message):
        """Send a message to the server"""
        if not self.connected or not self.socket:
            return False

        # Add timestamp from logical clock
        message["timestamp"] = self.logical_clock.increment()

        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n')
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            self.disconnect()
            return False

    def create_room(self):
        """Create a new game room"""
        message = {"type": "create_room"}
        return self.send_message(message)

    def join_room(self, room_id):
        """Join an existing game room"""
        message = {"type": "join_room", "room_id": room_id}
        return self.send_message(message)

    def submit_answer(self, room_id, answer):
        """Submit an answer to a question"""
        message = {"type": "answer", "room_id": room_id, "answer": answer}
        return self.send_message(message)

    def rpc_call(self, method, params=None, callback=None):
        """Make an RPC call to the server"""
        if params is None:
            params = []

        # Generate a unique ID for this call
        call_id = self.rpc_counter
        self.rpc_counter += 1

        message = {
            "type": "rpc_call",
            "method": method,
            "params": params,
            "call_id": call_id
        }

        # Store callback if provided
        if callback:
            self.rpc_callbacks[call_id] = callback

        return self.send_message(message)

    def request_resource(self, resource_id):
        """Request a shared resource"""
        # Add to pending resources
        self.pending_resources.add(resource_id)

        message = {
            "type": "resource_request",
            "resource_id": resource_id
        }

        return self.send_message(message)

    def release_resource(self, resource_id):
        """Release a shared resource"""
        # Remove from held resources
        if resource_id in self.held_resources:
            self.held_resources.remove(resource_id)

        message = {
            "type": "resource_release",
            "resource_id": resource_id
        }

        return self.send_message(message)

    def _register_default_handlers(self):
        """Register default message handlers"""
        self.register_handler("welcome", self._handle_welcome)
        self.register_handler("clock_sync", self._handle_clock_sync)
        self.register_handler("rpc_result", self._handle_rpc_result)
        self.register_handler("resource_response", self._handle_resource_response)
        self.register_handler("resource_released", self._handle_resource_released)

    def _receive_messages(self):
        """Background thread to receive messages"""
        buffer = b''
        while self.connected and self.socket:
            try:
                data = self.socket.recv(4096)
                if not data:
                    # Server disconnected
                    break

                # Add to buffer
                buffer += data

                # Process complete messages
                while b'\n' in buffer:
                    # Split on newline
                    message_data, buffer = buffer.split(b'\n', 1)

                    if not message_data.strip():
                        continue

                    try:
                        # Parse the message
                        message = json.loads(message_data.decode('utf-8'))
                        self._process_message(message)
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON: {e}")

            except Exception as e:
                print(f"Error receiving: {e}")
                break

        # If we get here, the connection is closed
        if self.connected:
            self.disconnect()

    def _process_message(self, message):
        """Process a received message"""
        message_type = message.get("type")

        # Update logical clock if message has timestamp
        timestamp = message.get("timestamp")
        if timestamp is not None:
            self.logical_clock.update(timestamp)

        # Call registered handler if exists
        if message_type in self.handlers:
            try:
                self.handlers[message_type](message)
            except Exception as e:
                print(f"Error in handler for {message_type}: {e}")

    def _handle_welcome(self, message):
        """Handle welcome message from server"""
        self.client_id = message.get("client_id")
        print(f"Connected to server. Client ID: {self.client_id}")

    def _handle_clock_sync(self, message):
        """Handle clock synchronization message"""
        # Update our logical clock with the server's timestamp
        timestamp = message.get("timestamp", 0)
        self.logical_clock.update(timestamp)

    def _handle_rpc_result(self, message):
        """Handle RPC call result"""
        call_id = message.get("call_id")
        result = message.get("result")

        # Call the callback if registered
        if call_id in self.rpc_callbacks:
            try:
                self.rpc_callbacks[call_id](result)
            except Exception as e:
                print(f"Error in RPC callback: {e}")
            finally:
                # Remove the callback
                del self.rpc_callbacks[call_id]

    def _handle_resource_response(self, message):
        """Handle resource request response"""
        resource_id = message.get("resource_id")
        granted = message.get("granted", False)

        # Remove from pending
        if resource_id in self.pending_resources:
            self.pending_resources.remove(resource_id)

        # Add to held if granted
        if granted:
            self.held_resources.add(resource_id)

    def _handle_resource_released(self, message):
        """Handle resource release confirmation"""
        resource_id = message.get("resource_id")

        # Ensure it's not in our held resources
        if resource_id in self.held_resources:
            self.held_resources.remove(resource_id)


class DistributedGameUI:
    def __init__(self, root):
        """Initialize the Tkinter UI for distributed client"""
        self.root = root
        self.root.title("Math Battle - Distributed")
        self.root.geometry("600x500")
        self.root.configure(bg=BG_COLOR)

        # Client and game state
        self.client = DistributedMathBattleClient()
        self.room_id = None
        self.answer_var = tk.StringVar()
        self.room_code_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.calc_var = tk.StringVar()
        self.status_var.set("Welcome to Math Battle!")

        # Create fonts
        self.title_font = font.Font(family="Arial", size=24, weight="bold")
        self.heading_font = font.Font(family="Arial", size=16, weight="bold")
        self.text_font = font.Font(family="Arial", size=12)
        self.button_font = font.Font(family="Arial", size=12, weight="bold")

        # Create frames for different screens
        self.menu_frame = tk.Frame(root, bg=BG_COLOR)
        self.create_room_frame = tk.Frame(root, bg=BG_COLOR)
        self.join_room_frame = tk.Frame(root, bg=BG_COLOR)
        self.waiting_frame = tk.Frame(root, bg=BG_COLOR)
        self.playing_frame = tk.Frame(root, bg=BG_COLOR)
        self.game_over_frame = tk.Frame(root, bg=BG_COLOR)
        self.stats_frame = tk.Frame(root, bg=BG_COLOR)

        # Create UI elements for each frame
        self._create_menu_ui()
        self._create_create_room_ui()
        self._create_join_room_ui()
        self._create_waiting_ui()
        self._create_playing_ui()
        self._create_game_over_ui()
        self._create_stats_ui()

        # Status bar at the bottom
        self.status_label = tk.Label(
            root,
            textvariable=self.status_var,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            font=self.text_font,
            pady=10
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        # Clock display
        self.clock_frame = tk.Frame(root, bg=BG_COLOR)
        self.clock_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.clock_label = tk.Label(
            self.clock_frame,
            text="Logical Clock: 0",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            font=self.text_font,
            pady=5
        )
        self.clock_label.pack(side=tk.RIGHT, padx=10)

        # Update clock display periodically
        self._update_clock_display()

        # Register message handlers
        self.client.register_handler("create_room", self._handle_create_room)
        self.client.register_handler("join_room", self._handle_join_room)
        self.client.register_handler("game_start", self._handle_game_start)
        self.client.register_handler("question", self._handle_question)
        self.client.register_handler("answer", self._handle_answer)
        self.client.register_handler("game_over", self._handle_game_over)

        # Start with the menu screen
        self._show_frame(self.menu_frame)

        # Connect to server
        if not self.client.connect():
            self._show_status("Failed to connect to server", ERROR_COLOR)

    def _create_menu_ui(self):
        """Create UI elements for the menu screen"""
        # Title
        title_label = tk.Label(
            self.menu_frame,
            text="MATH BATTLE",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=20
        )
        title_label.pack(pady=20)

        # Description
        desc_label = tk.Label(
            self.menu_frame,
            text="Distributed Math Quiz Game",
            font=self.heading_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        desc_label.pack(pady=10)

        # Create Room button
        create_btn = tk.Button(
            self.menu_frame,
            text="Create Room",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=lambda: self._show_frame(self.create_room_frame)
        )
        create_btn.pack(pady=10)

        # Join Room button
        join_btn = tk.Button(
            self.menu_frame,
            text="Join Room",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=lambda: self._show_frame(self.join_room_frame)
        )
        join_btn.pack(pady=10)

        # View Stats button
        stats_btn = tk.Button(
            self.menu_frame,
            text="View Stats",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=self._view_stats_action
        )
        stats_btn.pack(pady=10)

        # Quit button
        quit_btn = tk.Button(
            self.menu_frame,
            text="Quit",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=self.root.destroy
        )
        quit_btn.pack(pady=10)

    def _create_create_room_ui(self):
        """Create UI elements for the create room screen"""
        # Title
        title_label = tk.Label(
            self.create_room_frame,
            text="CREATE ROOM",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=20
        )
        title_label.pack(pady=20)

        # Instructions
        instructions = tk.Label(
            self.create_room_frame,
            text="Click 'Create' to create a new game room",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        instructions.pack(pady=20)

        # Create button
        create_btn = tk.Button(
            self.create_room_frame,
            text="Create",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=self._create_room_action
        )
        create_btn.pack(pady=10)

        # Back button
        back_btn = tk.Button(
            self.create_room_frame,
            text="Back",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=lambda: self._show_frame(self.menu_frame)
        )
        back_btn.pack(pady=10)

    def _create_join_room_ui(self):
        """Create UI elements for the join room screen"""
        # Title
        title_label = tk.Label(
            self.join_room_frame,
            text="JOIN ROOM",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=20
        )
        title_label.pack(pady=20)

        # Instructions
        instructions = tk.Label(
            self.join_room_frame,
            text="Enter the room code and click 'Join'",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        instructions.pack(pady=10)

        # Room code entry
        entry_frame = tk.Frame(self.join_room_frame, bg=BG_COLOR)
        entry_frame.pack(pady=10)

        room_code_label = tk.Label(
            entry_frame,
            text="Room Code:",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        room_code_label.pack(side=tk.LEFT, padx=5)

        room_code_entry = tk.Entry(
            entry_frame,
            textvariable=self.room_code_var,
            font=self.text_font,
            width=10
        )
        room_code_entry.pack(side=tk.LEFT, padx=5)

        # Join button
        join_btn = tk.Button(
            self.join_room_frame,
            text="Join",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=self._join_room_action
        )
        join_btn.pack(pady=10)

        # Back button
        back_btn = tk.Button(
            self.join_room_frame,
            text="Back",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=lambda: self._show_frame(self.menu_frame)
        )
        back_btn.pack(pady=10)

    def _create_waiting_ui(self):
        """Create UI elements for the waiting screen"""
        # Title
        title_label = tk.Label(
            self.waiting_frame,
            text="WAITING FOR PLAYER",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=20
        )
        title_label.pack(pady=20)

        # Room code display
        self.room_code_label = tk.Label(
            self.waiting_frame,
            text="Room Code: ",
            font=self.heading_font,
            bg=BG_COLOR,
            fg=HIGHLIGHT_COLOR,
            pady=10
        )
        self.room_code_label.pack(pady=20)

        # Waiting message
        self.waiting_message = tk.Label(
            self.waiting_frame,
            text="Waiting",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=10
        )
        self.waiting_message.pack(pady=20)

        # Show dots animation when frame is visible
        self.waiting_frame.bind("<Visibility>", lambda e: self._update_waiting_dots())

    def _create_playing_ui(self):
        """Create UI elements for the playing screen"""
        # Title
        title_label = tk.Label(
            self.playing_frame,
            text="MATH BATTLE",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=10
        )
        title_label.pack(pady=10)

        # Question number
        self.question_number_label = tk.Label(
            self.playing_frame,
            text="Question 0 of 0",
            font=self.heading_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=5
        )
        self.question_number_label.pack(pady=5)

        # Question text
        self.question_label = tk.Label(
            self.playing_frame,
            text="",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=10
        )
        self.question_label.pack(pady=20)

        # Answer entry
        entry_frame = tk.Frame(self.playing_frame, bg=BG_COLOR)
        entry_frame.pack(pady=10)

        answer_label = tk.Label(
            entry_frame,
            text="Answer:",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        answer_label.pack(side=tk.LEFT, padx=5)

        answer_entry = tk.Entry(
            entry_frame,
            textvariable=self.answer_var,
            font=self.text_font,
            width=10
        )
        answer_entry.pack(side=tk.LEFT, padx=5)

        # Submit button
        submit_btn = tk.Button(
            self.playing_frame,
            text="Submit",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=self._submit_answer_action
        )
        submit_btn.pack(pady=10)

        # Calculator section (uses RPC)
        calc_frame = tk.Frame(self.playing_frame, bg=BG_COLOR)
        calc_frame.pack(pady=10)

        calc_label = tk.Label(
            calc_frame,
            text="Calculator:",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        calc_label.pack(side=tk.LEFT, padx=5)

        calc_entry = tk.Entry(
            calc_frame,
            textvariable=self.calc_var,
            font=self.text_font,
            width=15
        )
        calc_entry.pack(side=tk.LEFT, padx=5)

        calc_btn = tk.Button(
            calc_frame,
            text="Calculate",
            font=self.text_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            command=self._calculate_action
        )
        calc_btn.pack(side=tk.LEFT, padx=5)

    def _create_game_over_ui(self):
        """Create UI elements for the game over screen"""
        # Title
        title_label = tk.Label(
            self.game_over_frame,
            text="GAME OVER",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=20
        )
        title_label.pack(pady=20)

        # Results frame
        self.results_frame = tk.Frame(self.game_over_frame, bg=BG_COLOR)
        self.results_frame.pack(pady=20)

        # Back to menu button
        menu_btn = tk.Button(
            self.game_over_frame,
            text="Back to Menu",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=lambda: self._show_frame(self.menu_frame)
        )
        menu_btn.pack(pady=10)

    def _create_stats_ui(self):
        """Create UI elements for the stats screen"""
        # Title
        title_label = tk.Label(
            self.stats_frame,
            text="PLAYER STATISTICS",
            font=self.title_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            pady=20
        )
        title_label.pack(pady=20)

        # Stats content
        self.stats_content = tk.Frame(self.stats_frame, bg=BG_COLOR)
        self.stats_content.pack(pady=20, fill=tk.BOTH, expand=True)

        # Loading message
        self.stats_loading = tk.Label(
            self.stats_content,
            text="Loading statistics...",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        self.stats_loading.pack(pady=20)

        # Back button
        back_btn = tk.Button(
            self.stats_frame,
            text="Back",
            font=self.button_font,
            bg=BUTTON_COLOR,
            fg=BG_COLOR,
            padx=20,
            pady=10,
            command=lambda: self._show_frame(self.menu_frame)
        )
        back_btn.pack(pady=10)

    def _show_frame(self, frame):
        """Show a specific frame and hide others"""
        for f in [self.menu_frame, self.create_room_frame, self.join_room_frame,
                  self.waiting_frame, self.playing_frame, self.game_over_frame,
                  self.stats_frame]:
            f.pack_forget()

        frame.pack(fill=tk.BOTH, expand=True)

    def _show_status(self, message, color=TEXT_COLOR):
        """Show a status message"""
        self.status_var.set(message)
        self.status_label.config(fg=color)

    def _update_waiting_dots(self):
        """Update the waiting dots animation"""
        if self.waiting_frame.winfo_ismapped():
            current_text = self.waiting_message.cget("text")
            base_text = "Waiting"

            if current_text == base_text + "...":
                new_text = base_text
            else:
                new_text = current_text + "."

            self.waiting_message.config(text=new_text)
            self.waiting_frame.after(500, self._update_waiting_dots)

    def _update_clock_display(self):
        """Update the logical clock display"""
        self.clock_label.config(text=f"Logical Clock: {self.client.logical_clock.get_time()}")
        self.root.after(1000, self._update_clock_display)

    def _create_room_action(self):
        """Create a new game room"""
        # FIXED: Directly create a room without resource management
        self._show_status("Creating room...", HIGHLIGHT_COLOR)
        self.client.create_room()

    def _join_room_action(self):
        """Join an existing room"""
        room_code = self.room_code_var.get().strip().upper()
        if not room_code:
            self._show_status("Please enter a room code", ERROR_COLOR)
            return

        self.client.join_room(room_code)

    def _submit_answer_action(self):
        """Submit an answer to the current question"""
        if not self.client.current_question or not self.room_id:
            return

        answer = self.answer_var.get().strip()
        if not answer:
            self._show_status("Please enter an answer", ERROR_COLOR)
            return

        self.client.submit_answer(self.room_id, answer)
        self.answer_var.set("")  # Clear the answer field
        self.question_label.config(text="Waiting for next question...")

    def _calculate_action(self):
        """Use RPC to calculate an expression"""
        expression = self.calc_var.get().strip()
        if not expression:
            self._show_status("Please enter an expression", ERROR_COLOR)
            return

        # Make an RPC call to calculate
        self.client.rpc_call(
            "calculate_expression",
            [expression],
            self._handle_calculate_result
        )

        self._show_status("Calculating...", HIGHLIGHT_COLOR)

    def _view_stats_action(self):
        """View statistics via RPC"""
        self._show_frame(self.stats_frame)

        # Clear previous stats
        for widget in self.stats_content.winfo_children():
            widget.destroy()

        # Show loading message
        self.stats_loading = tk.Label(
            self.stats_content,
            text="Loading statistics...",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        )
        self.stats_loading.pack(pady=20)

        # Get leaderboard
        self.client.rpc_call(
            "get_leaderboard",
            [5],  # Get top 5
            self._handle_leaderboard_result
        )

        # Also get personal stats
        if self.client.client_id:
            self.client.rpc_call(
                "get_player_stats",
                [self.client.client_id],
                self._handle_player_stats_result
            )

    def _handle_create_room(self, message):
        """Handle create room response"""
        success = message.get("success", False)

        if success:
            self.room_id = message.get("room_id")
            self.room_code_label.config(text=f"Room Code: {self.room_id}")
            self._show_frame(self.waiting_frame)
            self._show_status(f"Room created! Code: {self.room_id}", SUCCESS_COLOR)
        else:
            error_msg = message.get("message", "Failed to create room")
            self._show_status(error_msg, ERROR_COLOR)

    def _handle_join_room(self, message):
        """Handle join room response"""
        success = message.get("success", False)

        if success:
            self.room_id = message.get("room_id")
            self.room_code_label.config(text=f"Room Code: {self.room_id}")
            self._show_frame(self.waiting_frame)
            self._show_status(f"Joined room {self.room_id}!", SUCCESS_COLOR)
        else:
            error_msg = message.get("message", "Failed to join room")
            self._show_status(error_msg, ERROR_COLOR)

    def _handle_game_start(self, message):
        """Handle game start notification"""
        self.room_id = message.get("room_id")
        self._show_frame(self.playing_frame)
        self._show_status("Game starting!", SUCCESS_COLOR)

    def _handle_question(self, message):
        """Handle new question"""
        self.client.current_question = message.get("question_text")
        self.client.question_number = message.get("question_number", 0)
        self.client.total_questions = message.get("total_questions", 0)

        self.question_label.config(text=self.client.current_question)
        self.question_number_label.config(
            text=f"Question {self.client.question_number} of {self.client.total_questions}"
        )
        self._show_frame(self.playing_frame)

    def _handle_answer(self, message):
        """Handle answer response"""
        correct = message.get("correct", False)
        correct_answer = message.get("correct_answer", "")

        if correct:
            self._show_status("Correct!", SUCCESS_COLOR)
        else:
            self._show_status(f"Wrong! Correct answer: {correct_answer}", ERROR_COLOR)

    def _handle_game_over(self, message):
        """Handle game over notification"""
        # Clear previous results
        for widget in self.results_frame.winfo_children():
            widget.destroy()

        # Process results
        results = message.get("results", [])
        winner = message.get("winner")

        # Add title
        result_title = tk.Label(
            self.results_frame,
            text="GAME RESULTS",
            font=self.heading_font,
            bg=BG_COLOR,
            fg=HIGHLIGHT_COLOR,
            pady=10
        )
        result_title.pack()

        # Add each player's score
        for result in results:
            player_id = result.get("player_id", "")
            score = result.get("score", 0)
            is_winner = result.get("is_winner", False)

            # Format display name (highlight current player)
            display_name = "You" if player_id == self.client.client_id else f"Opponent"
            if is_winner:
                display_name += " (Winner!)"

            # Set color based on win status
            color = SUCCESS_COLOR if is_winner else TEXT_COLOR

            # Create label for this player
            result_label = tk.Label(
                self.results_frame,
                text=f"{display_name}: {score} points",
                font=self.text_font,
                bg=BG_COLOR,
                fg=color,
                pady=5
            )
            result_label.pack()

        # Show game over frame
        self._show_frame(self.game_over_frame)

        # Show status
        if winner == self.client.client_id:
            self._show_status("Game over! You won!", SUCCESS_COLOR)
        else:
            self._show_status("Game over! You lost.", TEXT_COLOR)

    def _handle_calculate_result(self, result):
        """Handle calculation result from RPC"""
        if result.get("status") == "error":
            self._show_status(f"Calculation error: {result.get('message')}", ERROR_COLOR)
        else:
            calc_result = result.get("result")
            self.calc_var.set("")
            self.answer_var.set(str(calc_result))
            self._show_status(f"Calculation result: {calc_result}", SUCCESS_COLOR)

    def _handle_leaderboard_result(self, result):
        """Handle leaderboard result from RPC"""
        leaderboard = result.get("leaderboard", [])

        # Create section for leaderboard
        leaderboard_frame = tk.Frame(self.stats_content, bg=BG_COLOR)
        leaderboard_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        # Title
        title = tk.Label(
            leaderboard_frame,
            text="LEADERBOARD",
            font=self.heading_font,
            bg=BG_COLOR,
            fg=HIGHLIGHT_COLOR
        )
        title.pack(pady=5)

        # Create table header
        header_frame = tk.Frame(leaderboard_frame, bg=BG_COLOR)
        header_frame.pack(fill=tk.X)

        tk.Label(
            header_frame,
            text="Rank",
            width=5,
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        ).grid(row=0, column=0, padx=5, pady=5)

        tk.Label(
            header_frame,
            text="Player",
            width=15,
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        ).grid(row=0, column=1, padx=5, pady=5)

        tk.Label(
            header_frame,
            text="Wins",
            width=5,
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR
        ).grid(row=0, column=2, padx=5, pady=5)

        # Add each entry
        for i, entry in enumerate(leaderboard):
            entry_frame = tk.Frame(leaderboard_frame, bg=BG_COLOR)
            entry_frame.pack(fill=tk.X)

            # Determine if this is the current player
            is_current = entry.get("player_id") == self.client.client_id
            color = HIGHLIGHT_COLOR if is_current else TEXT_COLOR

            # Format display name
            display_name = "You" if is_current else f"Player {i+1}"

            tk.Label(
                entry_frame,
                text=str(i+1),
                width=5,
                font=self.text_font,
                bg=BG_COLOR,
                fg=color
            ).grid(row=0, column=0, padx=5, pady=2)

            tk.Label(
                entry_frame,
                text=display_name,
                width=15,
                font=self.text_font,
                bg=BG_COLOR,
                fg=color
            ).grid(row=0, column=1, padx=5, pady=2)

            tk.Label(
                entry_frame,
                text=str(entry.get("wins", 0)),
                width=5,
                font=self.text_font,
                bg=BG_COLOR,
                fg=color
            ).grid(row=0, column=2, padx=5, pady=2)

    def _handle_player_stats_result(self, result):
        """Handle player stats result from RPC"""
        # Remove loading message
        for widget in self.stats_content.winfo_children():
            if widget == self.stats_loading:
                widget.destroy()

        stats = result.get("stats", {})

        # Create section for personal stats
        stats_frame = tk.Frame(self.stats_content, bg=BG_COLOR)
        stats_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        # Title
        title = tk.Label(
            stats_frame,
            text="YOUR STATISTICS",
            font=self.heading_font,
            bg=BG_COLOR,
            fg=HIGHLIGHT_COLOR
        )
        title.pack(pady=5)

        # Create stats display
        stats_grid = tk.Frame(stats_frame, bg=BG_COLOR)
        stats_grid.pack()

        # Games played
        tk.Label(
            stats_grid,
            text="Games played:",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=10, pady=2)

        tk.Label(
            stats_grid,
            text=str(stats.get("games", 0)),
            font=self.text_font,
            bg=BG_COLOR,
            fg=HIGHLIGHT_COLOR
        ).grid(row=0, column=1, padx=10, pady=2)

        # Wins
        tk.Label(
            stats_grid,
            text="Wins:",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            anchor="w"
        ).grid(row=1, column=0, sticky="w", padx=10, pady=2)

        tk.Label(
            stats_grid,
            text=str(stats.get("wins", 0)),
            font=self.text_font,
            bg=BG_COLOR,
            fg=SUCCESS_COLOR
        ).grid(row=1, column=1, padx=10, pady=2)

        # Losses
        tk.Label(
            stats_grid,
            text="Losses:",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            anchor="w"
        ).grid(row=2, column=0, sticky="w", padx=10, pady=2)

        tk.Label(
            stats_grid,
            text=str(stats.get("losses", 0)),
            font=self.text_font,
            bg=BG_COLOR,
            fg=ERROR_COLOR
        ).grid(row=2, column=1, padx=10, pady=2)

        # Win rate
        win_rate = 0
        if stats.get("games", 0) > 0:
            win_rate = (stats.get("wins", 0) / stats.get("games", 0)) * 100

        tk.Label(
            stats_grid,
            text="Win rate:",
            font=self.text_font,
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            anchor="w"
        ).grid(row=3, column=0, sticky="w", padx=10, pady=2)

        tk.Label(
            stats_grid,
            text=f"{win_rate:.1f}%",
            font=self.text_font,
            bg=BG_COLOR,
            fg=HIGHLIGHT_COLOR
        ).grid(row=3, column=1, padx=10, pady=2)


def main():
    """Main entry point"""
    root = tk.Tk()
    app = DistributedGameUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()