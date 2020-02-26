# coding: utf-8

"""
Config file for running GEN, SIM and DIGI steps with configurable gun / physics process and pileup.
"""

import os
import math

import FWCore.ParameterSet.Config as cms
from FWCore.ParameterSet.VarParsing import VarParsing
from reco_prodtools.templates.GSD_fragment import process


# constants
HGCAL_Z = 319.0
HGCAL_ETA_MIN = 1.52
HGCAL_ETA_MAX = 3.00


# helpers
def calculate_rho(z, eta):
    return z * math.tan(2 * math.atan(math.exp(-eta)))


# option parsing
options = VarParsing("python")

options.setDefault("outputFile", "file:gsd.root")
options.setDefault("maxEvents", 1)

options.register("generator", "flatEtaGun:50", VarParsing.multiplicity.singleton,
    VarParsing.varType.string, "a string that configures the generator or physics process")
options.register("pileup", 0, VarParsing.multiplicity.singleton, VarParsing.varType.int,
    "pileup")
options.register("seed", 1, VarParsing.multiplicity.singleton, VarParsing.varType.int,
    "random seed")

options.parseArguments()


# input / output
process.maxEvents.input = cms.untracked.int32(options.maxEvents)
process.FEVTDEBUGHLToutput.fileName = cms.untracked.string(
    options.__getattr__("outputFile", noTags=True))
process.source.firstLuminosityBlock = cms.untracked.uint32(1)


# random seeds
seed = int(options.seed) + 1
process.RandomNumberGeneratorService.generator.initialSeed = cms.untracked.uint32(seed)
process.RandomNumberGeneratorService.VtxSmeared.initialSeed = cms.untracked.uint32(seed)
process.RandomNumberGeneratorService.mix.initialSeed = cms.untracked.uint32(seed)


# generator gun or physics process
gen_parts = options.generator.split(":")
if gen_parts[0] == "flatEtaGun":
    defaults = ("50", "3.0", "100.0")
    gen_parts += defaults[len(gen_parts) - 1:]

    process.generator = cms.EDProducer("FlatEtaRangeGunProducer",
        # particle ids
        particleIDs=cms.vint32(22, 22, 11, -11, 211, -211, 13, -13),
        # max number of particles to shoot at a time
        nParticles=cms.int32(int(gen_parts[1])),
        # shoot exactly the particles defined in particleIDs in that order
        exactShoot=cms.bool(False),
        # randomly shoot [1, nParticles] particles, each time randomly drawn from particleIDs
        randomShoot=cms.bool(False),
        # energy range
        eMin=cms.double(float(gen_parts[2])),
        eMax=cms.double(float(gen_parts[3])),
        # phi range
        phiMin=cms.double(-math.pi),
        phiMax=cms.double(math.pi),
        # eta range
        etaMin=cms.double(HGCAL_ETA_MIN),
        etaMax=cms.double(HGCAL_ETA_MAX),
        # misc
        debug=cms.untracked.bool(True),
    )
elif gen_parts[0] == "flatDeltaRGun":
    defaults = ("50", "3.0", "100.0", "0.0", "0.5")
    gen_parts += defaults[len(gen_parts) - 1:]

    process.generator = cms.EDProducer("CloseByFlatDeltaRGunProducer",
        # particle ids
        particleIDs=cms.vint32(22, 22, 11, -11, 211, -211, 13, -13),
        # max number of particles to shoot at a time
        nParticles=cms.int32(int(gen_parts[1])),
        # shoot exactly the particles defined in particleIDs in that order
        exactShoot=cms.bool(False),
        # randomly shoot [1, nParticles] particles, each time randomly drawn from particleIDs
        randomShoot=cms.bool(False),
        # energy range
        eMin=cms.double(float(gen_parts[2])),
        eMax=cms.double(float(gen_parts[3])),
        # phi range
        phiMin=cms.double(-math.pi),
        phiMax=cms.double(math.pi),
        # eta range
        etaMin=cms.double(HGCAL_ETA_MIN),
        etaMax=cms.double(HGCAL_ETA_MAX),
        # longitudinal gun position in cm
        zMin=cms.double(0.),
        zMax=cms.double(0.),
        # deltaR settings
        deltaRMin=cms.double(float(gen_parts[4])),
        deltaRMax=cms.double(float(gen_parts[5])),
        # misc
        debug=cms.untracked.bool(True),
    )
else:
    raise ValueError("unknown generator type '{}'".format(gen_parts[0]))


# configure pileup
if options.pileup > 0:
    process.load("SimGeneral.MixingModule.mix_POISSON_average_cfi")
    process.mix.input.nbPileupEvents.averageNumber = cms.double(options.pileup)
    local_pu_dir = "/eos/cms/store/cmst3/group/hgcal/CMG_studies/pepr/pu/RelvalMinBias14_106X_upgrade2023_realistic_v3_2023D41noPU-v1"  # noqa
    process.mix.input.fileNames = cms.untracked.vstring([
        "file://" + os.path.abspath(os.path.join(local_pu_dir, elem))
        for elem in os.listdir(local_pu_dir)
        if elem.endswith(".root")
    ])
else:
    process.load("SimGeneral.MixingModule.mixNoPU_cfi")


# print some stats
print("pileup   : {}".format(options.pileup))
print("generator: {}".format(process.generator.dumpConfig()))
