#!/usr/bin/env bash

action() {
    local origin="$( pwd )"
    local scram_cores="${SCRAM_CORES:-1}"

    export SCRAM_ARCH="slc7_amd64_gcc820"
    export CMSSW_VERSION="CMSSW_11_0_0_patch1"
    export CMSSW_BASE="$( hgc_cmssw_base )"

    if [ -d "$CMSSW_BASE" ]; then
        echo "remove already installed software in $CMSSW_BASE"
        rm -rf "$CMSSW_BASE"
    fi

    echo "setting up $CMSSW_VERSION with $SCRAM_ARCH in $CMSSW_BASE"

    source "/cvmfs/cms.cern.ch/cmsset_default.sh" ""
    mkdir -p "$( dirname "$CMSSW_BASE" )"
    cd "$( dirname "$CMSSW_BASE" )"
    scramv1 project CMSSW "$CMSSW_VERSION" || return "$?"
    cd "$CMSSW_VERSION/src"
    eval `scramv1 runtime -sh` || return "$?"
    scram b || return "$?"


    #
    # custom packages
    #

    git cms-init

    git cms-merge-topic cms-pepr:pepr_CMSSW_11_0_0_patch1 || return "$?"

    # TODO: use central repo from CMS-HGCAL again when private branch is merged
    # git clone --recursive https://github.com/CMS-HGCAL/reco-prodtools.git reco_prodtools
    # ( cd reco_prodtools; git checkout dev )
    git clone --recursive https://github.com/riga/reco-prodtools.git reco_prodtools
    ( cd reco_prodtools; git checkout hgctruth )

    git clone https://github.com/CMS-HGCAL/reco-ntuples.git RecoNtuples

    scram b -j "$scram_cores" || return "$?"


    #
    # create prodtools templates
    #

    cd reco_prodtools/templates/python
    # the next line requires a valid proxy
    ./produceSkeletons_D41_NoSmear_PU_AVE_200_BX_25ns.sh || return "$?"
    cd "$CMSSW_VERSION/src"
    scram b python


    #
    # custom gfal2 bindings
    #

    source "$(law location)/contrib/cms/scripts/setup_gfal_plugins.sh" "$HGC_SOFTWARE/gfal2_${CMSSW_VERSION}" || return "$?"
    unlink "$GFAL_PLUGIN_DIR/libgfal_plugin_http.so"


    cd "$origin"
}
action "$@"
