# Console-based interface for Europe Sea Route Pathfinder

from Astar import Grid, AStarPathfinder  

#config

GRID_FILE = r"C:\Users\isaac\OneDrive\Desktop\NEA Project new\NEA-Project-2\Pathfinder Algorithm\Data\FullGridOfEurope.npy"


PORTS = [
    {"name": "Rotterdam",   "coords": (2001, 1950)},
    {"name": "Hamburg",     "coords": (2214, 1895)},
    {"name": "Piraeus",     "coords": (3044, 2918)},
    {"name": "Gibraltar",   "coords": (1298, 2918)},
    {"name": "Valencia",    "coords": (1624, 2835)},
    {"name": "Felixstowe",  "coords": (1842, 1892)},
    {"name": "Genoa",       "coords": (2193, 2511)},
    {"name": "Gdansk",      "coords": (2615, 1723)}
    # add rest later
]

# main program

def print_menu():
    print("\n" + "="*50)
    print("     EUROPE SEA ROUTE PATHFINDER")
    print("="*50)
    print("1. List all available ports")
    print("2. Find route between two ports")
    print("3. Exit")
    print("="*50)


def list_ports():
    print("\nAvailable ports:")
    for i, port in enumerate(PORTS, 1):
        r, c = port["coords"]
        print(f"  {i:2d}. {port['name']:15}  (row {r:4d}, col {c:4d})")


def select_port(prompt: str):
    list_ports()
    while True:
        try:
            choice = int(input(prompt))
            if 1 <= choice <= len(PORTS):
                return PORTS[choice-1]["coords"], PORTS[choice-1]["name"]
            else:
                print(f"Please enter a number between 1 and {len(PORTS)}.")
        except ValueError:
            print("Please enter a valid number.")


def main():
    print("Loading grid... ", end="")
    try:
        grid = Grid(GRID_FILE)
        pathfinder = AStarPathfinder(grid)
        print("Done!")
    except Exception as e:
        print(f"Failed: {e}")
        return

    while True:
        print_menu()
        choice = input("Enter your choice (1-3): ").strip()

        if choice == "1":
            list_ports()

        elif choice == "2":
            print("\nSelect start port:")
            start_coords, start_name = select_port("Start port number: ")

            print("\nSelect goal port:")
            goal_coords, goal_name = select_port("Goal port number: ")

            if start_coords == goal_coords:
                print("Start and goal cannot be the same port.")
                continue

            print(f"\nComputing route: {start_name} → {goal_name} ...")
            path = pathfinder.find_path(start_coords, goal_coords)

            if path:
                print(f"\nSuccess! Found path with {len(path)-1} steps")
                print(f"Start: {start_coords} ({start_name})")
                print(f"Goal:  {goal_coords}  ({goal_name})")
                print(f"Path length: {len(path)} cells")
                print("\nFirst 5 steps:", path[:5])
                print("Last 5 steps :", path[-5:])
            else:
                print("\nNo valid sea route found between these ports.")

        elif choice == "3":
            print("\nThank you for using the Sea Route Pathfinder!")
            break

        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

if __name__ == "__main__":
    main()
