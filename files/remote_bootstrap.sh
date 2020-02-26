#!/usr/bin/env bash

action() {
    # source law wlcg tools
    source "law_wlcg_tools{{file_postfix}}.sh" ""


    #
    # set env variables
    #

    exportHGCON_{{hgc_remote_type}}="1"
    export HGC_DATA="$LAW_JOB_HOME/hgc_data"
    export HGC_SOFTWARE="$HGC_DATA/software"
    export HGC_STORE="$HGC_DATA/store"
    export HGC_LOCAL_CACHE="$HGC_DATA/cache"
    export HGC_GRID_USER="{{hgc_grid_user}}"
    export HGC_CMSSW_BASE="$HGC_DATA/cmssw"

    local skip_cmssw="{{hgc_skip_cmssw}}"
    export SCRAM_ARCH="{{hgc_scram_arch}}"
    export CMSSW_VERSION="{{hgc_cmssw_version}}"

    mkdir -p "$HGC_DATA"


    #
    # load the software bundle
    #

    mkdir -p "$HGC_SOFTWARE"
    cd "$HGC_SOFTWARE"
    law_wlcg_download_file "{{hgc_software_uri}}" "software\.\d+\.tgz" "software.tgz" "3" || return "$?"
    tar -xzf "software.tgz" || return "$?"
    rm "software.tgz"
    cd "$LAW_JOB_HOME"


    #
    # load the repo bundle
    #

    law_wlcg_download_file "{{hgc_repo_uri}}" "{{hgc_repo_name}}\.{{hgc_repo_checksum}}\.\d+\.tgz" "repo.tgz" "3" || return "$?"
    tar -xzf "repo.tgz" || return "$?"
    rm "repo.tgz"

    # source the repo setup
    source "{{hgc_repo_name}}/setup.sh" ""


    #
    # setup CMSSW
    #

    if [ "$skip_cmssw" != "1" ]; then
        (
            source "/cvmfs/cms.cern.ch/cmsset_default.sh" ""
            mkdir -p "$HGC_CMSSW_BASE"
            cd "$HGC_CMSSW_BASE"
            scramv1 project CMSSW "$CMSSW_VERSION"
            cd "$CMSSW_VERSION"
            law_wlcg_download_file "{{hgc_cmssw_uri}}" "$CMSSW_VERSION\.{{hgc_cmssw_checksum}}\.\d+\.tgz" "cmssw.tgz" "3" || return "$?"
            tar -xzf "cmssw.tgz" || return "$?"
            rm "cmssw.tgz"
            cd src
            eval `scramv1 runtime -sh`
            scram build || return "$?"
        )
    fi

    return "0"
}
action "$@"
