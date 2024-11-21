#!/bin/bash

# Set Bash "strict" mode
# see: http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# these need to be in sync with:
# - webserver.py: variable CGROUPNAME
# - Dockerfile: adduser call
APPUSER=appuser
CGROUPNAME=pdftotext


# Cleanup routine:
# - kill hypercorn
# - remove cgroup
cleanup() {
  # get the signal $? is set to signal number + 128
  sig=$(($? - 128))
  echo "GOT SIGNAL $sig" >&2
  # send the signal to hypercorn
  echo "Trying to kill pid $PID with sig $sig" >&2
  kill -n $sig $PID
  # remove the cgroup
  echo "Deleting cgroup in signal handler" >&2
  cgdelete -g memory:$CGROUPNAME
}

# docker first sends SIGTERM
# Ctrl-C of interactive session give SIGINT
trap 'cleanup' SIGTERM
trap 'cleanup' SIGINT


total_mem_in_kb=$(cat /proc/meminfo | grep MemFree | awk '{ print $2 }')
total_mem=$(( total_mem_in_kb * 1024 ))
avail_mem=$(( total_mem * 8 / 10))
# allow setting max allowed memory via env var MAX_ALLOWED_MEMORY
allowed_mem=${MAX_ALLOWED_MEMORY:-$avail_mem}
# check that allowed mem is actually an unsigned integer
if [[ "$allowed_mem" != +([0-9]) ]] ; then
  echo "Not supported memory setting: $allowed_mem" >&2
  exit 1
fi

if [ -r /sys/fs/cgroup/cgroup.controllers ] ; then
  echo "Detected cgroups v2" >&2
  CGROUP_VERSION=2
else
  echo "Detected cgroups v1" >&2
  CGROUP_VERSION=1
fi

# check whether the cgroup already exists. If yes, stop!!
if [ $CGROUP_VERSION = 2 ] ; then
  if [ -d /sys/fs/cgroup/${CGROUPNAME} ] ; then
    echo "cgroup $CGROUPNAME already present, exiting!" >&2
    exit 1
  fi
else
  if [ -d /sys/fs/cgroup/memory/${CGROUPNAME} ] ; then
    echo "cgroup $CGROUPNAME already present, exiting!" >&2
    exit 1
  fi
fi

# create cgroup that $APPUSER can use
cgcreate -t $APPUSER:nogroup -a $APPUSER:nogroup -g memory:$CGROUPNAME

# "/sys/fs/cgroup/memory/memory.limit_in_bytes",  # cgroups v1 hard limit
# "/sys/fs/cgroup/memory/memory.soft_limit_in_bytes",  # cgroups v1 soft limit
# "/sys/fs/cgroup/memory.max",  # cgroups v2 hard limit
# "/sys/fs/cgroup/memory.high",  # cgroups v2 soft limit
if [ $CGROUP_VERSION = 2 ] ; then
  # cgroups v2
  # we cannot simply create a group since in v2 access control is more strict
  # and we need access to cgroup.procs
  # One might be able to work around this according to the following document,
  # but that complicates a lot of things:
  # - https://unix.stackexchange.com/questions/725112/using-cgroups-v2-without-root
  chmod go+w /sys/fs/cgroup/cgroup.procs
  echo "$allowed_mem" > /sys/fs/cgroup/${CGROUPNAME}/memory.max
else
  # cgroups v1
  echo "$allowed_mem" > /sys/fs/cgroup/memory/${CGROUPNAME}/memory.limit_in_bytes
fi

# we need to preserve the environment, otherwise the various variables set
# by docker -e are not visible to the webserver process!
sudo --preserve-env -u $APPUSER /app/.venv/bin/hypercorn --error-logfile - --bind 0.0.0.0:8888 webserver:app &
PID=$!
# wait for the process to terminate, or getting killed via signal
wait
# In case we are still here, delete the cgroup
echo "Deleting cgroup after wait" >&2
cgdelete -g memory:$CGROUPNAME


