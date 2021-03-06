# coding: utf-8

"""
Helpful utilities.
"""


__all__ = [
    "wget", "cms_run", "parse_cms_run_event", "cms_run_and_publish",
]


import os
import re
import subprocess

import six
import law


def wget(src, dst, force=False):
    # check if the target directory exists
    dst = os.path.normpath(os.path.abspath((os.path.expandvars(os.path.expanduser(dst)))))
    if os.path.isdir(dst):
        dst = os.path.join(dst, os.path.basename(src))
    else:
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            raise IOError("target directory '{}' does not exist".format(dst_dir))

    if os.path.exists(dst) and not force:
        raise IOError("target '{}' already exists".format(dst))

    cmd = ["wget", src, "-O", dst]
    code, _, error = law.util.interruptable_popen(law.util.quote_cmd(cmd), shell=True,
        executable="/bin/bash", stderr=subprocess.PIPE)

    if code != 0:
        raise Exception("wget failed: {}".format(error))

    return dst


def cms_run(cfg_file, args, cmd_format="{}", yield_output=False):
    if isinstance(args, dict):
        args = list(args.items())

    def cms_run_arg(key, value):
        return " ".join("{}=\"{}\"".format(key, v) for v in law.util.make_list(value))

    cfg_file = os.path.expandvars(os.path.expanduser(cfg_file))
    sorted_args = sorted(args, key=lambda tpl: tpl[0])
    args_str = " ".join(cms_run_arg(*tpl) for tpl in sorted_args)
    cmd = "cmsRun {} {}".format(cfg_file, args_str)

    # apply the custom cmd_format
    cmd = cmd_format.format(cmd)
    print("cmd: {}".format(law.util.colored(cmd, style="bright")))

    fn = law.util.interruptable_popen if not yield_output else law.util.readable_popen
    return fn(cmd, shell=True, executable="/bin/bash")


def parse_cms_run_event(line):
    if not isinstance(line, str):
        return None

    match = re.match(r"^Begin\sprocessing\sthe\s(\d+)\w{2,2}\srecord\..+$", line.strip())
    if not match:
        return None

    return int(match.group(1))


def cms_run_and_publish(task, *args, **kwargs):
    max_events = kwargs.get("maxEvents")

    # run the command, parse output as it comes
    kwargs["yield_output"] = True
    for obj in cms_run(*args, **kwargs):
        if isinstance(obj, six.string_types):
            print(obj)

            # try to parse the event number
            n_event = parse_cms_run_event(obj)
            if n_event:
                task._publish_message("handle event {}".format(n_event))
                if max_events:
                    task.publish_progress(100. * n_event / max_events)
        else:
            # obj is the popen object
            if obj.returncode != 0:
                raise Exception("cmsRun failed")
