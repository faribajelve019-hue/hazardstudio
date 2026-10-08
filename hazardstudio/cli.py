import sys


def main():
    args = sys.argv[1:]

    if not args:
        print("HazardStudio CLI")
        print()
        print("Usage:")
        print("  hazardstudio login")
        print("  hazardstudio account")
        print("  hazardstudio tunnel <port>")
        return

    command = args[0]

    if command == "login":
        print("HazardStudio Login")
        print("Coming soon...")

    elif command == "account":
        print("HazardStudio Account")
        print("Not logged in.")

    elif command == "tunnel":
        if len(args) < 2:
            print("Usage:")
            print("  hazardstudio tunnel <port>")
            return

        try:
            port = int(args[1])
        except ValueError:
            print("❌ Invalid port.")
            return

        print(f"Tunnel requested on port {port}")
        print("Tunnel service is not configured yet.")

    else:
        print("❌ Unknown command.")
        print()
        print("Usage:")
        print("  hazardstudio login")
        print("  hazardstudio account")
        print("  hazardstudio tunnel <port>")
