import click, os, re, sys
from subprocess import Popen, PIPE
from pkg_resources import get_distribution, DistributionNotFound
try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    pass

# error indicator string
ERROR = '__error__'

@click.group(invoke_without_command=True)
@click.option('-v', '--version', is_flag=True, help='show version')
@click.pass_context
def cli(ctx,version):
  ''' program to manipulate files/directories in btrfs snapshots '''
  if version:
    click.echo(__version__)
    sys.exit()

  if ctx.obj is None:
    ctx.obj = {}
  ctx.obj['targets'] = []
  # show list with summary option of cwd when no command is specified
  if ctx.invoked_subcommand is None:
    ctx.invoke(list,path=os.getcwd(),summary=True)



def shell_cmd(cmd, return_on_error=False):
  ''' execute given shell command '''
  p = Popen(cmd, stdout=PIPE,stderr=PIPE)
  out, err = p.communicate()

  if p.returncode != 0:
    if return_on_error:
      return ':'.join([ERROR, str(err, 'utf-8')])
    else:
      click.echo('cmd error: {}\n{}'.format(' '.join(cmd),err))
      sys.exit(1)

  return out

def errored(rtn):
  ''' return true if input is and error; false otherwise '''
  err = True if rtn[:len(ERROR)] == ERROR else False
  return err



def get_target_subvolume(target):
  ''' find root subvolume of given path '''

  cmd = ['btrfs', 'subvolume', 'show', target]

  cmd_return = shell_cmd(cmd, return_on_error=True)
  if not errored(cmd_return):
    # subvolume has been found return it's path
    return target

  elif target == '/':
    # no data was found for the base subvolume
    click.echo('Failed to get subvolume info on path or parent\n  {}'.format(cmd_return))
    sys.exit(1)

  else:
    # back up a level and research
    return get_target_subvolume(os.path.abspath(os.path.join(target,"..")))



def get_subvol_info(subvol_path):
  ''' collect subvolume info of given path '''

  cmd = ['btrfs', 'subvolume', 'show', subvol_path]
  sdata = shell_cmd(cmd).splitlines()

  def parse(heading, lines):
    ''' look for content based on given heading and return remaining data '''

    m   = False
    val = ''
    # loop through all lines of info
    while len(lines) != 0:
      line = str(lines.pop(0), 'utf-8')
      m = re.match(r'\s*{}\s*(.+)'.format(heading), line)
      # if match is found collect data and exit loop
      if m:
        val = m.group(1)
        break
    # return value and remaining unsearched data
    return val, lines

  info = {}
  info['name'],   sdata = parse('Name:',          sdata)
  info['time'],   sdata = parse('Creation time:', sdata)
  info['id'],     sdata = parse('Subvolume ID:',  sdata)
  info['parent'], sdata = parse('Parent ID:',     sdata)
  info['top'],    sdata = parse('Top level ID:',  sdata)
  info['flags'],  sdata = parse('Flags:',         sdata)
  info['snapshots'] = []
  while sdata:
    snap, sdata = parse('\t\t\t\t',sdata)
    info['snapshots'].append(snap)

  return info



def get_path_usage(path):
  ''' get shallow disk usage of path '''
  cmd = ['du', '-h', '-d0', path]
  out = shell_cmd(cmd, return_on_error=True)
  if not errored(out):
    return str(out, 'utf-8').split()[0]
  return '??'



@cli.command()
@click.option('-s', '--summary', is_flag=True, help='show only summary info')
@click.option('-f', '--flags',   is_flag=True, help='show snapshot flags')
@click.option('-d', '--disk',    is_flag=True, help='show target disk usage in snapshot')
@click.option('-S', '--silent',  is_flag=True, help='collect target snapshots with no display')
@click.argument('path',type=click.Path())
@click.pass_context
def list(ctx, path, summary, flags, disk, silent):
  ''' search btrfs snapshots for a file or directory '''

  target        = os.path.abspath(path)
  target_subvol = get_target_subvolume(target)
  base_sub      = get_subvol_info(target_subvol)

  # look for mount point of base subvolume
  with open('/proc/mounts') as f:

    for line in f:
      # look for top level mount
      m = re.match(r'^.*?\s+([^\s]*).*subvolid={}.*'.format(base_sub['top']), line)
      if m:
        mount_point = m.group(1)
        break

    if not mount_point:
      click.echo('top level volume (subvolid={}) not listed in /proc/mount'.format(base_sub['top']))
      sys.exit(1)

  # get stub path and output full target path
  relative_path = target[len(target_subvol):]
  if not silent:
    click.echo('target: {}  ({})'.format(target, get_path_usage(target)))
  else:
    ctx.obj['relative_path'] = relative_path

  # process all snapshots containing the target
  for snap in base_sub['snapshots']:
    # full path of snapshot
    snap_path = ('').join([mount_point,'/',snap])
    # full path of target in snapshot
    search_path = ('').join([snap_path,relative_path])

    # process only snapshots that contain the target
    if os.path.isdir(search_path) or os.path.isfile(search_path):
      if silent:
        ctx.obj['targets'].append(search_path)

      else:
        # get info about snapshot subvolue
        snap_sub  = get_subvol_info(snap_path)

        # if information was found
        if snap_sub:
          # gather output
          out = ['  {}'.format(snap_sub['time'])]
          if flags:
            out.append('{}'.format(snap_sub['flags']))
          if disk:
            out.append('{}'.format(get_path_usage(search_path)))
          out.append('{}'.format(snap_path))

          # print output
          click.echo(('   ').join(out))


