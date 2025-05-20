class PriorityQueue:
    def __init__ (self, numberOfNodes):
        self.queue = [None] * numberOfNodes
        self.maxLength = numberOfNodes


    def push(self, index, source):
        if not self.queue:
            self.queue.insert(index,source)
        else:
            for i in range(0, len(self.queue)):
                if i == index:
                    self.queue[index] = source
                    
    def pop(self):
        minPriority = float("inf")
        if not self.queue:
            print("Error, no values to pop")
        else:
            for i in range(0,len(self.queue)):
                if self.queue[i] != None:
                    if i < minPriority:
                        minPriority = i
        value = self.queue[minPriority]
        self.queue[minPriority] = None
        return value
    


priorityQueue = PriorityQueue(9)
priorityQueue.push(0, "My")
priorityQueue.push(2, "is")
priorityQueue.push(1, "name")

print(priorityQueue.queue)

print(priorityQueue.pop())
print(priorityQueue.pop())
print(priorityQueue.pop())

print(priorityQueue.queue)


