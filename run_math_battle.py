"""
Math Battle Launcher

This script provides a menu to launch the Math Battle server and clients
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox


def run_server(num_nodes=3):
    """Run the server with the specified number of nodes"""
    subprocess.Popen([sys.executable, "distributed_server.py", "--nodes", str(num_nodes)])


def run_client():
    """Run a client"""
    subprocess.Popen([sys.executable, "distributed_client.py"])


def run_standalone():
    """Run server and client in one process (for testing)"""
    # Start server in a separate thread
    thread = threading.Thread(target=lambda: run_server(1))
    thread.daemon = True
    thread.start()

    # Wait a moment for server to start
    import time
    time.sleep(1)

    # Start client
    run_client()


class LauncherApp:
    def __init__(self, root):
        """Initialize the launcher UI"""
        self.root = root
        self.root.title("Math Battle Launcher")
        self.root.geometry("400x350")

        # Main frame
        main_frame = ttk.Frame(root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Math Battle Launcher",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=10)

        # Server options
        server_frame = ttk.LabelFrame(main_frame, text="Server Options", padding=10)
        server_frame.pack(fill=tk.X, pady=10)

        self.nodes_var = tk.IntVar(value=3)
        nodes_label = ttk.Label(server_frame, text="Number of nodes:")
        nodes_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)

        nodes_spinbox = ttk.Spinbox(
            server_frame,
            from_=1,
            to=10,
            textvariable=self.nodes_var,
            width=5
        )
        nodes_spinbox.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=20)

        server_btn = ttk.Button(
            button_frame,
            text="Start Server",
            command=self.start_server
        )
        server_btn.pack(fill=tk.X, pady=5)

        client_btn = ttk.Button(
            button_frame,
            text="Start Client",
            command=self.start_client
        )
        client_btn.pack(fill=tk.X, pady=5)

        standalone_btn = ttk.Button(
            button_frame,
            text="Start Standalone Mode",
            command=self.start_standalone
        )
        standalone_btn.pack(fill=tk.X, pady=5)

        exit_btn = ttk.Button(
            button_frame,
            text="Exit",
            command=root.destroy
        )
        exit_btn.pack(fill=tk.X, pady=5)

        # Status
        self.status_var = tk.StringVar(value="Ready to launch")
        status_label = ttk.Label(
            main_frame,
            textvariable=self.status_var,
            foreground="blue"
        )
        status_label.pack(pady=10)

    def start_server(self):
        """Start the server"""
        num_nodes = self.nodes_var.get()
        self.status_var.set(f"Starting server with {num_nodes} nodes...")
        run_server(num_nodes)
        self.status_var.set(f"Server started with {num_nodes} nodes")

    def start_client(self):
        """Start a client"""
        self.status_var.set("Starting client...")
        run_client()
        self.status_var.set("Client started")

    def start_standalone(self):
        """Start standalone mode"""
        self.status_var.set("Starting standalone mode...")
        run_standalone()
        self.status_var.set("Standalone mode started")


def main():
    """Main entry point"""
    # Check if files exist
    required_files = ["distributed_server.py", "distributed_client.py", "distributed_components.py"]
    missing_files = [f for f in required_files if not os.path.exists(f)]

    if missing_files:
        print(f"Error: Missing files: {', '.join(missing_files)}")
        print("Please make sure all required files are in the current directory.")
        return

    # Create and run launcher
    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()