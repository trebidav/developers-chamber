import os
import subprocess
import logging
import sys

from pathlib import Path

import shutil

from click import ClickException, BadParameter

from python_hosts.hosts import Hosts, HostsEntry
from python_hosts.exception import UnableToWriteHosts


LOGGER = logging.getLogger()


def call_command(command):
    try:
        LOGGER.info(command if isinstance(command, str) else ' '.join(command))
        subprocess.check_call(command, stdout=sys.stdout, shell=isinstance(command, str))
    except subprocess.CalledProcessError:
        raise ClickException('Command returned error')


def get_command_output(command):
    try:
        LOGGER.info(command if isinstance(command, str) else ' '.join(command))
        return subprocess.check_output(command, shell=isinstance(command, str))
    except subprocess.CalledProcessError:
        raise ClickException('Command returned error')


def set_hosts(domains):
    try:
        hosts = Hosts()
        hosts.add([HostsEntry(entry_type='ipv4', address='127.0.0.1', names=domains)])
        hosts.write()
    except UnableToWriteHosts:
        raise ClickException('Unable to write to hosts file. Please call command with "sudo".')


def _call_compose_command(project_name, compose_files, command, containers=None, extra_command=None):
    compose_command = ['docker-compose', '-p', project_name]
    compose_command += [
        '-f{}'.format(f) for f in compose_files
    ]
    compose_command.append(command)
    compose_command += list(containers) if containers else []
    if extra_command:
        compose_command.append(extra_command)
    call_command(compose_command)


def compose_build(project_name, compose_files, containers=None):
    _call_compose_command(project_name, compose_files, 'build', containers)


def compose_run(project_name, compose_files, containers, command):
    for container in containers:
        _call_compose_command(project_name, compose_files, 'run', [container], command)


def compose_exec(project_name, compose_files, containers, command):
    for container in containers:
        _call_compose_command(project_name, compose_files, 'exec', [container], command)


def compose_kill_all():
    if get_command_output('docker ps -q'):
        call_command('docker kill $(docker ps -q)')


def compose_up(project_name, compose_files, containers):
    _call_compose_command(project_name, compose_files, 'up', containers)


def compose_stop(project_name, compose_files, containers):
    _call_compose_command(project_name, compose_files, 'stop', containers)


def docker_clean(hard=False):
    call_command(['docker', 'image', 'prune', '-f'])
    call_command(['docker', 'container', 'prune', '-f'])
    if hard:
        call_command(['docker', 'system', 'prune', '-af'])
        if get_command_output('docker volume ls -q'):
            call_command('docker volume rm $(docker volume ls -q)')


def compose_install(project_name, compose_files, var_dirs=None, containers_dir_to_copy=None,
                    install_container_commands=None):
    var_dirs = [
        Path.cwd() / var_dir for var_dir in var_dirs or ()
    ]

    for _, _, host_dir in containers_dir_to_copy:
        shutil.rmtree(Path.cwd() / host_dir, ignore_errors=True)

    for var_dir in var_dirs:
        shutil.rmtree(var_dir, ignore_errors=True)

    for var_dir in var_dirs:
        os.makedirs(var_dir)

    for _, _, host_dir in containers_dir_to_copy:
        os.makedirs(Path.cwd() / host_dir)

    compose_build(project_name, compose_files)

    for container_name, container_dir, host_dir in containers_dir_to_copy:
        call_command([
            'docker', 'run', '-v', '{}:/copy_tmp'.format(Path.cwd() / host_dir),
            '{}_{}'.format(project_name, container_name),
            "cp -r {}/* /copy_tmp/".format(container_dir)
        ])

    for container_name, command in install_container_commands or ():
        compose_run(project_name, compose_files, [container_name], command)