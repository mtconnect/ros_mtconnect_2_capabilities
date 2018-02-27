from transitions.extensions import HierarchicalMachine as Machine
from transitions.extensions.nesting import NestedState
from threading import Timer, Thread
import functools, time, copy

import subTask

#will be included under assets!?
class interface(object):

    def __init__(self, value = None):
        self.value = value

class collaborator(object):

    def __init__(self, parent, interface, collaborator_name):

        class statemachineModel(object):

            def __init__(self, parent, interface, collaborator_name):

                self.interface = interface
                self.parent = parent
                self.collaborator_name = collaborator_name
                self.task_name = None
                self.id = collaborator_name #which one?
                self.subTask = {}
                self.currentSubTask = str()
                
            def INACTIVE(self): 
                self.interface.value = 'INACTIVE'
                
                self.parent.adapter.begin_gather()
                self.binding_state1.set_value("INACTIVE")
                self.parent.adapter.complete_gather()
                
                self.task_created()

            def PREPARING(self):
                self.interface.value = 'PREPARING'
                self.parent.binding_state = 'PREPARING'
                
                self.parent.adapter.begin_gather()
                self.binding_state1.set_value("PREPARING")
                self.parent.adapter.complete_gather()
                
            def committed(self, value, code, text):
                if self.collaborator_name in value['coordinator'][text]['SubTask']:
                    self.subTask[value['coordinator'][text]['SubTask'][self.collaborator_name][0]] = subTask.subTask(parent = self , interface = interface, master_task_uuid = code, collaborators = value['coordinator'][text]['SubTask'][self.collaborator_name][2])
                    self.subTask[value['coordinator'][text]['SubTask'][self.collaborator_name][0]].create_statemachine()
                    self.subTask[value['coordinator'][text]['SubTask'][self.collaborator_name][0]].superstate.create()
                    self.currentSubTask = copy.deepcopy(value['coordinator'][text]['SubTask'][self.collaborator_name][0])

                    for key, val in self.parent.master_tasks[code]['collaborators'].iteritems():

                        if self.task_name in val['SubTask'].keys():
                            for i,x in enumerate(val['SubTask'][self.task_name]):
                                
                                self.subTask[x[0]] = subTask.subTask(parent = self , interface = interface, master_task_uuid = code, collaborators = x[4])
                                self.subTask[x[0]].create_statemachine()
                                self.subTask[x[0]].superstate.create()
                                self.currentSubTask = copy.deepcopy(x[0])

                                while self.subTask[self.currentSubTask].superstate.state != 'removed':
                                    pass
                                self.parent.master_tasks[code]['collaborators'][key]['SubTask'][self.task_name][i][2] = 'COMPLETE'

                    self.currentSubTask = copy.deepcopy(value['coordinator'][text]['SubTask'][self.collaborator_name][0])
                                
 
                    while self.subTask[self.currentSubTask].superstate.state != 'removed':
                        pass
                    self.parent.master_tasks[code]['coordinator'][text]['SubTask'][self.collaborator_name][1] = 'COMPLETE'
                    
                    
                else:
                    for key, val in self.parent.master_tasks[code]['collaborators'].iteritems():
                        if self.task_name in val['SubTask'].keys():
                            for i,x in enumerate(val['SubTask'][self.task_name]):
                                self.subTask[x[0]] = subTask.subTask(parent = self , interface = interface, master_task_uuid = code, collaborators = x[4])
                                self.subTask[x[0]].create_statemachine()
                                self.subTask[x[0]].superstate.create()
                                self.currentSubTask = copy.deepcopy(x[0])
                                while self.subTask[self.currentSubTask].superstate.state != 'removed':
                                    pass
                                self.parent.master_tasks[code]['collaborators'][key]['SubTask'][self.task_name][i][2] = 'COMPLETE'

                
                                
            def COMMITTED(self):
                self.interface.value = 'COMMITTED'
                self.parent.binding_state = 'COMMITTED'

                self.parent.adapter.begin_gather()
                self.binding_state1.set_value("COMMITTED")
                self.parent.adapter.complete_gather()


            def event(self, source, comp, name, value, code = None, text = None):
                #sample: ('cnc', 'Coordinator', 'information_model',{..}, code = 'master_task_uuid', text = 'cnc1') 
                if comp == 'Coordinator' and name == 'binding_state' and value.lower() == 'preparing':
                    self.parent.master_tasks[code[0]] = code[1]

                #elif comp == 'Coordinator' and value.lower() == 'start':
                #        self.committed(code[1], code[0], text)
                    
                elif comp == 'Coordinator' and name == 'binding_state':
                    if value.lower() == 'committing':
                        self.commit()

                    elif value.lower() == 'committed':
                        self.parent.master_tasks[code]['coordinator'][text]['state'][2] = value

                elif 'SubTask' in name:
                    
                    if not self.subTask:
                        def subt():
                            self.committed(self.parent.master_tasks[code],code, self.parent.master_tasks[code]['coordinator'].keys()[0])
                        t0= Thread(target = subt)
                        t0.start()
                        time.sleep(0.3)
                        
                    self.subTask[self.currentSubTask].superstate.event(source, comp, name, value, code, text)
                else:
                    if 'complete' in value.lower():
                        self.parent.binding_state = 'INACTIVE'
                        
                        self.parent.adapter.begin_gather()
                        self.binding_state1.set_value("INACTIVE")
                        self.parent.adapter.complete_gather()
                    self.parent.event(source, comp, name, value, code, text)
                                    
                    
        self.superstate = statemachineModel(parent = parent, interface = interface, collaborator_name = collaborator_name)

    def create_statemachine(self):
        NestedState.separator = ':'
        states = [{'name':'base', 'children':['inactive', 'preparing', 'committing', 'committed']}]

        transitions = [['unavailable', 'base', 'base:inactive'],

                       ['task_created', 'base:inactive', 'base:preparing'],

                       ['commit', 'base:preparing', 'base:committed'],

                       ['completed', 'base:committed', 'base:inactive'],
                       ['failed', 'base:committed', 'base:inactive'],

                       ['default', 'base:inactive', 'base:inactive'],
                       ['default', 'base:committed', 'base:committed']
                       ]

        self.statemachine = Machine(model = self.superstate, states = states, transitions = transitions, initial = 'base',ignore_invalid_triggers=True)
                       
        self.statemachine.on_enter('base:inactive', 'INACTIVE')
        self.statemachine.on_enter('base:preparing', 'PREPARING')
        self.statemachine.on_enter('base:committing', 'COMMITTING')
        self.statemachine.on_enter('base:committed', 'COMMITTED')

        
