import sys
from xmlrpc.client import Boolean

trace_filename = sys.argv[4]
trace_file = open(trace_filename, "w")
#trace_file = 0
#tid = 0
num_cu = int(sys.argv[1]) #only simulate single cluster; these represent conventional CU, not chiplets

def init_trace():
     global trace_file
     #global trace_filename
     trace_file.write('{\n"traceEvents": [\n')

def begin_trace_event(pid, tid, time, name):
     global trace_file
     trace_file.write('{{"name": "{0}", "cat": "Cod", "ph": "B", "ts": "{1}", "pid": "{2}", "tid": "{3}", "args": {{}}}},\n'.format(name, time, pid, tid))

def end_trace_event(pid, tid, time, name):
     global trace_file
     trace_file.write('{{"name": "{}", "cat": "Cod", "ph": "E", "ts": "{}", "pid": "{}", "tid": "{}", "args": {{}}}},\n'.format(name, time, pid, tid))

def final_trace_event(pid, tid, time):
     global trace_file
     trace_file.write('{{"name": "end_cod", "cat": "Cod", "ph": "B", "ts": "{}", "pid": "{}", "tid": "{}", "args": {{}}}},\n'.format(time, pid, tid))
     trace_file.write('{{"name": "end_cod", "cat": "Cod", "ph": "E", "ts": "{}", "pid": "{}", "tid": "{}", "args": {{}}}}\n'.format(time+1, pid, tid)) #no comma after event

def close_trace():
     global trace_file
     trace_file.write(']\n}')
     trace_file.close()

init_trace()
codelet_dict = {}
class Codelet:
     def __init__(self, name, delay, dep, dep_list, is_pipelined, is_special, special_type, special_delay_mult):
          #global tid
          self.name = name
          self.delay = delay
          self.dep = dep
          self.reset_dep = dep
          self.is_pipelined = is_pipelined
          self.dep_list = dep_list
          self.active = False
          self.special_active = False
          self.is_special = is_special
          self.special_type = special_type
          self.special_delay_mult = special_delay_mult
          self.tid = 0 #for tracing, set when firing
          #tid += 1
     
     def dec_dep(self):
          self.dep = self.dep - 1
     
     def fire(self, time, is_special, tid):
          #Consumer codelets of pipelines should:
          #    - Only have the producer(s) as a dependency
          #    - Only be marked as pipelined if they 
          #      are also streaming output
          self.tid = tid
          if self.is_pipelined:
               for consumer in self.dep_list:
                    codelet_dict[consumer].dec_dep()
          self.fire_time = time
          self.active = True
          self.special_active = is_special
          begin_trace_event(0, self.tid, time, self.name)
          #have to reset deps here
          self.dep = self.reset_dep

     def is_done(self, time):
          if (self.special_active):
               if time > (self.fire_time + self.delay * self.special_delay_mult):
                    self.active = False
                    #self.special_active = False #this breaks the process; freeing Chiplet if statement needs this to be True still
                    end_trace_event(0, self.tid, time, self.name)
                    return(True)
               else:
                    return(False)
          elif time > (self.fire_time + self.delay):
               self.active = False
               end_trace_event(0, self.tid, time, self.name)
               return(True)
          else:
               return(False)

     def is_active(self):
          return(self.active)

     def is_special_active(self):
          return(self.special_active)

     def is_enabled(self):
          return(self.dep == 0)

     def is_special(self):
          return(self.is_special)

     def get_type(self):
          if (self.is_special):
               return(self.special_type)
          else:
               return("")
     
     def get_name(self):
          return(self.name)
     
     def get_dep_list(self):
          return(self.dep_list)

class Chiplet:
     def __init__(self, name, res_num, tid_offset):
          self.name = name
          self.res_num = res_num
          self.res_cnt = 0
          self.chiplet_list = []
          for i in range(res_num):
               self.chiplet_list.append(tid_offset + i) #offset so 
     
     #Acquire chiplets resource
     def acq(self):
          if self.res_cnt < self.res_num:
               self.res_cnt += 1
               return(True)
          else:
               return(False)
     
     #Release chiplets resource
     def rel(self):
          self.res_cnt -= 1

