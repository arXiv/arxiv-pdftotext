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

total_mem_in_kb=$(cat /proc/meminfo | grep MemFree | awk '{ print $2 }')
total_mem=$(( total_mem_in_kb * 1024 ))
avail_mem=$(( total_mem * 8 / 10))

# create cgroup that $APPUSER can use
cgcreate -t $APPUSER:nogroup -a $APPUSER:nogroup -g memory:$CGROUPNAME

# "/sys/fs/cgroup/memory/memory.limit_in_bytes",  # cgroups v1 hard limit
# "/sys/fs/cgroup/memory/memory.soft_limit_in_bytes",  # cgroups v1 soft limit
# "/sys/fs/cgroup/memory.max",  # cgroups v2 hard limit
# "/sys/fs/cgroup/memory.high",  # cgroups v2 soft limit
if [ -r /sys/fs/cgroup/cgroup.controllers ] ; then
  # cgroups v2
  # we cannot simply create a group since in v2 access control is more strict
  # and we need access to cgroup.procs
  # One might be able to work around this according to the following document,
  # but that complicates a lot of things:
  # - https://unix.stackexchange.com/questions/725112/using-cgroups-v2-without-root
  echo "Detected cgroups v2" >&2
  chmod go+w /sys/fs/cgroup/cgroup.procs
  echo $avail_mem > /sys/fs/cgroup/${CGROUPNAME}/memory.max
else
  # cgroups v1
  echo "Detected cgroups v1" >&2
  echo $avail_mem > /sys/fs/cgroup/memory/${CGROUPNAME}/memory.limit_in_bytes
fi

# we need to preserve the environment, otherwise the various variables set
# by docker -e are not visible to the webserver process!
sudo --preserve-env -u $APPUSER /app/.venv/bin/hypercorn --error-logfile - --bind 0.0.0.0:8888 webserver:app

