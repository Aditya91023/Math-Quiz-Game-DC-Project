Math Battle - Distributed Multiplayer Game
🧠 Project Overview
Math Battle is a distributed client-server multiplayer game that tests players' math skills in real-time. Players create or join game rooms, solve math questions, and compete head-to-head. The project serves as a practical implementation of distributed systems concepts like socket communication, RPC, logical clocks, resource management, mutual exclusion, and multi-node task scheduling.

📁 File Structure
math_battle/
├── distributed_client.py       # Client application with Tkinter UI
├── distributed_components.py   # Core distributed system components
├── distributed_server.py       # Server application with game logic
├── run_math_battle.py          # Launcher for different running modes
├── simple_standalone.py        # Single-process version for testing
└── second_client.py            # Simplified client for second player
⚙️ Core Components
1. distributed_components.py
Contains the fundamental distributed system features:

LogicalClock: Lamport's logical clock for event ordering
ResourceManager: Shared resource management and deadlock prevention
MutualExclusionManager: Ricart-Agrawala mutual exclusion algorithm
MessageRouter: Message passing between nodes with simulated delays
RPCManager: Handles RPC logic for client-server calls
TaskScheduler: Distributes tasks across server nodes
2. distributed_server.py
Manages multiplayer game logic:

GameManager: Handles rooms and player tracking
QuestionGenerator: Creates math problems
StatsManager: Records player performance
DistributedServer: Brings everything together with networking and game flow
3. distributed_client.py
Provides the interactive frontend and network client:

LocalClock: Maintains the client’s logical time
DistributedMathBattleClient: Handles socket communication and RPC
DistributedGameUI: Tkinter-based interface for room joining, gameplay, and stats
4. run_math_battle.py
Provides a launcher interface:

LauncherApp: Tkinter-based GUI launcher
run_server(): Starts only the server
run_client(): Starts only the client
run_standalone(): Starts both server and client in one process
🌐 Distributed System Features
✔ Socket Communication
Uses TCP sockets for reliable client-server communication
JSON-based messages with newline delimiters
✔ Remote Procedure Call (RPC)
Clients remotely execute server-side functions
Example: expression evaluation, fetching player stats
✔ Multiple Nodes with Logical Clocks
Server spawns multiple "nodes", each with its own logical clock
Timestamps used for causal consistency
✔ Random Message Passing
MessageRouter simulates random delays
Ensures out-of-order message testing and event ordering via timestamps
✔ Resource Management
Prevents conflicts through locking and request queuing
Includes deadlock prevention mechanism
✔ Mutual Exclusion Algorithm
Implements Ricart-Agrawala algorithm
Manages critical sections (e.g., resource access)
✔ Multi-Node Task Scheduling
Distributes tasks among threads (nodes)
Ensures scalable handling of client actions
🕹 Game Features
🎮 Room Management
Create room with unique 6-character code
Join existing rooms using code
Waiting screen for host until opponent joins
❓ Gameplay
Answer 5 math questions (easy to medium)
Real-time feedback on correctness
Score-based winner declaration
🧮 Player Tools
In-game calculator via RPC
Stats screen for player history and leaderboard
🚀 Running the Game
🛠 Prerequisites
Python 3.6+
Built-in modules: socket, threading, json, uuid, tkinter, etc.
✅ Option 1: Using the Launcher
python run_math_battle.py
Choose from:

Start Server
Start Client
Start Standalone Mode
✅ Option 2: Run Separately (Manual)
# In one terminal
python distributed_server.py --host 0.0.0.0 --port 5555 --nodes 3

# In another terminal
python distributed_client.py
✅ Option 3: Standalone Mode
python simple_standalone.py
Runs both server and client in one process — great for local testing.

🔄 Game Flow
Launch the Game – Use launcher or manual script
Main Menu – Choose to create/join room or view stats
Create Room – Share code with second player
Wait – Host waits until opponent joins
Play Game – Answer 5 questions competitively
View Results – See scores and winner
Return to Menu – Replay or exit
🛠 Troubleshooting
Connection Issues: Ensure the server is up before starting the client
Port In Use: Use --port to select a different port
UI Problems: Use standalone mode for better Tkinter compatibility
💡 Implementation Notes
TCP socket-based client-server architecture
Retry logic improves connection resilience
Logical clocks maintain event order across distributed nodes
Room creation logic avoids deadlocks by bypassing mutual exclusion
Multiple threads simulate distributed servers
