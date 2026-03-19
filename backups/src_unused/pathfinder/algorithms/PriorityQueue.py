"""PriorityQueue module."""

class PriorityQueue:
    def __init__ (self):
        self.queue = []

    def push(self, priority, value):
        self.queue.append((priority, value))
        self.queue.sort(key=lambda x: x[0])

    def pop(self):
        if not self.queue:
            print("Error: Queue is empty.")
            return None
        else:
            priority,value = self.queue.pop(0)
            return value
        
    def is_empty(self):
        return len(self.queue) == 0
    
    def size(self):
        return len(self.queue)
    