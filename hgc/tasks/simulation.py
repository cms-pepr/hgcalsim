# coding: utf-8

"""
HGCAL simulation tasks.
"""


__all__ = ["GSDTask", "RecoTask", "NtupleTask"]


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


class SimWorkflow(CMSSWSandboxTask, law.LocalWorkflow, HTCondorWorkflow):

    n_events = luigi.IntParameter(default=10, description="number of events to generate per task, "
        "default: 10")
    n_tasks = luigi.IntParameter(default=1, description="number of tasks to execute, default: 1")
    generator = luigi.Parameter(default="flatEtaGun:50:3.0:100.0", description="configuration "
        "string for the generator in the GSD steps, default: flatEtaGun:50:3.0:100.0")
    pileup = luigi.IntParameter(default=200, description="number of pileup events in the GSD "
        "steps, default: 200")
    seed = luigi.IntParameter(default=1, description="initial seed to be used in the GSD steps, "
        "default: 1")

    previous_task = None

    gsd_cfg = os.path.expandvars("$HGC_BASE/files/gsd_cfg.py")
    reco_cfg = os.path.expandvars("$HGC_BASE/files/reco_cfg.py")
    ntup_cfg = os.path.expandvars("$HGC_BASE/files/ntup_cfg.py")

    def store_parts(self):
        sim_part = "n{}__pu{}__s{}__{}".format(
            self.n_events, self.pileup, self.seed, self.generator.replace(":", "_"))
        return super(SimWorkflow, self).store_parts() + (sim_part,)

    def create_branch_map(self):
        return {i: i for i in range(self.n_tasks)}

    def workflow_requires(self):
        reqs = super(SimWorkflow, self).workflow_requires()

        # add the "previous" task when not piloting
        if self.previous_task and not self.pilot:
            key, cls = self.previous_task
            reqs[key] = cls.req(self, _prefer_cli=["version"])

        return reqs

    def requires(self):
        reqs = {}

        # add the "previous" task
        if self.previous_task:
            key, cls = self.previous_task
            reqs[key] = cls.req(self, _prefer_cli=["version"])

        return reqs


class GSDTask(SimWorkflow):

    def output(self):
        return self.auto_target("gsd_{}.root".format(self.branch))

    @law.decorator.notify
    def run(self):
        with self.localize_output("w") as outp:
            cms_run_and_publish(self, self.gsd_cfg, dict(
                outputFile=outp.uri(),
                maxEvents=self.n_events,
                generator=self.generator,
                pileup=self.pileup,
                seed=self.seed + self.branch,
            ))


class RecoTask(SimWorkflow):

    previous_task = ("gsd", GSDTask)

    def output(self):
        return {
            "reco": self.auto_target("reco_{}.root".format(self.branch)),
            "dqm": self.auto_target("dqm_{}.root".format(self.branch)),
        }

    @law.decorator.notify
    def run(self):
        with self.localize_input("r") as inp, self.localize_output("w") as outp:
            cms_run_and_publish(self, self.reco_cfg, dict(
                inputFiles=[inp["gsd"].uri()],
                outputFile=outp["reco"].uri(),
                outputFileDQM=outp["dqm"].uri(),
            ))


class NtupleTask(SimWorkflow):

    previous_task = ("reco", RecoTask)

    def output(self):
        return self.auto_target("ntup_{}.root".format(self.branch))

    @law.decorator.notify
    def run(self):
        with self.localize_input("r") as inp, self.localize_output("w") as outp:
            cms_run_and_publish(self, self.ntup_cfg, dict(
                inputFiles=[inp["reco"]["reco"].uri()],
                outputFile=outp.uri(),
            ))