chiplet_dict = {}
chiplet_dict["highSIMD"] = Chiplet("highSIMD", 16, num_cu)
chiplet_dict["formatChanger"] = Chiplet("formatChanger", 16, num_cu+16)

# n is the power of 2, i.e. n=3 represents an 8x8 matrix (or more specifically a graph that can handle at smallest an 8x8 matrix)
# Procedural n inner product matrix multitplication --------------------------------------------------------------------------
def inner_product_n(codelet_dict, n, pipeline, use_chiplet):
     width = 2**n
     granularity = 1 #lower = finer, 1 is the finest
     chiplet1 = "highSIMD" if use_chiplet else ""
     mult_delay = granularity * width * 3
     dot_prod_delay = granularity * width * 5
     add_st_delay = granularity * width
     if pipeline:
          codelet_dict["start"] = Codelet("start", 1, 1, ["pointwise_mult{}".format(x) for x in range(width*width)], False, False, "", 1.0)
          for i in range(width*width):
               current = "pointwise_mult{}".format(i)
               codelet_dict[current] = Codelet(current, mult_delay, 1, ["block_sum{}".format(i//width)], pipeline, use_chiplet, chiplet1, 0.07)
          for i in range(width):
               current = "block_sum{}".format(i)
               codelet_dict[current] = Codelet(current, add_st_delay, width, ["end"], False, use_chiplet, chiplet1, 0.07)
          codelet_dict["end"] = Codelet("end", 1, width, [], False, False, "", 1.0)
     else:
          codelet_dict["start"] = Codelet("start", 1, 1, ["dot_prod_st{}".format(x) for x in range(width*width)], False, False, "", 1.0)
          for i in range(width*width):
               current = "dot_prod_st{}".format(i)
               codelet_dict[current] = Codelet(current, dot_prod_delay, 1, ["end"], False, use_chiplet, chiplet1, 0.07)
          codelet_dict["end"] = Codelet("end", 1, width*width, [], False, False, "", 1.0)
# ---------------------------------------------------------------------------------------------------------------------------

# Procedural n outer product matrix multiplication --------------------------------------------------------------------------
def outer_product_n(codelet_dict, n, pipeline, use_chiplet):
     codelet_dict["start"] = Codelet("start", 1, 1, ["convert_form{}".format(x) for x in range(2**n)], False, False, "", 1.0)
     granularity = 1 #lower = finer. 1 is the finest grain
     width = 2**n
     chiplet1 = ""
     chiplet2 = ""
     if use_chiplet:
          chiplet1 = "formatChanger"
          chiplet2 = "highSIMD"
     mult_delay = granularity * (width) * 3 
     sum_delay =  granularity * (width * width)
     level = int(2**n)
     off_agg = 0
     agg = 0
     for i in range(level):
          current = "convert_form{}".format(i)
          codelet_dict[current] = Codelet(current, mult_delay, 1, ["vector_mult{}".format(i)], pipeline, use_chiplet, chiplet1, 0.5) #use UDP for comparison?

     for i in range(level):
          current = "vector_mult{}".format(i)
          codelet_dict[current] = Codelet(current, mult_delay, 1, ["matrix_sum{}".format(i//2)], pipeline, use_chiplet, chiplet2, 0.07) #TPUs 15-30x faster
          print("creating Codelet", current, "-->", "matrix_sum{}".format(i//2))
     level = int(level // 2)
     agg += level 
     for j in range(n-1):
          for i in range(level):
               current = "matrix_sum{}".format(off_agg+i) # 0 - 7
               codelet_dict[current] = Codelet(current, sum_delay, 2, ["matrix_sum{}".format(agg+i//2)], pipeline, use_chiplet, chiplet2, 0.07)
               print("creating Codelet", current, "-->", "matrix_sum{}".format(agg+i//2))
          off_agg += level #now 8
          level = int(level // 2) #now 4
          agg += level      #now 12 
     agg = agg - level
     current = "matrix_sum{}".format(agg)
     codelet_dict[current] = Codelet(current, sum_delay, 2, ["end"], False, use_chiplet, chiplet2, 0.07)
     codelet_dict["end"] = Codelet("end", 0, 1, [], False, False, "", 1.0)
     print(codelet_dict.keys())
# -----------------------------------------------------------------------------------------------------------------------------

#Define all the Codelets and their dependencies here (or use a predefined function for a specific graph)
#DO NOT add a Codelet with 0 deps; start codelet should have 1 deps and be prematurely decreased
#For pipelining: is_pipelined will indicate that the Codelet is intended to stream to the Codelet after it.
#     This intrinsically means it should only have one Codelet in its dep_list, and that one consumer
#     Codelet should only set is_pipelined to True if it is also streaming to a single consumer, and so on.
#     The consumer Codelet should only have one dependency, that being the producer Codelet, because the
#     consumer will automatically receive a dec_dep when the producer is fired. This means the consumer
#     inherently has the same dependencies as the producer Codelet.

pipelining_enabled = (int(sys.argv[2]) == 1)
chiplet_enabled = (int(sys.argv[3]) == 1)
#outer_product_n(codelet_dict, 6, pipelining_enabled, chiplet_enabled)
inner_product_n(codelet_dict, 6, pipelining_enabled, chiplet_enabled) #builds graph for 2**6 inner product GEMM

time = 0
cu_list = []
for i in range(num_cu):
     cu_list.append(i)
active_cycles = 0
active_chiplet_cycles = 0
active_chiplets = 0
end_now = False

codelet_dict["start"].dec_dep()
while(not(end_now)):
     #first walk through to update deps and release resources
     for name, cod in codelet_dict.items():
          if (cod.is_active()):
               if (cod.is_done(time)):
                    if (not(cod.is_special_active())): #if normal codelet, release CU
                         cu_list.append(cod.tid)
                    else: #if chiplet codelet, release chiplet
                         chiplet_dict[cod.get_type()].chiplet_list.append(cod.tid)
                    if not(cod.is_pipelined): #if pipelined, deps already signaled, so only signal if normal
                         for cod_name in cod.get_dep_list():
                              codelet_dict[cod_name].dec_dep()
                              print("Decreasing deps of", cod_name)

     #second walk through to fire Codelets that are enabled and have resources available
     for name, cod in codelet_dict.items():
          if (cod.is_enabled()): #if codelet has no remaining dependencies
               print(name, "is enabled")
               if (cod.is_special): #and it targets a chiplet
                    if len(chiplet_dict[cod.get_type()].chiplet_list) > 0:
                         cod.fire(time, True, chiplet_dict[cod.get_type()].chiplet_list.pop()) #special firing
                         print("Firing", name, "on chiplet")
               elif(name == "end"): #end codelet
                    end_now = True
                    break #should break while loop
               elif (len(cu_list) > 0):
                    cod.fire(time, False, cu_list.pop()) #firing on normal CU
                    print("Firing", name)

     active_chiplets = 0
     for name, chiplet in chiplet_dict.items():
          active_chiplets += chiplet.res_num - len(chiplet.chiplet_list)
     print(str(time) + "----------------------------------")
     active_cycles += num_cu - len(cu_list)
     active_chiplet_cycles += active_chiplets
     time += 1
#end while(not(end_now))
final_trace_event(0, 128, time)
close_trace()
num_chiplets = 0
for name, chiplet in chiplet_dict.items():
     num_chiplets += chiplet.res_num
print(str(num_cu), "CUs available")
print("Chiplets available:", str(num_chiplets))
print("Pipelining enabled:", str(pipelining_enabled))
print("Chiplets enabled:", str(chiplet_enabled))
print("Final time:", str(time))
print("Chiplet Utilization:", str(float(active_chiplet_cycles/time/num_chiplets)))
print("CU Utilization:", str(float(active_cycles/time/num_cu)))
print("-------------------------------------------------------------")
