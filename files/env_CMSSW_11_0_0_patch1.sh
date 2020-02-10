#!/usr/bin/env bash

action() {
    local origin="$( pwd )"

    export SCRAM_ARCH="slc7_amd64_gcc820"
    export CMSSW_VERSION="CMSSW_11_0_0_patch1"
    export CMSSW_BASE="$( hgc_cmssw_base )"

    source "/cvmfs/cms.cern.ch/cmsset_default.sh" ""
    cd "$CMSSW_BASE/src" || return "$?"
    eval `scramv1 runtime -sh` || return "$?"
    cd "$origin"

    export GFAL_PLUGIN_DIR="$HGC_SOFTWARE/gfal2_${CMSSW_VERSION}"

    export LAW_SANDBOX="bash::\$HGC_BASE/files/env_${CMSSW_VERSION}.sh"
}
action "$@"
