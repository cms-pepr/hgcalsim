#!/usr/bin/env bash

action() {

    #
    # global variables
    #

    # determine the directory of this file
    local this_file="$( [ ! -z "$ZSH_VERSION" ] && echo "${(%):-%x}" || echo "${BASH_SOURCE[0]}" )"
    local this_dir="$( cd "$( dirname "$this_file" )" && pwd )"
    export HGC_BASE="$this_dir"

    # check if cvmfs is mounted
    if [ -d "/cvmfs/cms.cern.ch" ]; then
        export HGC_HAS_CVMFS="1"
    else
        export HGC_HAS_CVMFS="0"
    fi

    # check if /eos/cms is mounted
    if [ -d "/eos/cms" ]; then
        export HGC_HAS_EOS_CMS="1"
    else
        export HGC_HAS_EOS_CMS="0"
    fi

    # check if /eos/user is mounted
    if [ -d "/eos/user" ]; then
        export HGC_HAS_EOS_USER="1"
    else
        export HGC_HAS_EOS_USER="0"
    fi

    # check if we're on lxplus
    if [[ "$( hostname )" = lxplus*.cern.ch ]]; then
        export HGC_ON_LXPLUS="1"
    else
        export HGC_ON_LXPLUS="0"
    fi

    # check if this setup script is sourced by a remote job
    if [ "$HGC_ON_HTCONDOR" = "1" ] || [ "$HGC_ON_GRID" = "1" ]; then
        export HGC_REMOTE_JOB="1"
    else
        export HGC_REMOTE_JOB="0"
    fi

    # default grid user
    if [ -z "$HGC_GRID_USER" ]; then
        if [ "$HGC_ON_LXPLUS" = "1" ]; then
            export HGC_GRID_USER="$( whoami )"
            echo "NOTE: lxplus detected, setting HGC_GRID_USER to $HGC_GRID_USER"
        else
            2>&1 echo "please set HGC_GRID_USER to your grid user name and try again"
            return "1"
        fi
    fi
    export HGC_GRID_USER_FIRST_CHAR="${HGC_GRID_USER:0:1}"

    # other hgc defaults
    [ -z "$HGC_DATA" ] && export HGC_DATA="$HGC_BASE/data"
    [ -z "$HGC_SOFTWARE" ] && export HGC_SOFTWARE="$HGC_DATA/software"
    [ -z "$HGC_STORE_LOCAL" ] && export HGC_STORE_LOCAL="$HGC_DATA/store"
    export HGC_STORE_EOS_GROUP="/eos/cms/store/cmst3/group/hgcal/CMG_studies/pepr/hgcalsim"
    export HGC_STORE_EOS_USER="/eos/cms/store/cmst3/group/hgcal/CMG_studies/$HGC_GRID_USER/hgcalsim"
    [ -z "$HGC_DEFAULT_WLCG_FS" ] && export HGC_DEFAULT_WLCG_FS="wlcg_fs_group"
    [ -z "$HGC_DEFAULT_STORE" ] && export HGC_DEFAULT_STORE="eos_group"
    [ -z "$HGC_CMSSW_BASE" ] && export HGC_CMSSW_BASE="$HGC_BASE/cmssw"

    # law and luigi configs
    export LAW_HOME="$HGC_BASE/.law"
    export LAW_CONFIG_FILE="$HGC_BASE/law.cfg"

    # configs that differ on the grid
    if [ "$HGC_REMOTE_JOB" = "1" ]; then
        export HGC_LUIGI_WORKER_KEEP_ALIVE="False"
        export HGC_LUIGI_WORKER_FORCE_MULTIPROCESSING="True"
    else
        export HGC_LUIGI_WORKER_KEEP_ALIVE="False"
        export HGC_LUIGI_WORKER_FORCE_MULTIPROCESSING="False"
    fi

    if [ -z "$HGC_SCHEDULER_HOST" ]; then
        2>&1 echo "NOTE: HGC_SCHEDULER_HOST is not set, default to local scheduler (HGC_LOCAL_SCHEDULER=True)"
        export HGC_LOCAL_SCHEDULER="True"
    elif [ -z "$HGC_LOCAL_SCHEDULER" ]; then
        export HGC_LOCAL_SCHEDULER="False"
    fi
    [ -z "$HGC_SCHEDULER_PORT" ] && export HGC_SCHEDULER_PORT="80"


    #
    # helper functions
    #

    hgc_pip_install() {
        pip install --ignore-installed --no-cache-dir --prefix "$HGC_SOFTWARE" "$@"
    }
    [ -z "$ZSH_VERSION" ] && export -f hgc_pip_install

    hgc_add_py() {
        export PYTHONPATH="$1:$PYTHONPATH"
    }
    [ -z "$ZSH_VERSION" ] && export -f hgc_add_py

    hgc_add_bin() {
        export PATH="$1:$PATH"
    }
    [ -z "$ZSH_VERSION" ] && export -f hgc_add_bin

    hgc_add_lib() {
        export LD_LIBRARY_PATH="$1:$LD_LIBRARY_PATH"
    }
    [ -z "$ZSH_VERSION" ] && export -f hgc_add_lib

    hgc_cmssw_base() {
        if [ -z "$CMSSW_VERSION" ]; then
            2>&1 echo "CMSSW_VERSION must be set for hgc_cmssw_path"
            return "1"
        fi
        echo "$HGC_CMSSW_BASE/$CMSSW_VERSION"
    }
    [ -z "$ZSH_VERSION" ] && export -f hgc_cmssw_base


    #
    # minimal software stack
    #

    # certificate proxy handling
    [ "$HGC_REMOTE_JOB" != "1" ] && export X509_USER_PROXY="/tmp/x509up_u$( id -u )"

    # variables for external software
    export PYTHONWARNINGS="ignore"
    export GLOBUS_THREAD_MODEL="none"
    export LCG_SOFTWARE_BASE="/cvmfs/grid.cern.ch/centos7-ui-4.0.3-1_umd4v3/usr"
    if [ -d "$LCG_SOFTWARE_BASE" ]; then
        export GFAL_PLUGIN_DIR="$LCG_SOFTWARE_BASE/lib64/gfal2-plugins"
    else
        2>&1 echo "NOTE: LCG_SOFTWARE_BASE $LCG_SOFTWARE_BASE does not exist"
    fi

    # ammend software paths
    hgc_add_bin "$HGC_SOFTWARE/bin:$LCG_SOFTWARE_BASE/bin"
    hgc_add_py "$HGC_SOFTWARE/lib/python2.7/site-packages:$HGC_SOFTWARE/lib64/python2.7/site-packages:$LCG_SOFTWARE_BASE/lib64/python2.7/site-packages"
    hgc_add_lib "$LCG_SOFTWARE_BASE/lib64:$LCG_SOFTWARE_BASE/lib"

    # software that is used in this project
    hgc_install_software() {
        local origin="$( pwd )"
        local mode="$1"

        if [ -d "$HGC_SOFTWARE" ]; then
            if [ "$mode" = "force" ]; then
                echo "remove software in $HGC_SOFTWARE"
                rm -rf "$HGC_SOFTWARE"
            else
                if [ "$mode" != "silent" ]; then
                    echo "software already installed in $HGC_SOFTWARE"
                fi
                return "0"
            fi
        fi

        echo "installing software stack in $HGC_SOFTWARE"
        mkdir -p "$HGC_SOFTWARE"

        hgc_pip_install "setuptools<45"
        hgc_pip_install tabulate
        hgc_pip_install requests
        hgc_pip_install python-telegram-bot
        hgc_pip_install slackclient
        hgc_pip_install luigi

        # avoid psutil for python 2.7
        rm -rf $HGC_SOFTWARE/lib/python2.7/site-packages/psutil*
        rm -rf $HGC_SOFTWARE/lib64/python2.7/site-packages/psutil*
        echo "raise ImportError('psutil disabled manually')" > "$HGC_SOFTWARE/lib64/python2.7/site-packages/psutil.py"
    }
    [ -z "$ZSH_VERSION" ] && export -f hgc_install_software
    hgc_install_software silent

    # add _this_ repo to the python path
    hgc_add_py "$HGC_BASE"

    # submodules
    hgc_add_py "$HGC_BASE/modules/plotlib"
    hgc_add_py "$HGC_BASE/modules/law"
    hgc_add_bin "$HGC_BASE/modules/law/bin"

    if [ "$HGC_REMOTE_JOB" != "1" ]; then
        # source law's bash completion scipt
        source "$( law completion )" ""

        # run law's task indexing
        law index --verbose

        # check the proxy validity
        LAW_LOG_LEVEL=WARNING python -c "import law;law.contrib.load('wlcg');law.wlcg.check_voms_proxy_validity(log=True)"
    fi
}
action "$@"
