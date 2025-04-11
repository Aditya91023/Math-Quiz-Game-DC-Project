"""
Distributed system components for Math Battle
"""

import time
import threading
import random
import queue
from typing import Dict, List, Tuple, Set, Any


class LogicalClock:
    """Implements Lamport's logical clock for event ordering in distributed systems"""

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


class ResourceManager:
    """Manages shared resources and detects/prevents deadlocks"""

    def __init__(self):
        """Initialize the resource manager"""
        self.resources = {}  # resource_id -> {owner, waitlist}
        self.client_resources = {}  # client_id -> [resource_ids]
        self.lock = threading.Lock()

    def request_resource(self, client_id: str, resource_id: str) -> bool:
        """Request a resource, returns True if granted"""
        with self.lock:
            # Create resource if it doesn't exist
            if resource_id not in self.resources:
                self.resources[resource_id] = {"owner": None, "waitlist": []}

            # If resource is free, grant it
            if self.resources[resource_id]["owner"] is None:
                self.resources[resource_id]["owner"] = client_id

                # Add to client's resources
                if client_id not in self.client_resources:
                    self.client_resources[client_id] = []
                self.client_resources[client_id].append(resource_id)

                return True

            # Resource is taken, add to waitlist
            if client_id not in self.resources[resource_id]["waitlist"]:
                self.resources[resource_id]["waitlist"].append(client_id)

            # Check for potential deadlocks
            if self._would_cause_deadlock(client_id, resource_id):
                # Remove from waitlist to prevent deadlock
                self.resources[resource_id]["waitlist"].remove(client_id)
                return False

            return False

    def release_resource(self, client_id: str, resource_id: str) -> None:
        """Release a resource"""
        with self.lock:
            if resource_id not in self.resources:
                return

            # Only the owner can release
            if self.resources[resource_id]["owner"] != client_id:
                return

            # Release the resource
            self.resources[resource_id]["owner"] = None

            # Remove from client's resources
            if client_id in self.client_resources and resource_id in self.client_resources[client_id]:
                self.client_resources[client_id].remove(resource_id)

            # Grant to next client in waitlist if any
            if self.resources[resource_id]["waitlist"]:
                next_client = self.resources[resource_id]["waitlist"].pop(0)
                self.resources[resource_id]["owner"] = next_client

                # Add to client's resources
                if next_client not in self.client_resources:
                    self.client_resources[next_client] = []
                self.client_resources[next_client].append(resource_id)

    def release_all_client_resources(self, client_id: str) -> None:
        """Release all resources held by a client (e.g. on disconnect)"""
        with self.lock:
            if client_id not in self.client_resources:
                return

            # Get all resources held by client
            resources_to_release = self.client_resources[client_id].copy()

            # Release each resource
            for resource_id in resources_to_release:
                self.release_resource(client_id, resource_id)

            # Remove client from all waitlists
            for resource_id in self.resources:
                if client_id in self.resources[resource_id]["waitlist"]:
                    self.resources[resource_id]["waitlist"].remove(client_id)

            # Remove client from client_resources
            if client_id in self.client_resources:
                del self.client_resources[client_id]

    def check_deadlocks(self) -> List:
        """Check for potential deadlocks in the system"""
        with self.lock:
            # Build a resource allocation graph
            graph = {}  # client_id -> [client_ids it's waiting for]

            for resource_id, resource in self.resources.items():
                owner = resource["owner"]
                if owner is None:
                    continue

                for waiting_client in resource["waitlist"]:
                    if waiting_client not in graph:
                        graph[waiting_client] = []
                    graph[waiting_client].append(owner)

            # Find cycles in the graph (deadlocks)
            deadlocks = []
            visited = set()

            def dfs(node, path):
                if node in path:
                    # Found a cycle
                    cycle_start = path.index(node)
                    deadlocks.append(path[cycle_start:])
                    return

                if node in visited:
                    return

                visited.add(node)
                path.append(node)

                if node in graph:
                    for neighbor in graph[node]:
                        dfs(neighbor, path.copy())

            # Run DFS from each node
            for client_id in graph:
                dfs(client_id, [])

            return deadlocks

    def _would_cause_deadlock(self, client_id: str, resource_id: str) -> bool:
        """Check if granting a resource to a client would cause a deadlock"""
        # Simple deadlock detection for now
        if client_id not in self.client_resources:
            return False

        # Check if this client is waiting for a resource owned by someone
        # who is waiting for a resource owned by this client
        for other_resource_id in self.resources:
            if other_resource_id == resource_id:
                continue

            if (self.resources[other_resource_id]["owner"] == client_id and
                    self.resources[resource_id]["owner"] in self.resources[other_resource_id]["waitlist"]):
                return True

        return False


