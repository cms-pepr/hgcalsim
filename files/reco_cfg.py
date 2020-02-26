# coding: utf-8

"""
Config file for running the RECO step.
"""


import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing
from reco_prodtools.templates.RECO_fragment import process


# option parsing
options = VarParsing("python")

options.setDefault("outputFile", "file:reco.root")
options.setDefault("maxEvents", -1)

options.register("outputFileDQM", "file:dqm.root", VarParsing.multiplicity.singleton,
    VarParsing.varType.string, "path to the DQM output file")

options.parseArguments()


# input / output
process.maxEvents.input = cms.untracked.int32(options.maxEvents)
process.source.fileNames = cms.untracked.vstring(options.inputFiles)
process.FEVTDEBUGHLToutput.fileName = cms.untracked.string(
    options.__getattr__("outputFile", noTags=True))
process.DQMoutput.fileName = cms.untracked.string(options.outputFileDQM)
process.source.firstLuminosityBlock = cms.untracked.uint32(1)


# add the HGCTruthProducer
# (this is currently running in the ntup config for fast testing, but should be moved here again
# once a valid truth is established)
# process.hgcSimTruth = cms.EDProducer("HGCTruthProducer")
# process.recosim_step += process.hgcSimTruth
# process.FEVTDEBUGHLToutput.outputCommands.append("keep *_hgcSimTruth_*_*")
