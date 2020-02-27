# HGCAL simulation using law


### Resources

- [law](https://law.readthedocs.io/en/latest)
- [luigi](https://luigi.readthedocs.io/en/stable)


### Setup

This repository has submodules, so you should clone it with

```shell
git clone --recursive https://github.com/cms-pepr/hgcalsim.git
```

By default, the simulation tasks store their output in the common hgcalsim output directory on EOS at `/eos/cms/store/cmst3/group/hgcal/CMG_studies/pepr/hgcalsim` (== `$HGC_STORE_EOS_GROUP`). Make sure you obtain the necessary access permissions.

If you want to store outputs at a different location, run

```shell
export HGC_DEFAULT_STORE="local"
export HGC_STORE_LOCAL="YOUR_LOCATION_HERE"  # defaults to "store/" relative to the repository
```

or add the lines (e.g.) to your `.bashrc` to make this change permanent.

After cloning the repository, run

```shell
source setup.sh
```

This will install a few python packages **once**. You should source the setup script everytime you start with a new session.


### Luigi scheduler

Task statuses and dependency trees can be visualized live using a central luigi scheduler. **This is optional** and no strict requirement to run tasks.

In order to let the tasks communicate with a central luigi scheduler, you should set

```shell
export HGC_SCHEDULER_HOST="<user>:<pass>@<host>"
```

most probably in your bashrc file.

You can also [setup a personal scheduler on OpenStack](https://github.com/CMS-HGCAL/hgcalsim/wiki#setting-up-a-luigi-scheduler-on-openstack), or use the [common hgcalsim scheduler](http://hgcalsim-common-scheduler1.cern.ch) (host is `hgcalsim-common-scheduler1`, please [ask](mailto:marcel.rieger@cern.ch?Subject=Access%20to%20common%20hgcalsim%20scheduler) for user and password).


### Example commands

##### Compile CMSSW with 2 cores after making some updates to the code:

```shell
law run base.InstallCMSSW --cores 2
```

##### Run GSD, RECO, and (window) NTUP steps in one go

```shell
law run sim.NtupleTask \
  --version dev \
  --n-events 10 \
  --pileup 200 \
  --branch 0 \
  --generator flatEtaGun:50:3.0:100.0  # 50 particles in the energy range 3.0 - 100.0 GeV
```

The underlying config files for `cmsRun` are located in [files/](files/):

- [gsd_cfg.py](files/gsd_cfg.py)
- [reco_cfg.py](files/reco_cfg.py)
- [ntup_cfg.py](files/ntup_cfg.py)


**Note:** `sim.NtupleTask` is a so-called *workflow*, i.e., a task that triggers the execution of multiple so-called *branch* tasks, or *branches*, whose difference can be expressed by a single number. In this case, one would change the seed for different branch numbers. Without passing a value for the `--branch` parameter, all branches are executed. But here, we set `--branch 0` which triggers only the execution of the first branch. You can add `--n-tasks N` to set the total number of branches (the default is 1 anyway).

See the [law docs on workflows](https://law.readthedocs.io/en/latest/workflows.html) for more info on workflows, and the next example command to run multiple branches on htcondor.


##### Run GSD, RECO, and (window) NTUP steps on htcondor

```shell
law run sim.NtupleTask \
  --version dev \
  --n-events 10 \
  --pileup 200 \
  --n-tasks 10 \
  --workflow htcondor \
  --max-runtime 2h \
  --transfer-logs \
  --pilot \
  --generator flatEtaGun:50:3.0:100.0  # 50 particles in the energy range 3.0 - 100.0 GeV
```
