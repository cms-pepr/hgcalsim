# coding: utf-8

"""
Config file for creating ntuples in hgcal windows.
"""


import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing
from reco_prodtools.templates.NTUP_fragment import process


# option parsing
options = VarParsing("python")

options.setDefault("outputFile", "file:ntup.root")
options.setDefault("maxEvents", -1)

options.parseArguments()


# input / output
process.maxEvents.input = cms.untracked.int32(options.maxEvents)
process.source.fileNames = cms.untracked.vstring(options.inputFiles)
process.TFileService = cms.Service("TFileService", fileName=cms.string(
    options.__getattr__("outputFile", noTags=True)))
process.source.firstLuminosityBlock = cms.untracked.uint32(1)


# define a custom sequence to run
seq = cms.Sequence()

# add the HGCTruthProducer
# (this should be moved to the reco step once a valid truth is established)
process.hgcSimTruth = cms.EDProducer("HGCTruthProducer")
seq += process.hgcSimTruth


# load and configure the windowInference module
from RecoHGCal.GraphReco.windowNTupler_cfi import WindowNTupler
# one version for the custum truth
process.windowNTupler = WindowNTupler.clone(
    simClusters="hgcSimTruth",
)
seq += process.windowNTupler
# one version for the default truth
process.windowNTuplerDefaultTruth = WindowNTupler.clone()
seq += process.windowNTuplerDefaultTruth


# remove all registered paths and the schedule,
# so that only our ntuplizer paths will be executed
for p in process.paths:
    delattr(process, p)
delattr(process, "schedule")


# define the schedule
process.p = cms.Path(seq)
process.schedule = cms.Schedule(process.p)
