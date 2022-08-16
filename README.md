# codelet\_program\_sim

## Usage

The base python program is functional with Python 3.9.7. The chiplet\_test.sh
program will run the python program with the currently selected Codelet graph
with only normal CUs, with chiplets enabled, with pipelining enabled, and with
both chiplets and pipelining enabled. Through the shell script, full program
output is sent to respective text files in the test\_output directory while
trace files are sent to the traces directory and only the execution summary
of each run is output to the command line. The trace files can be read
using the Perfetto UI. Each CU and chiplet core are their own threads in
the traces. Threads 0 - `num_cus` are normal CUs while the rest of the
threads are chiplet cores. Note that currently, Codelets that are chiplet
enabled ONLY run on their respective chiplets (there is currently no
heterogeneous scheduling). For more info on the Codelet Model see
[here](https://www.capsl.udel.edu/codelets.shtml).
