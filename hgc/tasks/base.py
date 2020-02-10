# coding: utf-8

"""
Custom base task classes.
"""


__all__ = [
    "Task", "HTCondorWorkflow", "UploadSoftware", "UploadRepo", "UploadCMSSW", "CMSSWSandboxTask",
    "InstallCMSSW",
]


import os
import re
import math

import law
import luigi

law.contrib.load("cms", "git", "htcondor", "root", "slack", "tasks", "telegram", "wlcg")


class Task(law.Task):
    """
    Custom base task.
    """

    version = luigi.Parameter(description="version of outputs to produce")
    notify = law.NotifyMultiParameter(parameters=[
        law.telegram.NotifyTelegramParameter(significant=False),
        law.slack.NotifySlackParameter(significant=False),
    ])

    user = luigi.Parameter(default=os.environ["HGC_GRID_USER"], significant=False,
        description="the user executing the task, only for visual purposes on central luigi "
        "schedulers")

    exclude_params_index = {"user"}
    exclude_params_req = {"notify"}
    exclude_params_branch = {"notify"}
    exclude_params_workflow = {"notify"}

    message_cache_size = 20

    output_collection_cls = law.SiblingFileCollection

    workflow_run_decorators = [law.decorator.notify]

    default_store = "$HGC_DEFAULT_STORE"

    def __init__(self, *args, **kwargs):
        # harcoded for the moment
        self.cmssw_version = "CMSSW_11_0_0_patch1"
        self.cmssw_base = os.path.expandvars("$HGC_CMSSW_BASE/{}".format(self.cmssw_version))

        # store a bash sandbox to interact with the cmssw environment
        self.cmssw_sandbox = law.BashSandbox("$HGC_BASE/files/env_{}.sh".format(self.cmssw_version))

        super(Task, self).__init__(*args, **kwargs)

    def store_parts(self):
        parts = (self.task_family,)
        return parts

    def store_parts_opt(self):
        parts = tuple()
        if self.version is not None:
            parts += (self.version,)
        return parts

    def local_path(self, *path, **kwargs):
        parts = [str(p) for p in self.store_parts() + self.store_parts_opt() + path]
        return os.path.join(os.environ["HGC_STORE_LOCAL"], *parts)

    def local_target(self, *args, **kwargs):
        cls = law.LocalDirectoryTarget if kwargs.pop("dir", False) else law.LocalFileTarget
        return cls(self.local_path(*args), **kwargs)

    def wlcg_path(self, *path):
        parts = [str(p) for p in self.store_parts() + self.store_parts_opt() + path]
        return os.path.join(*parts)

    def wlcg_target(self, *args, **kwargs):
        cls = law.wlcg.WLCGDirectoryTarget if kwargs.pop("dir", False) else law.wlcg.WLCGFileTarget
        return cls(self.wlcg_path(*args), **kwargs)

    def auto_target(self, *args, **kwargs):
        store = kwargs.pop("store", self.default_store)
        store = os.path.expandvars(store)

        # return a local or wlcg target, depending on the store
        if store == "local":
            kwargs["fs"] = law.config.get_expanded("target", "default_local_fs")
            return self.local_target(*args, **kwargs)
        elif store == "eos_user":
            kwargs.setdefault("fs", "wlcg_fs_user")
            return self.wlcg_target(*args, **kwargs)
        elif store == "eos_group":
            kwargs.setdefault("fs", "wlcg_fs_group")
            return self.wlcg_target(*args, **kwargs)
        else:
            raise ValueError("unknown store '{}', choices are local,eos_user,eos_group".format(
                store))


