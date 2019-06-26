# argument: the path to the `fec` plugin directory in pquic
# /!\ make sure you executed `make` in the plugin directory before executing this script
find $1 -name "*.o" | grep -v block | grep -v never_send_recovered_frames.o