@cli.command()
@click.option('-p', '--preview',     is_flag=True, help='preview removals without making changes')
@click.option('-i', '--interactive', is_flag=True, help='prompt before every removal')
@click.option('-d', '--disk',        is_flag=True, help='show target disk usage in snapshot')
@click.option('-a', '--active',      is_flag=True, help='remove target in active filesystem')
@click.argument('path',type=click.Path())
@click.pass_context
def remove(ctx, path, preview, interactive, disk, active):
  ''' command to remove a file/directory from btrfs snapshots '''

  # run list command with silent flag to build target list
  ctx.invoke(list,path=path,silent=True)

  def delete_in_subvolume(target):
    ''' delete a given file in the snapshot which it resides '''

    def get_subvol_property(subvol, prop):
      ''' returns given subvolume's property '''
      cmd = ['btrfs', 'property', 'get', '-ts', subvol, prop]
      out = shell_cmd(cmd)
      return str(out, 'utf-8').strip()

    def set_subvol_property(subvol, prop, val):
      ''' sets given subvolume's property '''
      cmd = ['btrfs', 'property', 'set', '-ts', subvol, prop, val]
      shell_cmd(cmd)
      return

    # get target subvolume and properties
    subvol   = get_target_subvolume(target)
    ro_state = get_subvol_property(subvol,'ro')
    read_only = True if ro_state == 'ro=true' else False

    # change readonly subvolumes to non-readonly in order to delete
    if read_only:
      set_subvol_property(subvol,'ro','false')

    # recursively remove path from subvolume
    cmd = ['rm', '-rf', target]
    cmd_return = shell_cmd(cmd, return_on_error=True)
    if errored(cmd_return):
      if read_only: set_subvol_property(subvol,'ro','true')
      click.echo('cmd error: {}\n{}'.format(' '.join(cmd), cmd_return))
      sys.exit(1)

    # if subvolume was originally readonly then set it back
    if read_only:
      set_subvol_property(subvol,'ro','true')

    return

  def get_reply(prompt):
    ''' display the given prompt and return true or false. true is yY or enter,
        false is nN, qQ exits program, all else re-queries prompt. '''

    click.echo('{} [Y/n/q]? '.format(prompt),nl=False)
    reply = click.getchar().lower()
    click.echo()
    if reply == '\r' or reply == 'y':
      reply = True
    elif reply == 'n':
      reply = False
    elif reply == 'q':
      sys.exit()
    else:
      reply = get_reply('Confirm')
    return reply


  if active and os.path.isdir(path) or os.path.isfile(path):
    ''' add file in active snapshot to list of targets if it exists '''
    ctx.obj['targets'].append(os.path.abspath(path))

  if not interactive and not preview:
    ''' erase all history of target path - give one prompt to be safe '''

    erase = get_reply('  erase "{}" in all snapshots (count:{})'.format(
      ctx.obj['relative_path'],
      len(ctx.obj['targets'])))
    if not erase:
      sys.exit()
    else:
      with click.progressbar(ctx.obj['targets'], show_pos=True) as bar:
        for target in bar:
          delete_in_subvolume(target)


  for target in reversed(ctx.obj['targets']):
    ''' loop through all targets, i.e. paths existing in snapshots '''

    if preview:
      ''' show what would have been deleted, but don't delete '''

      out = []
      out.append('  would remove: {}'.format(target))
      if disk: out.append('{}'.format(get_path_usage(target)))
      click.echo(('  ').join(out))

    elif interactive:
      ''' perform remove per file based on user feed back '''

      prompt = []
      prompt.append('  rm -rf {}'.format(target))
      if disk: prompt.append('({})'.format(get_path_usage(target)))
      erase = get_reply(' '.join(prompt))
      if erase:
        delete_in_subvolume(target)



if __name__ == '__main__':
  cli(obj={})
