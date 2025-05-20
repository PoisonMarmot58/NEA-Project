from heapq import heappop, heapify, heappush

class Graph:
    def __init__(self, graph: dict = {}):
        self.graph = graph

    def add_edge(self, node1, node2, weight):
        if node1 not in self.graph:
            self.graph[node1] = {}
        self.graph[node1][node2]

    def shortest_distances(self, source:str):
        distances = {node: float("inf") for node in self.graph}
        distances[source] = 0

        priority_queue = [(0, source)]
        heapify(priority_queue)

        visited = set()

        while priority_queue:
            current_distance, current_node = heappop(priority_queue)

            if current_node in visited:
                continue
            visited.add(current_node)

            for neighbour, weight in self.graph[current_node].items():
                cumulative_distance = current_distance + weight
                if cumulative_distance < distances[neighbour]:
                    distances[neighbour] = cumulative_distance
                    heappush(priority_queue, (cumulative_distance, neighbour))

        predecessors = {node: None for node in self.graph}
        for node, distance in distances.items():
            for neighbour, weight in self.graph[node].items():
                if distances[neighbour] == distance + weight:
                    predecessors[neighbour] = node
            
        return distances, predecessors
    
    def shortest_path(self, source:str, target:str):
        _, predecessors = self.shortest_distances(source)

        path = []
        current_node = target

        while current_node:
            path.append(current_node)
            current_node = predecessors[current_node]

        path.reverse()
        return path

graph = {
    "A": {"B": 2, "C": 3}, 
    "B": {"A": 2, "C": 3, "E": 9},
    "C": {"A": 3, "B": 3, "F": 1, "G": 6},
    "D": {"G": 1},
    "E": {"B": 9, "G": 4}, 
    "F": {"C": 8},
    "G": {"C": 6, "D": 1, "E": 4}
}

graph = Graph(graph=graph)

print(graph.shortest_path("A", "C"))
