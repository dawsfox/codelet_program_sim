#!/bin/bash

python3 chiplet_codelet_case_study.py 64 0 0 ./traces/trace_inner.json > ./test_output/testing_inner.txt
tail -n 8 ./test_output/testing_inner.txt
python3 chiplet_codelet_case_study.py 64 1 0 ./traces/trace_inner_pipe.json > ./test_output/testing_inner_pipe.txt
tail -n 8 ./test_output/testing_inner_pipe.txt
python3 chiplet_codelet_case_study.py 32 0 1 ./traces/trace_inner_chip.json > ./test_output/testing_inner_chip.txt
tail -n 8 ./test_output/testing_inner_chip.txt
python3 chiplet_codelet_case_study.py 32 1 1 ./traces/trace_inner_pipe_chip.json > ./test_output/testing_inner_pipe_chip.txt
tail -n 8 ./test_output/testing_inner_pipe_chip.txt
