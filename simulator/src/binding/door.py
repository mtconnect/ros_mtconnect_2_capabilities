from response import *


def OpenDoor(parent):
    OpenDoor = Response(parent, parent.adapter, parent.open_door, 'door', 'OPEN', 'UNLATCHED', parent.door_state, rel = True, simulate = True)
    OpenDoor.create_statemachine()
    OpenDoor.superstate.start()
    return OpenDoor

def CloseDoor(parent):
    CloseDoor = Response(parent, parent.adapter, parent.close_door, 'door', 'CLOSED', 'UNLATCHED',parent.door_state, rel = True, simulate = True)
    CloseDoor.create_statemachine()
    CloseDoor.superstate.start()
    return CloseDoor