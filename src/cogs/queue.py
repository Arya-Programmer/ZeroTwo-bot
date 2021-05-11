from src.cogs.errors import QueueIsEmpty

history = []


class Queue:
    def __init__(self):
        self._queue = []
        self.position = 0
        self._isQueueLooped = False
        self._isLooped = False

    def add(self, *args):
        self._queue.extend(args)

    def addToFirst(self, *args):
        self._queue.insert(self.position+1, args[0])

    def removeIndex(self, index):
        self._queue.remove(self._queue[index])

    @property
    def firstTrack(self):
        if not self._queue:
            raise QueueIsEmpty

        return self._queue[0]

    def loop(self, loop):
        if not self._queue:
            raise QueueIsEmpty

        self._isLooped = loop

    def queueLoop(self, loop):
        if not self._queue:
            raise QueueIsEmpty

        self._isQueueLooped = loop

    def getNextTrack(self):
        if not self._queue:
            raise QueueIsEmpty

        print(self.position)
        print(self._queue, len(self._queue))

        if not self._isLooped:  # if not looped. Otherwise return itself
            self.position += 1
            # if queue not looped then go to next song if there is one
            if not self._isQueueLooped:
                self._queue = self._queue[self.position:]  # remove the songs before this one
                self.position = 0
            # if queue looped but we got to last song then return the first one again
            elif self.position == len(self._queue):
                self.position = 0
                return self.firstTrack

        try:
            history.append(self._queue[self.position])
        except IndexError:
            raise QueueIsEmpty
        return self._queue[self.position]

    @property
    def queue(self):
        if not self._queue:
            return QueueIsEmpty
        return self._queue

    @property
    def isLooped(self):
        if not self._queue:
            return QueueIsEmpty
        return self._isLooped

    @property
    def isQueueLooped(self):
        if not self._queue:
            return QueueIsEmpty
        return self._isQueueLooped

