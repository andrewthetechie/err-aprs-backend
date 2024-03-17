from aprs_backend.threads import ErrbotAPRSDThread
from aprs_backend.utils.log import log
from queue import Queue
from aprs_backend.clients import ErrbotAPRSISClient
from aprs_backend.clients import ErrbotKISSClient
from aprs_backend.packets import ErrbotPacketList
from aprs_backend.packets import ErrbotPacketTrack
from aprs_backend.packets import ErrbotPacketsSeenList
import time
from datetime import datetime
from aprs_backend.utils import strfdelta
from aprs_backend.threads import ErrbotAPRSDThreadList
import tracemalloc

class KeepAliveThread(ErrbotAPRSDThread):
    def __init__(self, packet_queue: Queue, 
                 send_queue: Queue, 
                 aprs_client: ErrbotAPRSISClient | ErrbotKISSClient,
                 packet_list: ErrbotPacketList,
                 packet_tracker: ErrbotPacketTrack,
                 seen_list: ErrbotPacketsSeenList,
                 thread_list: ErrbotAPRSDThreadList,
                 keep_alive_freq: int = 240, # .25 second sleep, should run ~ every 60 seconds
                 aprs_keep_alive_mins: int = 3 # if we haven't sent or received a message in 3 minutes, reset the connection
                 ):
        super().__init__("RX_MSG")
        self.packet_queue = packet_queue
        self.send_queue = send_queue
        self._client = aprs_client
        self._packet_list = packet_list
        self._packet_tracker = packet_tracker
        self._seen_list = seen_list
        self._thread_list = thread_list
        self._loop_counter: int = 1
        self._keep_alive_freq = keep_alive_freq
        self.started_time = datetime.now()
        self._aprs_keep_alive_seconds = aprs_keep_alive_mins * 60

    def loop(self):
        if self._loop_counter % self._keep_alive_freq == 0:
            uptime = datetime.now() - self.started_time
            curr_mem, peak_mem = tracemalloc.get_traced_memory()
            stats = f"Uptime {strfdelta(uptime)} RX: {self.packet_list.total_rx()} "
            stats += f"TX: {self.packet_list.total_tx()} Tracked: {len(self.packet_tracker)}"
            stats += f"Threads: {len(self._thread_list)} Mem: {curr_mem} PeakMem: {peak_mem}"
            log.info(stats)
            thread_out = []
            thread_info = {}
            for thread in self.thread_list.threads_list:
                alive = thread.is_alive()
                age = thread.loop_age()
                key = thread.__class__.__name__
                thread_out.append(f"{key}:{alive}:{age}")
                if key not in thread_info:
                    thread_info[key] = {}
                thread_info[key]["alive"] = alive
                thread_info[key]["age"] = age
                if not alive:
                    log.error(f"Thread {thread}")
            log.info(",".join(thread_out))
            # if the client isn't alive, and this isn't our first time through the loop, reset the client
            # This prevents the KeepALive thread from starting before the client has a chance to start up
            if not self._client.is_configured() and self._loop_counter > 1:
                log.error("Client %s is not alive. Resetting", self._client.__class__.__name__)
                self._client.reset()
            # See if we should reset the aprs-is client
            # Due to losing a keepalive from them
            else:
                if self._packet_list.secs_since_last_rx > self._aprs_keep_alive_seconds and self._packet_list > self._aprs_keep_alive_seconds:
                    log.error("No keepalive from aprs in %d seconds. Resetting connection", self._aprs_keep_alive_seconds)
                    self._client.reset()
            pass
        self._loop_counter += 1
        time.sleep(0.25)
        return True