class HTCondorWorkflow(law.htcondor.HTCondorWorkflow):
    """
    Custom htcondor workflow with good default configs for the CERN batch system.
    """

    poll_interval = luigi.FloatParameter(default=0.5, significant=False, description="time between "
        "status polls in minutes, default: 0.5")
    transfer_logs = luigi.BoolParameter(significant=True, description="transfer job logs to the "
        "output directory, default: True")
    only_missing = luigi.BoolParameter(default=True, significant=False, description="skip tasks "
        "that are considered complete, default: True")
    max_runtime = law.DurationParameter(default=2.0, unit="h", significant=False,
        description="maximum runtime, default unit is hours, default: 2")
    cmst3 = luigi.BoolParameter(default=False, significant=False, description="use the CMS T3 "
        "HTCondor quota for jobs, default: False")

    htcondor_skip_cmssw = False

    workflow_run_decorators = [law.decorator.notify, law.wlcg.ensure_voms_proxy]

    def htcondor_bootstrap_file(self):
        return os.path.expandvars("$HGC_BASE/files/remote_bootstrap.sh")

    def htcondor_wrapper_file(self):
        return os.path.expandvars("$HGC_BASE/files/cern_htcondor_bash_wrapper.sh")

    def htcondor_output_directory(self):
        return self.local_target(dir=True)

    def htcondor_use_local_scheduler(self):
        return True

    def htcondor_workflow_requires(self):
        reqs = law.htcondor.HTCondorWorkflow.htcondor_workflow_requires(self)

        reqs["repo"] = UploadRepo.req(self, replicas=5)
        reqs["software"] = UploadSoftware.req(self, replicas=5)

        if not self.htcondor_skip_cmssw:
            reqs["cmssw"] = UploadCMSSW.req(self, replicas=5)

        return reqs

    def htcondor_job_config(self, config, job_num, branches):
        reqs = self.htcondor_workflow_requires()

        # add input files
        config.input_files.append(law.util.law_src_path("contrib/wlcg/scripts/grid_tools.sh"))

        # helper to get all possible variants of a directory url
        def uris(req_key):
            uris = reqs[req_key].output().dir.uri(cmd="filecopy", return_all=True)
            return ",".join(uris)

        # add render variables
        config.render_variables["hgc_grid_user"] = os.getenv("HGC_GRID_USER")
        config.render_variables["hgc_repo_uri"] = uris("repo")
        config.render_variables["hgc_repo_name"] = os.path.basename(reqs["repo"].get_repo_path())
        config.render_variables["hgc_repo_checksum"] = reqs["repo"].checksum
        config.render_variables["hgc_software_uri"] = uris("software")
        config.render_variables["hgc_skip_cmssw"] = str(int(self.htcondor_skip_cmssw))

        if not self.htcondor_skip_cmssw:
            config.render_variables["hgc_cmssw_uri"] = uris("cmssw")
            config.render_variables["hgc_cmssw_version"] = self.cmssw_sandbox.env["CMSSW_VERSION"]
            config.render_variables["hgc_cmssw_checksum"] = reqs["cmssw"].checksum
            config.render_variables["hgc_scram_arch"] = self.cmssw_sandbox.env["SCRAM_ARCH"]

        # add X509_USER_PROXY to input files
        user_proxy = law.wlcg.get_voms_proxy_file()
        if user_proxy and os.path.exists(user_proxy):
            config.input_files.append(user_proxy)

        # render variables
        config.render_variables["hgc_remote_type"] = "HTCONDOR"
        config.render_variables["hgc_env_path"] = os.getenv("PATH")

        # custom content
        config.custom_content.append(("requirements", "(OpSysAndVer =?= \"CentOS7\")"))
        config.custom_content.append(("log", "/dev/null"))
        config.custom_content.append(("+MaxRuntime", int(math.floor(self.max_runtime * 3600)) - 1))
        if self.cmst3:
            config.custom_content.append(("+AccountingGroup", "group_u_CMST3.all"))

        return config


class UploadSoftware(Task, law.tasks.TransferLocalFile, law.tasks.RunOnceTask):

    replicas = luigi.IntParameter(default=5, description="number of replicas to generate, "
        "default: 5")
    force_upload = luigi.BoolParameter(default=False, description="force uploading")

    version = None

    def complete(self):
        if self.force_upload and not self.has_run:
            return False
        else:
            return Task.complete(self)

    def single_output(self):
        return self.auto_target("software.tgz", fs="wlcg_fs_user")

    def run(self):
        software_path = os.environ["HGC_SOFTWARE"]

        # create the local bundle
        bundle = law.LocalFileTarget(software_path + ".tgz", is_tmp=True)

        def _filter(tarinfo):
            if re.search(r"(\.pyc|\/\.git|\.tgz|__pycache__)$", tarinfo.name):
                return None
            return tarinfo

        # create the archive with a custom filter
        bundle.dump(software_path, filter=_filter)

        # log the size
        self.publish_message("bundled software archive, size is {:.2f} {}".format(
            *law.util.human_bytes(bundle.stat.st_size)
        ))

        # transfer the bundle and mark the task as complete
        self.transfer(bundle)
        self.mark_complete()


class UploadRepo(Task, law.git.BundleGitRepository, law.tasks.TransferLocalFile):

    replicas = luigi.IntParameter(default=5, description="number of replicas to generate, "
        "default: 5")

    exclude_files = [
        ".data",
        ".law",
        "data",
        "tmp",
        "cmssw",
    ]

    version = None
    task_namespace = None

    def get_repo_path(self):
        # required by BundleGitRepository
        return os.environ["HGC_BASE"]

    def single_output(self):
        path = "{}.{}.tgz".format(os.path.basename(self.get_repo_path()), self.checksum)
        return self.auto_target(path, fs="wlcg_fs_user")

    def output(self):
        return law.tasks.TransferLocalFile.output(self)

    def run(self):
        # create the bundle
        bundle = law.LocalFileTarget(is_tmp="tgz")
        self.bundle(bundle)

        # log the size
        self.publish_message("bundled repository archive, size is {:.2f} {}".format(
            *law.util.human_bytes(bundle.stat.st_size)
        ))

        # transfer the bundle
        self.transfer(bundle)


