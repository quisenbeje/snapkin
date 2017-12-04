** snapkin

this is a script to help manage files and directories which have been backed-up
in btrfs snapshots. given a file or path the script will search for snapshots
and list, show disk usage, and/or delete the targets in the snapshots. executing
the script requires root access to perform btrfs commands. if removing files or
path do so with caution, "sudo rm -rf ..." is dangerous - there are a few fail
safes in place, but still.
