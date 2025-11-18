import time
from enum import Enum


class PositionType(Enum):
    UNKNOWN = 1
    CALCULATED = 2
    CONFIRMED = 3


class TravelStatus(Enum):
    DIRECTION_UP = 1
    DIRECTION_DOWN = 2
    STOPPED = 3


class TravelCalculator:

    def __init__(self, travel_time_down, travel_time_up):
        self.position_type = PositionType.UNKNOWN
        self.last_known_position = 0
        self.travel_to_position = 0
        self.travel_started_time = 0
        self.travel_time_down = travel_time_down
        self.travel_time_up = travel_time_up
        self.travel_direction = TravelStatus.STOPPED
        self.position_closed = 0
        self.position_open = 100
        self.time_set_from_outside = None

    def start_travel(self, position):
        self.travel_to_position = position
        self.travel_started_time = self.current_time()
        self.last_known_position = self.current_position()
        if position < self.current_position():
            self.travel_direction = TravelStatus.DIRECTION_DOWN
        elif position > self.current_position():
            self.travel_direction = TravelStatus.DIRECTION_UP
        else:
            self.travel_direction = TravelStatus.STOPPED

    def start_travel_up(self):
        self.travel_to_position = self.position_open
        self.travel_started_time = self.current_time()
        self.last_known_position = self.current_position()
        self.travel_direction = TravelStatus.DIRECTION_UP

    def start_travel_down(self):
        self.travel_to_position = self.position_closed
        self.travel_started_time = self.current_time()
        self.last_known_position = self.current_position()
        self.travel_direction = TravelStatus.DIRECTION_DOWN

    def stop(self):
        self.last_known_position = self.current_position()
        self.travel_direction = TravelStatus.STOPPED
        self.travel_started_time = 0
        self.travel_to_position = self.last_known_position
    
    # UPDATED: Do not stop automatically here; let external logic (auto_stop_if_necessary) handle stop & side-effects.
    def update_position(self):
        """Called periodically to allow external logic to detect arrival; no direct state mutation here."""
        # Intentionally left minimal. Keeping method for backward compatibility.
        return

    def set_position(self, position):
        self.last_known_position = position
        self.travel_to_position = position
        self.travel_direction = TravelStatus.STOPPED
        self.travel_started_time = 0

    def current_position(self):
        if self.travel_direction == TravelStatus.STOPPED:
            return self.last_known_position
        
        relative_position = self.travel_to_position - self.last_known_position
        
        if self.last_known_position == self.travel_to_position:
            return self.last_known_position

        travel_time = self._calculate_travel_time(relative_position)
        
        if travel_time == 0:
            return self.travel_to_position

        progress = (self.current_time() - self.travel_started_time) / travel_time
        
        if progress >= 1:
            return self.travel_to_position
        
        position = self.last_known_position + relative_position * progress
        return int(position)

    def is_traveling(self):
        return self.travel_direction != TravelStatus.STOPPED

    def is_closed(self):
        return self.current_position() == self.position_closed

    def position_reached(self):
        return self.current_position() == self.travel_to_position and self.is_traveling()

    def calculate_position(self):
        if not self.is_traveling():
            return self.current_position()

        if self.position_reached():
            return self.last_known_position
        
        travel_time_full = self.travel_time_up if self.travel_direction == TravelStatus.DIRECTION_UP else self.travel_time_down
        travel_range = self.position_open - self.position_closed
        
        travel_duration = self.current_time() - self.travel_started_time
        
        if self.travel_direction == TravelStatus.DIRECTION_UP:
            position_change = (travel_duration / travel_time_full) * travel_range
            position = self.last_known_position + position_change
            if position > self.travel_to_position:
                return self.travel_to_position
            return int(position)
        else:
            position_change = (travel_duration / travel_time_full) * travel_range
            position = self.last_known_position - position_change
            if position < self.travel_to_position:
                return self.travel_to_position
            return int(position)

    def _calculate_travel_time(self, relative_position):
        travel_direction = \
            TravelStatus.DIRECTION_UP \
            if relative_position > 0 else \
            TravelStatus.DIRECTION_DOWN
        travel_time_full = \
            self.travel_time_up \
            if travel_direction == TravelStatus.DIRECTION_UP else \
            self.travel_time_down
        travel_range = self.position_open - self.position_closed

        return travel_time_full * abs(relative_position) / travel_range

    def current_time(self):
        if self.time_set_from_outside is not None:
            return self.time_set_from_outside
        return time.time()

    def __eq__(self, other):
        return self.__dict__ == other.__dict__