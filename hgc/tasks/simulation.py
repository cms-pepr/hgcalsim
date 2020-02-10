# coding: utf-8

"""
HGCAL simulation tasks.
"""


__all__ = ["GSDTask", "RecoTask", "WindowNtupTask"]


import sys
import os
import re
import random
import math
import collections
import argparse

import law
import luigi
import six

from hgc.tasks.base import Task, HTCondorWorkflow, CMSSWSandboxTask
from hgc.util import cms_run_and_publish


luigi.namespace("sim", scope=__name__)


class ProdToolsInterface(CMSSWSandboxTask):

    n_tasks = luigi.IntParameter(default=1, description="number of branch tasks to create to "
        "parallelize the simulation of the requested number of events")
    seed = luigi.IntParameter(default=1, description="initial random seed, will be increased by "
        "branch number, default: 1")
    prodtools_config = luigi.Parameter(default="", description="the arguments to be passed to the "
        "prodtools for creating the gen, reco and ntup configuration files, default: ''")
    prodtools_help = luigi.BoolParameter(default=False, significant=False, description="show the "
        "help message of the prodtools and stop, do not run any task, default: False")

    interactive_params = law.Task.interactive_params + ["prodtools_help"]

    def __init__(self, *args, **kwargs):
        super(ProdToolsInterface, self).__init__(*args, **kwargs)

        # sanitize the prodtools config
        self.prodtools_config = " ".join(self.prodtools_config.strip().split())
        self.prodtools_config = re.sub(r"(-{1,2}[^\s]+)=", r"\1 ", self.prodtools_config)

    def _prodtools_help(self, args):
        cmd = "python SubmitHGCalPGun.py --help"
        cwd = os.path.join(self.cmssw_base, "src/reco_prodtools")

        print("printing the prodtools help message\n")

        code = law.util.interruptable_popen(cmd, cwd=cwd, shell=True, executable="/bin/bash")[0]
        if code != 0:
            raise Exception("printing the prodtools help message failed")

    def store_parts(self):
        parts = super(ProdToolsInterface, self).store_parts()

        # for the moment, just create a semi-deterministic hash of all prodtools config
        hash_content = sorted(self.prodtools_config.split())

        # add the seed
        hash_content.append(self.seed)

        return parts + (law.util.create_hash(hash_content),)

    @property
    def prodtools_nevts(self):
        m = re.match(r"^(|.*\s)(--nevts|-n)\s(\d+)(|\s.*)$", self.prodtools_config)
        return m and int(m.group(3))


class CreateConfigs(ProdToolsInterface):

    def output(self):
        return collections.OrderedDict(
            (tier, self.auto_target("{}_cfg.py".format(tier)))
            for tier in ("gsd", "reco", "ntup")
        )

    @law.decorator.safe_output
    def run(self):
        output = self.output()

        # do the following steps for all data tiers
        for tier, outp in output.items():
            # create a temporary directories to create the files in
            tmp_dir = law.LocalDirectoryTarget(is_tmp=True)
            tmp_dir.child("cfg", type="d").touch()
            tmp_dir.child("jobs", type="d").touch()

            # extend the config
            config = self.prodtools_config.strip("\"'")
            config += " --outDir " + tmp_dir.path
            config += " --datTier " + tier.upper()
            config += " --local"
            config += " --dry-run"
            config += " --skipInputs"
            config += " --keepDQMfile"

            # build and run the command
            cmd = "python SubmitHGCalPGun.py " + config
            cwd = os.path.join(self.cmssw_base, "src/reco_prodtools")
            code = law.util.interruptable_popen(cmd, cwd=cwd, shell=True, executable="/bin/bash")[0]
            if code != 0:
                raise Exception("{} config creation failed".format(tier))

            # provide the output
            cfg_dir = tmp_dir.child("cfg")
            outp.copy_from_local(cfg_dir.child(cfg_dir.glob("partGun_*.py")[0]))


class ParallelProdWorkflow(ProdToolsInterface, law.LocalWorkflow, HTCondorWorkflow):

    previous_task = None

    def create_branch_map(self):
        return {i: i for i in range(self.n_tasks)}

    def workflow_requires(self):
        reqs = super(ParallelProdWorkflow, self).workflow_requires()

        # always require the config files for this set of generator parameters
        reqs["cfg"] = CreateConfigs.req(self, _prefer_cli=["version"])

        # add the "previous" task when not piloting
        if self.previous_task and not self.pilot:
            key, cls = self.previous_task
            reqs[key] = cls.req(self, _prefer_cli=["version"])

        return reqs

    def requires(self):
        reqs = {}

        # always require the config files for this set of generator parameters
        reqs["cfg"] = CreateConfigs.req(self, _prefer_cli=["version"])

        # add the "previous" task
        if self.previous_task:
            key, cls = self.previous_task
            reqs[key] = cls.req(self, _prefer_cli=["version"])

        return reqs


class GSDTask(ParallelProdWorkflow):

    def output(self):
        return self.auto_target("gsd_{}.root".format(self.branch))

    @law.decorator.notify
    def run(self):
        with self.localize_input("r") as inp, self.localize_output("w") as outp:
            cms_run_and_publish(self, inp["cfg"]["gsd"].path, dict(
                outputFile=outp.path,
                maxEvents=self.prodtools_nevts,
                seed=self.seed + self.branch,
            ))


class RecoTask(ParallelProdWorkflow):

    # set previous_task which ParallelProdWorkflow uses to set the requirements
    previous_task = ("gsd", GSDTask)

    def output(self):
        return {
            "reco": self.auto_target("reco_{}.root".format(self.branch)),
            "dqm": self.auto_target("dqm_{}.root".format(self.branch)),
        }

    @law.decorator.notify
    def run(self):
        with self.localize_input("r") as inp, self.localize_output("w") as outp:
            cms_run_and_publish(self, inp["cfg"]["reco"].path, dict(
                inputFiles=[inp["gsd"].path],
                outputFile=outp["reco"].path,
                outputFileDQM=outp["dqm"].path,
            ))


class WindowNtupTask(ParallelProdWorkflow):

    previous_task = ("reco", RecoTask)

    def output(self):
        return self.auto_target("windowntup_{}.root".format(self.branch))

    @law.decorator.notify
    def run(self):
        with self.localize_input("r") as inp, self.localize_output("w") as outp:
            cms_run_and_publish(self, "$CMSSW_BASE/src/RecoHGCal/GraphReco/test/windowNTuple_cfg.py", dict(
                inputFiles=[inp["reco"]["reco"].path],
                outputFile=outp.path,
            ))