class UploadCMSSW(Task, law.cms.BundleCMSSW, law.tasks.TransferLocalFile, law.tasks.RunOnceTask):

    replicas = luigi.IntParameter(default=5, description="number of replicas to generate, "
        "default: 5")
    force_upload = luigi.BoolParameter(default=False, description="force uploading")

    exclude = "^src/tmp"

    version = None
    task_namespace = None

    def get_cmssw_path(self):
        # required by BundleCMSSW
        return self.cmssw_base

    def complete(self):
        if self.force_upload and not self.has_run:
            return False
        else:
            return Task.complete(self)

    def single_output(self):
        path = "{}.{}.tgz".format(os.path.basename(self.get_cmssw_path()), self.checksum)
        return self.auto_target(path, fs="wlcg_fs_user")

    def output(self):
        return law.tasks.TransferLocalFile.output(self)

    def run(self):
        # create the bundle
        bundle = law.LocalFileTarget(is_tmp="tgz")
        self.bundle(bundle)

        # log the size
        self.publish_message("bundled CMSSW archive, size is {:.2f} {}".format(
            *law.util.human_bytes(bundle.stat.st_size)
        ))

        # transfer the bundle and mark the task as complete
        self.transfer(bundle)
        self.mark_complete()


class CMSSWSandboxTask(Task, law.SandboxTask):

    @property
    def sandbox(self):
        return self.cmssw_sandbox.key

    def sandbox_stagein_mask(self):
        # disable stage-in
        return False

    def sandbox_stageout_mask(self):
        # disble stage-out
        return False


class InstallCMSSW(Task, law.tasks.RunOnceTask):

    cores = luigi.IntParameter(default=1, description="the number of cores for compilation, "
        "default: 1")

    version = None

    @law.decorator.notify
    @law.wlcg.ensure_voms_proxy
    def run(self):
        # when the cmsssw checkout does not exist yet, run the install script
        # otherwise, just build again
        if os.path.exists(self.cmssw_base):
            cmd = "scram b -j {}".format(self.cores)
            cwd = os.path.join(self.cmssw_base, "src")
        else:
            install_script = os.path.expandvars("$HGC_BASE/files/install_{}.sh".format(
                self.cmssw_version))
            cmd = "{} {}".format(install_script, self.cores)
            cwd = None

        self.publish_message("installing CMSSW with command '{}'".format(cmd))
        code = law.util.interruptable_popen(cmd, cwd=cwd, shell=True, executable="/bin/bash")[0]
        if code != 0:
            raise Exception("CMSSW installation failed")

        self.mark_complete()


# class CompileConverter(Task):

#     eos = None
#     version = None

#     def output(self):
#         return law.LocalFileTarget("$HGC_BASE/modules/hgcal-rechit-input-dat-gen/analyser")

#     @law.decorator.notify
#     @law.decorator.safe_output
#     def run(self):
#         # create the compilation command
#         cmd = "source env.sh '' && make clean && make"

#         # determine the directory in which to run
#         cwd = self.output().parent.path

#         # run the command
#         code = law.util.interruptable_popen(cmd, cwd=cwd, shell=True, executable="/bin/bash")[0]
#         if code != 0:
#             raise Exception("converter compilation failed")


# class CompileDeepJetCore(Task):

#     n_cores = luigi.IntParameter(default=1, significant=False, description="number of cores to use "
#         "for compilation")
#     clean = luigi.BoolParameter(default=False, description="run 'make clean' before compilation")

#     eos = None
#     version = None

#     def output(self):
#         return law.LocalFileTarget("$HGC_BASE/modules/DeepJetCore/compiled/classdict.so")

#     def get_setup_cmd(self):
#         # returns the command required to setup the conda and DeepJetCore env's
#         conda_executable = "$HGC_CONDA_DIR/bin/conda"
#         cmd = """
#             eval "$( scram unsetenv -sh )" &&
#             eval "$( {} shell.bash hook )" &&
#             cd $HGC_BASE/modules/DeepJetCore &&
#             source env.sh \
#         """.format(conda_executable)
#         return cmd

#     def get_setup_env(self):
#         env = os.environ.copy()
#         env["PYTHONPATH"] = env["HGC_PYTHONPATH_ORIG"]
#         return env

#     @law.decorator.notify
#     @law.decorator.safe_output
#     def run(self):
#         # create the compilation command
#         cmd = "{} && cd $HGC_BASE/modules/DeepJetCore/compiled".format(self.get_setup_cmd())
#         if self.clean:
#             cmd += " && make clean"
#         cmd += " && make -j {}".format(self.n_cores)

#         # run the command
#         code = law.util.interruptable_popen(cmd, env=self.get_setup_env(), shell=True,
#             executable="/bin/bash")[0]
#         if code != 0:
#             raise Exception("DeepJetCore compilation failed")
