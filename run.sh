#!/bin/bash

xterm -hold -e 'python ./main.py' &
sleep 1
xterm -hold -e 'tail -f `ls -1tr ./logs/*.log | tail -1`' &