class MutualExclusionManager:
    """Implements Ricart-Agrawala algorithm for mutual exclusion"""

    def __init__(self, num_nodes):
        """Initialize the mutual exclusion manager"""
        self.num_nodes = num_nodes
        self.request_queue = []  # [(node_id, timestamp)]
        self.replied_to = set()  # Set of node_ids we've replied to
        self.requesting = False  # Whether we're requesting the critical section
        self.logical_clock = LogicalClock()
        self.lock = threading.Lock()

    def request_access(self, node_id):
        """Request access to critical section for a node"""
        with self.lock:
            self.requesting = True
            timestamp = self.logical_clock.increment()

            # Count replies needed
            replies_needed = self.num_nodes - 1
            if replies_needed == 0:
                # No other nodes, can enter immediately
                return True

            # Send request to all other nodes
            for other_id in range(self.num_nodes):
                if other_id != node_id:
                    # Simulate sending request to other node
                    # In a real system, this would be a network message
                    self._handle_request(other_id, node_id, timestamp)

            # Wait for all replies
            # In a real system, this would wait for actual replies
            # Here we simulate it based on the request queue
            self._process_queue()

            # For simulation purposes, always grant access after processing
            return True

    def _handle_request(self, receiver_id, sender_id, timestamp):
        """Handle a request from another node"""
        with self.lock:
            self.logical_clock.update(timestamp)

            # Determine if we should reply or defer
            if (not self.requesting or
                    timestamp < self.logical_clock.get_time() or
                    (timestamp == self.logical_clock.get_time() and sender_id < receiver_id)):
                # Reply immediately
                self.replied_to.add(sender_id)
            else:
                # Defer reply by adding to queue
                self.request_queue.append((sender_id, timestamp))

    def release_access(self, node_id):
        """Release access to critical section for a node"""
        with self.lock:
            self.requesting = False
            self.replied_to = set()

            # Reply to all deferred requests
            self._process_queue()

    def _process_queue(self):
        """Process the request queue"""
        with self.lock:
            # Sort queue by timestamp and node_id
            self.request_queue.sort(key=lambda x: (x[1], x[0]))

            # Reply to all requests if we're not requesting
            # or to requests with lower timestamps
            if not self.requesting:
                for sender_id, _ in self.request_queue:
                    self.replied_to.add(sender_id)
                self.request_queue = []
            else:
                # Reply to requests with lower priority
                timestamp = self.logical_clock.get_time()
                node_id = -1  # This would be our node_id

                kept = []
                for sender_id, req_timestamp in self.request_queue:
                    if (req_timestamp < timestamp or
                            (req_timestamp == timestamp and sender_id < node_id)):
                        self.replied_to.add(sender_id)
                    else:
                        kept.append((sender_id, req_timestamp))

                self.request_queue = kept


class MessageRouter:
    """Routes messages between nodes in a distributed system"""

    def __init__(self, num_nodes):
        """Initialize the message router"""
        self.num_nodes = num_nodes
        self.message_queues = [queue.Queue() for _ in range(num_nodes)]
        self.logical_clocks = [LogicalClock() for _ in range(num_nodes)]
        self.delays = [[0 for _ in range(num_nodes)] for _ in range(num_nodes)]

    def send_message(self, sender_id, receiver_id, message):
        """Send a message from one node to another"""
        if sender_id < 0 or sender_id >= self.num_nodes or receiver_id < 0 or receiver_id >= self.num_nodes:
            return False

        # Add timestamp to message
        timestamp = self.logical_clocks[sender_id].increment()
        message["timestamp"] = timestamp

        # Get delay for this connection
        delay = self.delays[sender_id][receiver_id]
        if delay == 0:
            # No delay, put message in queue immediately
            self.message_queues[receiver_id].put((sender_id, message))
        else:
            # Simulate network delay
            def delayed_delivery():
                time.sleep(delay / 1000.0)  # Convert ms to seconds
                self.message_queues[receiver_id].put((sender_id, message))

            threading.Thread(target=delayed_delivery, daemon=True).start()

        return True

    def receive_message(self, node_id, timeout=0):
        """Receive a message for a node"""
        if node_id < 0 or node_id >= self.num_nodes:
            return None, None

        try:
            sender_id, message = self.message_queues[node_id].get(timeout=timeout if timeout > 0 else None)

            # Update logical clock
            timestamp = message.get("timestamp", 0)
            self.logical_clocks[node_id].update(timestamp)

            return sender_id, message
        except queue.Empty:
            return None, None

    def set_delay(self, sender_id, receiver_id, delay_ms):
        """Set delay for messages between two nodes"""
        if sender_id < 0 or sender_id >= self.num_nodes or receiver_id < 0 or receiver_id >= self.num_nodes:
            return
        self.delays[sender_id][receiver_id] = delay_ms

    def randomize_delays(self, min_delay=10, max_delay=500):
        """Randomize network delays between all nodes"""
        for i in range(self.num_nodes):
            for j in range(self.num_nodes):
                if i != j:
                    self.delays[i][j] = random.randint(min_delay, max_delay)


class RPCManager:
    """Handles Remote Procedure Call functionality"""

    def __init__(self):
        """Initialize the RPC manager"""
        self.methods = {}  # method_name -> function

    def register_method(self, method_name, method_func):
        """Register a method that can be called remotely"""
        self.methods[method_name] = method_func

    def call(self, method_name, *args, **kwargs):
        """Execute a method call"""
        if method_name not in self.methods:
            return {"status": "error", "message": f"Method {method_name} not found"}

        try:
            result = self.methods[method_name](*args, **kwargs)
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}


class TaskScheduler:
    """Schedules tasks among multiple server nodes"""

    def __init__(self, num_nodes):
        """Initialize the task scheduler"""
        self.num_nodes = num_nodes
        self.task_queues = [queue.Queue() for _ in range(num_nodes)]
        self.lock = threading.Lock()

    def add_task(self, task, node_id=None):
        """Add a task to a specific node or auto-assign"""
        with self.lock:
            if node_id is None:
                # Auto-assign to least loaded node
                node_id = self._get_least_loaded_node()

            if 0 <= node_id < self.num_nodes:
                self.task_queues[node_id].put(task)
                return True
            return False

    def get_task(self, node_id, timeout=0):
        """Get a task for a node"""
        if node_id < 0 or node_id >= self.num_nodes:
            return None

        try:
            return self.task_queues[node_id].get(timeout=timeout if timeout > 0 else None)
        except queue.Empty:
            return None

    def _get_least_loaded_node(self):
        """Get the index of the least loaded node"""
        with self.lock:
            sizes = [self.task_queues[i].qsize() for i in range(self.num_nodes)]
            return sizes.index(min(sizes))